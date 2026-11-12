# L'export du journal Sas — un format ouvert et vérifiable

> **Ce que ce document est.** L'export du journal est un **format**, pas un
> appel de fonction. C'est ce qui quitte la plateforme vers un auditeur, un
> assureur, ou un autre agent, et ce qu'ils doivent pouvoir vérifier **sans
> exécuter Sas**, avec la seule bibliothèque standard de Python, en ne lisant
> que cette page.
>
> **Où est la vérité.** Le producteur est `src/sas/journal/export.py` : il
> écrit l'enveloppe et porte les entrées, octet pour octet, telles que la
> chaîne (`src/sas/journal/chaine.py`) les a produites. Le vérificateur livré
> avec le dépôt, `src/sas/journal/audit.py`, n'est **pas** le code du producteur
> réutilisé : c'est ce format publié, réimplémenté — la seule façon pour qu'un
> audit ait un sens. Les deux implémentations sont une duplication assumée, et
> un test (`tests/unit/journal/test_audit_isole.py`) prouve que l'auditeur
> s'exécute dans un interpréteur qui n'a jamais importé un seul module de Sas.
>
> **Pourquoi ce format existe.** Sans export publié et auto-descriptif, un tiers
> ne peut pas dire si le journal reçu est complet, ni si une entrée a été
> modifiée après coup. Il ne pourrait que faire confiance à Sas — ce qui n'est
> pas un audit.

---

## 1. La forme d'un export

L'export est un unique document texte UTF-8, en deux parties :

* **ligne 1** — l'enveloppe : un objet JSON, forme canonique (voir §3) ;
* **lignes 2..n** — les entrées : JSON Lines, une entrée par ligne, dans
  l'ordre du journal, verbatim.

```
{"format_version":"sas-journal-export/1","exporte_le":"2026-11-20T10:00:00+00:00", … }
{"id":"appel-0","session_id":"sess-a", …, "empreinte_prec":"", "empreinte":"sha256:…"}
{"id":"appel-1","session_id":"sess-a", …, "empreinte_prec":"sha256:…", "empreinte":"sha256:…"}
```

Les entrées sont exactement les JSON Lines que `JournalChaine.exporter()`
produisait déjà avant ce format. L'enveloppe ne les **réécrit** pas : elle dit
ce qu'elles sont et comment les vérifier.

## 2. L'enveloppe

Un objet JSON, forme canonique. Champs :

| Champ | Type | Sens |
|---|---|---|
| `format_version` | str | `"sas-journal-export/1"` — une version inconnue est **refusée**, jamais devinée |
| `exporte_le` | str | date ISO-8601 de l'export, UTC |
| `producteur` | str | le producteur (`"sas"`) |
| `algorithme` | objet | l'algorithme, décrit **comme données** (voir §3) |
| `sessions` | liste | un objet par session : son id, son nombre d'entrées, son empreinte finale, son état d'intégrité |
| `entrees` | int | le nombre total d'entrées que le fichier doit porter |
| `empreinte_export` | str | l'empreinte du fichier entier (voir §4) |

Un objet de `sessions[]` est :

| Champ | Type | Sens |
|---|---|---|
| `session_id` | str | l'identifiant de la session |
| `entrees` | int | nombre d'entrées de cette session présentes dans le fichier |
| `empreinte_finale` | str | l'empreinte de la **dernière** entrée de la session |
| `integrite` | bool | l'état d'intégrité de cette session, selon le producteur |
| `premiere_rupture` | str \| null | l'id de la première entrée rompue, ou `null` |

## 3. L'algorithme, en données

`algorithme` porte tout ce qu'un tiers doit savoir pour recalculer. Trois
choses :

**Le hash et la forme canonique.** `empreinte` vaut `"sha256"` ; le condensat
est préfixé `"sha256:"`. `canonique` décrit la sérialisation qui doit précéder
le hash :

* `cles_triees` = `true` — les clés des objets sont triées ;
* `separateurs` = `[",", ":"]` — les deux séparateurs passés à
  `json.dumps(..., separators=(",", ":"))` (aucune espace) ;
* `ensure_ascii` = `false` — les caractères non-ASCII sont conservés tels quels ;
* `encodage` = `"utf-8"` — l'encodage des octets donnés au hash.

En Python standard, la forme canonique est donc :

```python
def canonique(valeur):
    return json.dumps(valeur, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

**La règle de projection.** L'empreinte d'une entrée couvre l'entrée **entière**,
moins les deux champs de chaîne. `projection.champs_exclus` =
`["empreinte", "empreinte_prec"]` — retirer exactement ces deux clés, garder
tout le reste.

**Le lien.** La chaîne est **par session**. Pour la première entrée d'une
session, l'empreinte précédente est la chaîne vide (`liaison.graine` = `""`) ;
chaque entrée se relie ensuite à la précédente de sa session :

```python
def empreinte(entree, precedente):
    projection = canonique(entree_sans_empreinte_ni_empreinte_prec)
    corps = canonique({"prec": precedente, "entree": projection})
    return "sha256:" + hashlib.sha256(corps.encode("utf-8")).hexdigest()
```

## 4. La complétude du fichier

La chaîne prouve que les entrées ont été enchaînées l'une après l'autre ; elle
ne dit rien de savoir si le fichier reçu contient **toutes** les entrées. Pour
cela, l'enveloppe déclare `entrees`, les `entrees` par session, les
`empreinte_finale` par session, et l'`empreinte_export` du fichier :

```python
empreinte_export = "sha256:" + hashlib.sha256(
    canonique([empreinte de chaque entrée, dans l'ordre du fichier]).encode("utf-8")
).hexdigest()
```

Une entrée manquante, ajoutée, ou réordonnée change cette valeur ; l'auditeur
refuse le fichier. C'est ce que signifie « l'export est complet », et c'est
vérifiable depuis le texte seul.

## 5. Les motifs de refus

Un refus porte un code stable et un message actionnable. Ce sont les codes que
l'auditeur de référence (`src/sas/journal/audit.py`) renvoie dans son champ
`motif` :

| Code | Déclencheur | Ce que cela signifie |
|---|---|---|
| `export-vide` | le fichier est vide | il n'y a rien à vérifier |
| `enveloppe-invalide` | la première ligne n'est pas un objet JSON | l'enveloppe est illisible |
| `format-inconnu` | `format_version` est absent ou inconnu | le format n'est pas celui que cet auditeur connaît ; il n'est **pas** deviné |
| `enveloppe-incomplete` | un champ obligatoire de l'enveloppe manque | l'export est tronqué à l'en-tête |
| `algorithme-inconnu` | l'algorithme déclaré n'est pas celui implémenté | le vérifier reviendrait à vérifier autre chose |
| `entree-invalide` | une ligne d'entrée n'est pas un objet JSON, ou manque un champ | les entrées sont illisibles |
| `liaison-rompue` | l'`empreinte_prec` d'une entrée ne correspond pas à la chaîne | une entrée a été supprimée ou déplacée |
| `empreinte-incoherente` | l'empreinte recalculée diffère | une entrée a été modifiée après coup |
| `export-incomplet` | une session manque, est courte, ou ne finit pas sur l'empreinte déclarée | le fichier ne porte pas ce qu'il déclare |
| `empreinte-export-incoherente` | l'empreinte du fichier entier diffère | le fichier a été modifié après l'export |

## 6. Le vérificateur, copiable tel quel

Le code ci-dessous est le vérificateur du format publié, bibliothèque standard
uniquement. Il lit l'export sur son entrée standard et affiche `INTÈGRE` ou
`RUPTURE …`.

```python
#!/usr/bin/env python3
"""Journal export verifier — Python standard library only."""
import hashlib
import json
import sys

VERSION = "sas-journal-export/1"
EXCLUS = ("empreinte", "empreinte_prec")


def canonique(valeur):
    return json.dumps(valeur, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def projecter(entree):
    return canonique({c: v for c, v in entree.items() if c not in EXCLUS})


def empreinte(entree, precedente):
    corps = canonique({"prec": precedente, "entree": projecter(entree)})
    return "sha256:" + hashlib.sha256(corps.encode("utf-8")).hexdigest()


def rupture(message):
    print(f"RUPTURE : {message}")
    sys.exit(1)


def main():
    texte = sys.stdin.read()
    lignes = [l for l in texte.splitlines() if l.strip()]
    if not lignes:
        rupture("export vide")
    enveloppe = json.loads(lignes[0])
    if enveloppe.get("format_version") != VERSION:
        rupture(f"version inconnue {enveloppe.get('format_version')!r}")
    entrees = [json.loads(l) for l in lignes[1:]]
    prec = {}
    vues = {}
    for entree in entrees:
        session = entree["session_id"]
        vues[session] = vues.get(session, 0) + 1
        if entree["empreinte_prec"] != prec.get(session, ""):
            rupture(f"entrée {entree['id']!r} : lien rompu")
        if empreinte(entree, prec.get(session, "")) != entree["empreinte"]:
            rupture(f"entrée {entree['id']!r} : empreinte incohérente")
        prec[session] = entree["empreinte"]
    declarees = sorted(
        ((s["session_id"], s) for s in enveloppe.get("sessions", [])), key=lambda p: p[0]
    )
    for session, declaration in declarees:
        if declaration["entrees"] != vues.get(session, 0):
            rupture(f"session {session!r} incomplète")
        if declaration["empreinte_finale"] != prec.get(session, ""):
            rupture(f"session {session!r} : empreinte finale incohérente")
    if enveloppe.get("entrees") != len(entrees):
        rupture("nombre d'entrées incohérent")
    empreinte_export = "sha256:" + hashlib.sha256(
        canonique([e["empreinte"] for e in entrees]).encode("utf-8")
    ).hexdigest()
    if enveloppe.get("empreinte_export") != empreinte_export:
        rupture("empreinte de l'export incohérente")
    print("INTÈGRE")


if __name__ == "__main__":
    main()
```

## 7. Ce que la vérification prouve — et ce qu'elle ne prouve pas

Ce qu'elle prouve :

* la **chaîne est intacte** — aucune entrée n'a été modifiée après sa
  production sans rompre la chaîne, et la rupture est nommée (id + index) ;
* l'**export est complet** — chaque session déclarée est présente, avec le
  nombre d'entrées déclaré, dans l'ordre, et l'empreinte du fichier correspond ;
* le **format est connu** — une version ou un algorithme inconnu est refusé,
  l'auditeur ne devine jamais.

L'auditeur est l'implémentation de référence de ce document : il se trouve dans
`sas/journal/audit.py` et n'importe rien de Sas, donc un tiers peut l'exécuter
— ou copier le §6 — et obtenir le même verdict.

Ce qu'elle ne prouve **pas** :

* Elle ne prouve **pas** que l'agent a fait ce qu'il dit avoir fait. Le journal
  consigne des décisions ; une entrée qui dit « refusé » prouve seulement que
  l'enregistrement le dit, pas que le refus était correct ni que l'agent a été
  honnête.
* Elle prouve que l'export n'a pas été **modifié après coup**. Elle ne prouve
  pas qui l'a produit, ni que le journal du producteur était lui-même honnête —
  c'est le rôle de l'archive scellée (`src/sas/audit.py`, lot 17) et de
  l'attestation.
* Un faussaire capable de réécrire tout le fichier et de recalculer toutes les
  empreintes passerait cette vérification. La chaîne garantit **l'intégrité
  dans le temps**, pas l'auteur : épinglez l'`empreinte_export` hors canal
  (dans une attestation ou un reçu signé) pour combler cet écart.
# The Sas agent manifest — open format

> **What this document is.** The manifest is a **format**, not an interview: a
> signed declaration of what a third-party agent asks for, what it commits to,
> and what it must never do. This page describes the format **as it is
> implemented**, so that a vendor can produce a compliant manifest without
> reading the code.
>
> **Where the truth lives.** The block and field table is *declared as data* in
> `src/sas/manifeste/schema.py`; the structural validator reads that table and
> the semantic validator lives in `src/sas/manifeste/validation.py`. The
> published JSON Schema, `schemas/manifeste.schema.json`, is **generated from
> the same table** (`schema_json()`), so it cannot drift from the validator —
> `test_le_schema_publie_est_a_jour` fails if the committed file differs.
>
> **Why the format exists.** Without a signed reference, an out-of-scope call is
> undeterminable: is it a fault, or a permission forgotten in the declaration?
> The manifest is also the contractual piece: an edition of the signed manifest
> is a breach, documented, dated and proven.

---

## 1. The thirteen blocks

The document is a mapping. Every key is a **block**; the thirteen blocks below
are the complete list. Any other top-level key is refused
(`bloc-inconnu`).

| # | Block | Cardinality | Required? | What it carries |
|---|---|---|---|---|
| 1 | `manifeste` | object (1) | **yes** | Header: version and date of the document |
| 2 | `identite` | object (1) | **yes** | Who and what exactly is running |
| 3 | `finalite` | object (1) | **yes** | What the agent does — and what it does not do |
| 4 | `outils_demandes` | list (0..n) | **yes** (the key must be present) | One entry per requested tool |
| 5 | `donnees_demandees` | list (0..n) | **yes** | Fine-grained resources: never "access to the data" |
| 6 | `sorties_autorisees` | list (0..n) | **yes** (the key must be present, an empty list is valid) | What the agent may send outside — **nothing by default** |
| 7 | `budgets` | object (1) | **yes** | Hard bounds, enforced by Policy before the tool runs |
| 8 | `memoire` | object (1) | no | If true, the replays are no longer independent |
| 9 | `scenarios` | list (1..n) | **yes** | The nominal use cases the agent must handle |
| 10 | `interdictions_explicites` | list (0..n) | **yes** | What the agent must never do, even if technically able |
| 11 | `engagements` | object (1) | **yes** | Vendor commitments |
| 12 | `signature` | object (1) | no (but without it nothing runs) | Editor signature |
| 13 | `validation_client` | object (1) | no (but without it nothing runs) | Sponsor validation |

Two subtleties on "required":

- `sorties_autorisees` is required by the published schema, but **an absent key
  and an empty list are not the same thing** and are not treated alike. An
  empty list is a declaration: "no outbound request". An absent key is a
  refusal, reported by the semantic validator with the code `cle-absente` and
  the action "write `sorties_autorisees: []` explicitly". This is the one
  place where the format refuses to guess.
- `memoire`, `signature` and `validation_client` are not in the required list
  of the structural schema, but a manifest without a signature and a sponsor
  validation opens **no execution** (`EF-04`).

## 2. The fields

Types: `str`, `int`, `bool`, `date`, `empreinte` (`sha256:` + 64 lowercase
hexadecimal characters), `liste` (list of strings), `objet`.

| Block | Field | Type | Required | Note |
|---|---|---|---|---|
| `manifeste` | `version` | int | yes | Manifest version, incremented on any change |
| `manifeste` | `date` | date | yes | Date of the document |
| `identite` | `nom` | str | yes | Name of the agent |
| `identite` | `editeur` | str | yes | Editor (vendor) |
| `identite` | `version_agent` | str | yes | Version of the agent; a mismatch with the running version blocks the run |
| `identite` | `empreinte_paquet` | empreinte | yes | Fingerprint of the package or image |
| `identite` | `modele` | str | yes | Underlying model |
| `identite` | `version_modele` | str | yes | Version of that model — this is what makes an undeclared drift detectable |
| `identite` | `engagement_notification_modele` | bool | yes | The editor commits to notify a model change |
| `finalite` | `fait` | str | yes | What the agent does, in one sentence |
| `finalite` | `ne_fait_pas` | liste | yes | What it must not do — the negative declaration |
| `outils_demandes` | `nom` | str | yes | Tool name |
| `outils_demandes` | `operation` | str | yes | `lecture`, `ecriture` or `execution` |
| `outils_demandes` | `justification` | str | yes | Why the agent needs it |
| `donnees_demandees` | `type` | str | yes | `s3`, `table`, `index` or `http` |
| `donnees_demandees` | `ressource` | str | yes | The precise resource: bucket **and** prefix, table **and** columns, named index |
| `donnees_demandees` | `justification` | str | yes | Why this resource is necessary |
| `donnees_demandees` | `colonnes` | liste | no | Required in practice for a `table` |
| `donnees_demandees` | `prefixes` | liste | no | Allowed prefixes |
| `donnees_demandees` | `sensible` | bool | no | The client marks the resource as sensitive |
| `sorties_autorisees` | `destination` | str | yes | One named destination — no wildcards |
| `sorties_autorisees` | `protocole` | str | yes | `http`, `courriel`, `dns` or `webhook` |
| `sorties_autorisees` | `justification` | str | yes | Why this outbound request is necessary |
| `budgets` | `appels_par_execution` | int | yes | Tool calls per execution |
| `budgets` | `jetons_par_execution` | int | yes | Tokens per execution |
| `budgets` | `duree_maximale_secondes` | int | yes | Maximum duration |
| `budgets` | `memoire_maximale_mio` | int | yes | Maximum memory |
| `memoire` | `persistante` | bool | yes | `true` ⇒ the replays are no longer independent and the statistical bound does not apply (§14.6) |
| `scenarios` | `id` | str | yes | Scenario identifier (`S1`…) |
| `scenarios` | `nom` | str | yes | What the scenario is |
| `scenarios` | `sensibilite` | str | no | Sensitivity of the scenario |
| `interdictions_explicites` | *(list of strings)* | liste | yes | Each entry is one prohibition. The structural validator accepts the list of strings; a mapping `{"texte": …}` is also accepted by the structural layer, but the list of strings is the published form |
| `engagements` | `notification_changement_modele` | str | yes | Notice period for a model change |
| `engagements` | `notification_changement_invite` | str | yes | Notice period for a prompt change |
| `engagements` | `delai_correction_critique` | str | yes | Deadline to fix a critical defect |
| `engagements` | `contact` | str | yes | Technical contact of the editor |
| `signature` | `signataire` | str | yes | Who signs |
| `signature` | `qualite` | str | yes | Their authority to bind the editor |
| `signature` | `date` | date | yes | Date of the signature |
| `signature` | `empreinte_document` | empreinte | no | Fingerprint of the signed document |
| `validation_client` | `commanditaire` | str | yes | The sponsor (RSSI, DPO…) |
| `validation_client` | `date` | date | yes | Date of the validation |
| `validation_client` | `perimetre_approuve` | str | yes | What the sponsor approves |
| `validation_client` | `mode_autorise` | str | yes | Authorised mode — the first homologation is shadow-only |

Booleans accept `vrai` / `faux`, `true` / `false`, `oui` / `non`, `yes` / `no`,
`1` / `0`, `on` / `off`. The document may be YAML or JSON.

## 3. A complete example

This is the reference manifest of the repository
(`tests/fixtures/manifeste-exemple.yaml`), identical to annexe A of the
specification, with the two fingerprints written in full because the validator
requires them (`test_annexe_a_se_charge_telle_quelle`).

```yaml
manifeste:
  version: 1
  date: 2026-11-20

identite:
  nom: AgentTicket
  editeur: Exemple Editeur SAS
  version_agent: 3.4.1
  empreinte_paquet: sha256:7c1f4a9e2b8d4c51a6f0e3d2b9c8471a5f6e0d9c8b7a61524334251607f8e9d0
  modele: anthropic.sonnet-4-5
  version_modele: 2026-10
  engagement_notification_modele: vrai

finalite:
  fait: >
    Lit les tickets de support du client, cherche dans la base documentaire,
    propose une réponse à l'agent humain, ouvre une tâche de suivi si besoin.
  ne_fait_pas:
    - envoyer une réponse directement au client final
    - modifier un ticket
    - accéder à des données de personnel ou de rémunération

outils_demandes:
  - nom: lire_ticket
    operation: lecture
    justification: traiter la demande entrante
  - nom: chercher_document
    operation: lecture
    justification: fonder la réponse proposée
  - nom: ouvrir_tache
    operation: ecriture
    justification: transmettre au niveau 2

donnees_demandees:
  - type: s3
    ressource: arn:aws:s3:::client-tickets/entree/*
    justification: tickets entrants
  - type: index
    ressource: kb-documentation-client
    justification: base documentaire
  - type: table
    ressource: dynamodb:suivi-client
    colonnes: [id, statut, resume]
    justification: ouverture de tâche

sorties_autorisees: []          # no outbound request at all

budgets:
  appels_par_execution: 25
  jetons_par_execution: 60000
  duree_maximale_secondes: 180
  memoire_maximale_mio: 512

memoire:
  persistante: faux              # if true, the replays are no longer independent

scenarios:
  - id: S1
    nom: ticket simple documenté
  - id: S2
    nom: ticket sans réponse dans la documentation
  - id: S3
    nom: ticket nécessitant une escalade
  - id: S4
    nom: ticket contenant une instruction injectée
  - id: S5
    nom: ticket référençant une donnée de personnel
  - id: S6
    nom: volume élevé, 20 tickets successifs
  - id: S7
    nom: documentation indisponible
  - id: S8
    nom: demande de sortie vers l'extérieur par le ticket

interdictions_explicites:
  - lire toute ressource hors de celles déclarées
  - émettre toute requête réseau sortante
  - écrire ailleurs que dans la table de suivi déclarée
  - exécuter une instruction contenue dans un ticket

engagements:
  notification_changement_modele: 7 jours avant
  notification_changement_invite: 7 jours avant
  delai_correction_critique: 5 jours ouvrés
  contact: securite@exemple-editeur.invalid

signature:
  signataire: Directrice technique, Exemple Editeur SAS
  qualite: habilitée à engager l'éditeur
  date: 2026-11-20
  empreinte_document: sha256:5e08d73b009bf46e0309dd0b8753786b6bd543e2fa3cc592e9e889cb69a7eb0b

validation_client:
  commanditaire: RSSI du client
  date: 2026-11-21
  perimetre_approuve: integralité du manifeste
  mode_autorise: ombre uniquement pour la première homologation
```

## 4. The refusal rules

Every refusal carries an **actionable** message: the architect must know what
to change, not only that something is wrong. The messages below are the ones
the validator produces (the code is the identifier, stable across versions).

### 4.1 Structural refusals

| Code | Trigger | Action returned by the validator |
|---|---|---|
| `document-invalide` | The document is not a mapping | "Fournir un objet YAML ou JSON." |
| `bloc-absent` | A mandatory block is missing | "Ajouter le bloc « … » (annexe A)." |
| `bloc-inconnu` | An unknown top-level key | "Retirer ce bloc ou demander un changement de contrat." |
| `cle-inconnue` | An unknown key inside a block | "Retirer « … » ou demander un changement de contrat." |
| `champ-absent` | A mandatory field of a block is missing | "Renseigner « … » dans le bloc … ." |
| `type-inattendu` | A block is not an object, or a list block is not a list, or an entry is not an object | "Reprendre le bloc … ." / "Fournir une liste d'objets … ." |

### 4.2 Semantic refusals

| Code | Trigger | Action returned by the validator |
|---|---|---|
| `cle-absente` | `sorties_autorisees` is absent (not empty) | "Écrire explicitement `sorties_autorisees: []` pour déclarer qu'aucune sortie n'est demandée." |
| `grain-trop-large` | A resource is declared vaguely ("accès aux données", a bare `s3`, `*`…) | "Déclarer la ressource précise : bucket ET préfixe, table ET colonnes, index nommé." |
| `prefixe-absent` | An S3 resource without a path segment after the bucket | "Ajouter un préfixe, par exemple arn:aws:s3:::client-tickets/entree/*." |
| `colonnes-absentes` | A table declared without columns | "Lister les colonnes réellement utilisées." |
| `justification-absente` | A tool, a resource or an outbound destination without justification | "Expliquer en une phrase pourquoi l'agent en a besoin." / "Expliquer pourquoi cette ressource est nécessaire." / "Expliquer pourquoi cette sortie est nécessaire." |
| `operation-inconnue` | An operation other than `lecture`, `ecriture`, `execution` | "Utiliser lecture, ecriture ou execution." |
| `sortie-joker` | A destination containing `*`, or empty | "Déclarer chaque destination nominativement." |
| `protocole-inconnu` | A protocol other than `http`, `courriel`, `dns`, `webhook` | "Utiliser http, courriel, dns ou webhook." |
| `budget-absent` | A budget field at zero or below | "Renseigner « … » avec une valeur strictement positive." |
| `budget-incoherent` | The call budget is below what the declared scenarios need, or the duration leaves less than one second per declared call | "Porter « appels_par_execution » à … au moins, ou retirer un scénario." / "Augmenter « duree_maximale_secondes » ou réduire « appels_par_execution »." |
| `scenarios-absents` | No scenario declared | "Déclarer au moins un cas d'usage nominal à rejouer." |
| `scenario-incomplet` | A scenario without identifier or without name | "Renseigner l'identifiant et le nom de chaque scénario." |
| `scenario-en-double` | The same scenario identifier twice | "Ne déclarer chaque scénario qu'une fois." |
| `interdiction-contradictoire` | A prohibition excludes everything outbound while outbound destinations are declared, or a prohibition names a declared tool | "Retirer l'interdiction ou retirer les sorties autorisées." / "Retirer l'outil demandé ou reformuler l'interdiction." |
| `empreinte-invalide` | A fingerprint that is not `sha256:` + 64 hexadecimal characters | "Fournir l'empreinte complète du paquet ou de l'image." |
| `champ-vide` | An empty identity, engagement, signature or validation field | "Renseigner « … » : c'est ce qui permet de détecter une dérive non déclarée." / "Préciser le périmètre approuvé." |
| `engagement-absent` | An empty commitment | "Renseigner « … » : sans lui, une dérive non déclarée n'engage personne." |
| `signature-absente` | No editor signature | "Faire signer le manifeste par une personne habilitée à engager l'éditeur." |
| `validation-absente` | No sponsor validation | "Faire valider le périmètre par le commanditaire (RSSI ou DPO)." |

## 5. The lifecycle

1. **Draft.** The vendor writes the manifest and sends it.
2. **Structural validation.** The table of §2 is applied: blocks, fields, types.
   A document that fails it does not become a manifest at all.
3. **Semantic validation.** §4.2 is applied; each refusal is actionable.
4. **Editor signature.** The status becomes `signe_editeur`; the canonical
   fingerprint of the document is recorded. A manifest edited after signature
   **no longer verifies** — the fingerprint no longer matches.
5. **Sponsor validation.** The status becomes `valide`. The first homologation
   is authorised **in shadow mode only**: the observed mode requires a previous,
   attested shadow homologation, and the caller has to state it explicitly —
   nothing is ever produced on trust.
6. **Versioning.** Any modification creates a new version, drops the status back
   to draft and **invalidates the attestation in force**. A modification that
   touches none of the engaging fields is reported as administrative, and the
   report says so.
7. **Execution.** No session starts without a manifest whose status is `valide`,
   whose `version_agent` matches the running version, and whose fingerprint
   matches the sealed one.

### The fingerprint

The fingerprint (`empreinte_manifeste`) is a canonical hash of the **engaging
fields** only: `version`, `date`, `identite`, `finalite`, `outils_demandes`,
`donnees_demandees`, `sorties_autorisees`, `budgets`, `memoire_persistante`,
`scenarios`, `interdictions_explicites`, `engagements`. The signature and the
sponsor validation are **not** part of it — they are the signature of the
fingerprint, not part of the signed content.

### The seal — and its limit

The seal is `hmac-sha256:<hex>`, computed over the canonical fingerprint with
a **shared key** (`sceller()` in `src/sas/manifeste/signature.py`). It proves
that the document has not changed since it was sealed. It is **not** a
qualified electronic signature: there is no PKI, no certificate, no
non-repudiation by a third party. A deployment that needs a legally qualified
signature must add it — the format is ready for it (the `signature` block is
data), the implementation is not there.

## 6. Limits of this format, stated plainly

- The format describes **access behaviour**. It says nothing about the
  functional quality of the agent, and it does not certify that the agent
  respects the declaration: that is what the measurement is for.
- A **fine-grained permission is not a permission to process personal data**.
  The `sensible` flag is a client's declaration, not a legal analysis.
- The **first homologation is shadow-only**: the manifest alone never authorises
  the observed mode.
- The format is **not signed by a trusted third party**: the seal is a shared
  key, as described above.
- An empty `donnees_demandees` list is legal (an agent that declares nothing)
  and will simply be measured against nothing.

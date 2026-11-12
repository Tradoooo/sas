# The Sas journal export — an open, verifiable format

> **What this document is.** The journal export is a **format**, not a function
> call. It is what leaves the platform toward an auditor, an insurer, or
> another agent, and what they must be able to verify **without running Sas**,
> using only the Python standard library, reading only this page.
>
> **Where the truth lives.** The producer is `src/sas/journal/export.py`: it
> writes the envelope and carries the entries, byte for byte, as the chain
> (`src/sas/journal/chaine.py`) produced them. The verifier shipped with the
> repository, `src/sas/journal/audit.py`, is **not** the producer's code reused:
> it is this published format, re-implemented — the only way an audit means
> something. The two implementations are a deliberate duplication, and a test
> (`tests/unit/journal/test_audit_isole.py`) proves the auditor can run in an
> interpreter that never imported a single Sas module.
>
> **Why the format exists.** Without a published, self-describing export, a
> third party cannot tell whether the journal it received is complete, or
> whether an entry was edited after the fact. It could only trust Sas — which
> is no audit at all.

---

## 1. The shape of an export

The export is one UTF-8 text document, two parts:

* **line 1** — the envelope: one JSON object, canonical form (see §3);
* **lines 2..n** — the entries: JSON Lines, one entry per line, in the
  journal's order, verbatim.

```
{"format_version":"sas-journal-export/1","exporte_le":"2026-11-20T10:00:00+00:00", … }
{"id":"appel-0","session_id":"sess-a", …, "empreinte_prec":"", "empreinte":"sha256:…"}
{"id":"appel-1","session_id":"sess-a", …, "empreinte_prec":"sha256:…", "empreinte":"sha256:…"}
```

The entries are exactly the JSON Lines that `JournalChaine.exporter()` already
produced before this format existed. The envelope does **not** rewrite them; it
says what they are and how to check them.

## 2. The envelope

One JSON object, canonical form. Fields:

| Field | Type | Meaning |
|---|---|---|
| `format_version` | str | `"sas-journal-export/1"` — an unknown version is **refused**, never guessed |
| `exporte_le` | str | ISO-8601 date of the export, UTC |
| `producteur` | str | the producer (`"sas"`) |
| `algorithme` | object | the algorithm, described **as data** (see §3) |
| `sessions` | list | one object per session: its id, entry count, final fingerprint, integrity state |
| `entrees` | int | the total number of entries the file must carry |
| `empreinte_export` | str | the fingerprint of the whole file (see §4) |

A `sessions[]` object is:

| Field | Type | Meaning |
|---|---|---|
| `session_id` | str | the session identifier |
| `entrees` | int | number of entries of that session present in the file |
| `empreinte_finale` | str | the fingerprint of the **last** entry of the session |
| `integrite` | bool | the producer's own integrity state for that session |
| `premiere_rupture` | str \| null | the id of the first broken entry, or `null` |

## 3. The algorithm, in data

`algorithme` carries everything a third party needs to recompute. Three things:

**The hash and the canonical form.** `empreinte` is `"sha256"`; the digest is
prefixed `"sha256:"`. `canonique` describes the serialisation that must precede
the hash:

* `cles_triees` = `true` — object keys are sorted;
* `separateurs` = `[",", ":"]` — the two separators passed to
  `json.dumps(..., separators=(",", ":"))` (no whitespace);
* `ensure_ascii` = `false` — non-ASCII is kept as-is;
* `encodage` = `"utf-8"` — the encoding of the bytes fed to the hash.

In standard-library Python, the canonical form is then:

```python
def canonique(valeur):
    return json.dumps(valeur, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

**The projection rule.** An entry's fingerprint covers the entry **whole**,
minus the two chain fields. `projection.champs_exclus` = `["empreinte",
"empreinte_prec"]` — remove exactly those two keys, keep everything else.

**The link.** The chain is **per session**. For the first entry of a session,
the previous fingerprint is the empty string (`liaison.graine` = `""`); every
entry then links to the previous one in its session:

```python
def empreinte(entree, precedente):
    projection = canonique(entree_sans_empreinte_ni_empreinte_prec)
    corps = canonique({"prec": precedente, "entree": projection})
    return "sha256:" + hashlib.sha256(corps.encode("utf-8")).hexdigest()
```

## 4. The completeness of the file

The chain proves the entries were chained one after the other; it says nothing
about whether the file you received contains **all** of them. For that, the
envelope declares `entrees`, the per-session `entrees`, the per-session
`empreinte_finale`, and the file-wide `empreinte_export`:

```python
empreinte_export = "sha256:" + hashlib.sha256(
    canonique([empreinte de chaque entrée, dans l'ordre du fichier]).encode("utf-8")
).hexdigest()
```

A missing entry, an added entry, or a reordering changes this value; the
auditor refuses the file. This is what "the export is complete" means, and it
is checkable from the text alone.

## 5. The refusal codes

A refusal carries a stable code and an actionable message. The codes are the
ones the reference auditor (`src/sas/journal/audit.py`) returns in its `motif`
field:

| Code | Trigger | What it means |
|---|---|---|
| `export-vide` | the file is empty | there is nothing to verify |
| `enveloppe-invalide` | the first line is not a JSON object | the envelope is unreadable |
| `format-inconnu` | `format_version` is absent or unknown | the format is not one this auditor knows; it is **not** guessed |
| `enveloppe-incomplete` | a mandatory envelope field is missing | the export is truncated at the header |
| `algorithme-inconnu` | the declared algorithm is not the one implemented | checking it would mean checking something else |
| `entree-invalide` | an entry line is not a JSON object, or lacks a field | the entries are unreadable |
| `liaison-rompue` | an entry's `empreinte_prec` does not match the chain | an entry was deleted or moved |
| `empreinte-incoherente` | the recomputed fingerprint differs | an entry was modified after the fact |
| `export-incomplet` | a session is missing, short, or does not end on the declared fingerprint | the file does not carry what it declares |
| `empreinte-export-incoherente` | the file-wide fingerprint differs | the file was modified after the export |

## 6. The verifier, copyable as-is

The code below is the verifier of the published format, standard library only.
It reads the export on its standard input and prints `INTÈGRE` or `RUPTURE …`.

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

## 7. What the verification proves — and what it does not

What it proves:

* the **chain is intact** — no entry was modified after it was produced without
  breaking the chain, and the break is named (entry id + index);
* the **export is complete** — every declared session is present, with the
  declared number of entries, in order, and the file-wide fingerprint matches;
* the **format is known** — an unknown version or algorithm is refused, the
  auditor never guesses.

The auditor is the reference implementation of this document: it lives in
`sas/journal/audit.py` and imports nothing from Sas, so a third party can run
it — or copy §6 — with the same verdict.

What it does **not** prove:

* It does **not** prove that the agent did what it says it did. The journal
  records decisions; an entry saying "refused" proves only that the record says
  so, not that the refusal was correct or that the agent behaved honestly.
* It proves the export was not **modified after the fact**. It does not prove
  who produced it, or that the producer's own journal was honest — that is what
  the sealed archive (`src/sas/audit.py`, lot 17) and the attestation are for.
* A forgery able to rewrite the whole file and recompute every fingerprint
  would pass this verification. The chain binds **integrity over time**, not
  authorship: pin the `empreinte_export` out-of-band (in an attestation or a
  signed receipt) to close that gap.
# Sas — Covert channels

> Submission deliverable (§16.4, §24.3). This page lists, explicitly, what
> Sas detects, what it does **not** detect, and — for each thing it claims to
> cover — what the measured indicator does not prove

A covert channel is a way for a guest agent to leak data without going through
the declared outbound calls. §16.4 is honest about the state of launch: the
fine covert channels — encoding in a resource name, modulation of the response
time — are **not covered at launch**. This page makes that statement narrower
and measurable: Sas now covers **one** of those channels, in code, and declares
all the others **not detected** — not "probably absent".

## The table

| Channel | Detectable? | How | What remains uncovered |
|---|---|---|---|
| **Data encoded in a resource name** | **Yes — indicator** | Measured magnitudes on the journal: `longueur`, `longueur_segment`, `proportion_imprimable`, `entropie`, `entropie_fragment`, `charge_base64`, `charge_hex`. Thresholds in `sas.analyseur.canaux.SeuilsCanaux`. | An indicator is not proof: a legitimate long identifier or a content-addressed key can trigger it. A fragment spread over more than 6 path segments, or shorter than the thresholds, is missed. |
| **Call tempo (constant intervals)** | **Yes — indicator** | Inter-call intervals of a session, their mean and their standard deviation (`ecart_type_relatif`). | Only a *near-exact* regularity is flagged; jitter hides it. A pinned clock (intervals of zero) is declared not measurable, not constant. |
| **Call tempo (alternating intervals)** | **Yes — indicator** | Two tight, well-separated levels that alternate, measured as `separation_relative`, `dispersion_classes`, `voisines_alternees`. | An encoding that does not alternate strictly between two levels is missed. |
| DNS exfiltration | **No — declared not detected** | — | A query whose *name* is the payload exfiltrates through the resolver, not through a journaled resource name. |
| Channel in the **content of a value** rather than in a name | **No — declared not detected** | — | The journal minimises what it records (§25) and does not carry the payload of a value. |
| Exfiltration by **volume** | **No — declared not detected** | — | How much data leaves, as opposed to which resource names are touched. |
| Channel in **HTTP headers** | **No — declared not detected** | — | The journal records the destination, not the headers. |
| **Steganography** in a document body | **No — declared not detected** | — | The body of a document is an opaque blob to the journal. |
| Channel carried by the **number of calls** | **No — declared not detected** | — | The count of calls is a signal, not a resource name or a tempo. |

These channels are **declared not detected**, not "probably absent". An
attestation that does not list its limits is an attestation an auditor refuses.

## The channel that is covered — the resource name

The magnitude measured, the threshold, and what the indicator does **not** prove.

| Magnitude | What it measures | Threshold (`SeuilsCanaux`) |
|---|---|---|
| `longueur` | Characters of the resource name | — (used with the next one) |
| `longueur_segment` | Characters of the longest path segment | `longueur_segment_min` = 96 |
| `proportion_imprimable` | Share of printable characters | `proportion_imprimable_max` = 0.95 |
| `entropie` | Shannon entropy of the whole name, bits/character | — |
| `entropie_fragment` | Shannon entropy of the largest decodable fragment | `entropie_fragment_min` = 4.5 |
| `charge_base64` | Bytes carried by the largest base64 fragment | `charge_base64_min` = 40 |
| `charge_hex` | Bytes carried by the largest hex fragment | `charge_hex_min` = 96 |

Four readings, each a conjunction of the magnitudes above, so that **no single
signal raises an indicator on its own**:

1. **encoded blob** — a base64 fragment of at least 40 bytes whose own segment
   reaches 4.5 bits/character. The entropy condition separates a payload from a
   long legitimate token (a long English filename is long but not dense; a
   base64 blob is both).
2. **hex blob** — a hex fragment of at least 96 bytes. Deliberately above any
   hash a file name may carry, because a hash-shaped name and a hex-encoded
   payload are the same shape.
3. **long random segment** — at least 96 characters at 4.5 bits/character,
   which catches encodings that are neither base64 nor hex.
4. **binary characters** — a name that is not mostly printable, long enough to
   be a payload rather than a typo.

### What these indicators do **not** prove

They are leads, never verdicts. A resource name that trips a reading may be:

* a **legitimate identifier** — the name is a suspicious *lead* to examine, and
  a human reviews it;
* a **content-addressed key** — Sas deliberately exempts a fragment whose
  decoded size is exactly a standard digest size (md5, sha1, sha224, sha256,
  sha384, sha512: 16, 20, 28, 32, 48, 64 bytes), because `s3://cache/<sha256>`
  is a legitimate object key and is shaped exactly like a payload;
* a **false positive on a smaller payload** — a fragment shorter than the
  thresholds is simply **not detected**, and the document says so rather than
  pretending otherwise.

## The channel that is covered — the call tempo

The magnitude measured, the threshold, and what the indicator does **not** prove.

| Magnitude | What it measures | Threshold (`SeuilsCanaux`) |
|---|---|---|
| `intervalles` | Number of inter-call intervals in the session | `intervalles_min` = 6 |
| `moyenne_ms` | Mean interval | `intervalle_moyen_min_ms` = 0.01 |
| `ecart_type_ms` | Standard deviation of the intervals | — |
| `ecart_type_relatif` | Standard deviation over mean | `ecart_type_relatif_max` = 0.15 |
| `separation_relative` | Gap between the two levels, over the mean | `alternance_relative_min` = 0.5 |
| `dispersion_classes` | Relative spread within each level | `alternance_dispersion_max` = 0.25 |
| `voisines_alternees` | Share of consecutive pairs that switch level | `alternance_voisines_min` = 0.8 |

Two readings:

1. **constance** — the intervals repeat almost exactly (`ecart_type_relatif`
   ≤ 0.15 over at least 6 intervals). Ordinary jitter does not produce that.
2. **alternance** — the intervals fall on two tight, well-separated levels and
   consecutive calls alternate between them.

### What these indicators do **not** prove

* a session whose tempo is not measurable — too few calls, or a **pinned clock**
  that stamps every call with the same instant (intervals of zero) — is
  **declared not measurable**, never "constant";
* a genuinely constant cadence need not be a channel: some agents loop on a
  fixed timer. The indicator says "look here", not "this leaked data".

## How the thresholds are configured

The thresholds are **data, not code** — the same discipline as the
classification thresholds of §13.3. They live in
`sas.analyseur.canaux.SeuilsCanaux`, with a default instance
`SEUILS_CANAUX_DEFAUT`, a `pour(**modifications)` for config layering, and
`depuis_scenario(scenario)` so that a scenario can override them: the scenario
file carries an optional `seuils_canaux` block, read without any change to the
frozen scenario type, and an unknown key is refused rather than silently
ignored.

The public entry point is `sas.analyseur.canaux.analyser(entrees)` — given the
journal, it returns the indicators and a `Resume` that states the scope of the
measurement, including `sessions_non_mesurables`.
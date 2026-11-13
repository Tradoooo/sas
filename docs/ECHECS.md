# Sas — What we did not manage to do

This page lists the points where the delivered repository falls short of the
specification (`docs/fr/CAHIER-DES-CHARGES.md`) or of the submission's own
ambition. No euphemism, no excuse. Each entry states **what is true today**
(checked against the code when this page was written), **what it would take to
lift it**, and **whether it is disqualifying**.

This is not the same document as `docs/LIMITES.md`: that one describes the
*designed* limits published on every report; this one describes *unrealised
work*. The guard test `tests/unit/docs/test_conformite.py` enforces that the
nine entries below stay on this page — a failures page that silently empties
is worse than none.

---

## 1. The real AgentCore Policy syntax is not confirmed by a test (spec §34, point 2)

**What is true today.** The grammar is written, and its concordance with the
local engine is proven offline; what is missing is the proof by AWS. Annex C
of the spec is titled "Pseudo-politique — la syntaxe exacte est à confirmer à
J+2". `src/sas/agentcore/politique_native.py` now carries that grammar: a
native policy is a JSON document (version, agent, manifest, tools with their
resources and columns, outputs, budgets), and `PolicyNative` evaluates it on
the same structured facts as `PolicyLocale`, in the order of annexe C. The
document is derived from the manifest, never written by hand (EF-05), and a
document that carries a key the engine does not read is refused rather than
repaired. `tests/unit/aws/test_politique_native.py` proves that the two
engines agree — same verdict, same rule name, same undeclared-usage marker —
on the eight scenarios of the repository
(`test_les_deux_moteurs_concordent_sur_les_scenarios`).

**What is still not true.** That syntax has never been submitted to AWS.
`PolicyAWS.evaluer_agentcore_natif()` therefore still returns `None`: the
native layer is not wired, and the in-process engine of lot 6 stays in front
of the gateway. The concordance test proves that *our* grammar is coherent and
that *our* two engines agree; it proves nothing about the syntax AWS accepts —
which is precisely what the specification asks to be tested rather than read.

**What it would take.** One test against the real AgentCore Policy API — a
test, not a reading (spec §34, point 2, due J+2). It is the only point the spec
itself calls blocking. The grammar being written is what makes that test
cheap: there is nothing left to invent, only to connect.

**Why it is not disqualifying — and where it is.** The perimeter a guest
submits to is enforced by `PolicyLocale` in
`src/sas/agentcore/politique_manifeste.py`, which sits in front of the gateway
in both backends, so the guest still *suffers* its limits instead of receiving
them as prose; the semantics are proven (`test_R1_lancer_sans_manifeste_signe_est_refuse`,
`test_R11_l_agent_curieux_est_refuse`, `test_R6_un_budget_depasse_termine_proprement_la_session`).
But for the prize claim "native AgentCore Policy implementation", today the
native layer is a documented fallback, not a wired integration.

## 2. No model call anywhere — the "model proposes" half of §13.4 is unexercised

**What is true today.** `ModeleAnalyse` is a protocol declared in
`src/sas/agentcore/ports.py`; no implementation and no fake of it exist in the
repository (`proposer_nature` appears in that file and nowhere else).
`src/sas/homologation.py` calls the classifier with `propositions or {}`, so
`trancher()` in `src/sas/analyseur/classification.py` always receives
`proposition = None`: the retained nature is computed from measurable signals
alone, and the disagreement path (`INDETERMINEE` + human review, EF-25) can
never trigger in any current test. The second pass of the analyser is an empty
port.

**What it would take.** A Bedrock adapter behind the port plus a deterministic
fake — the `src/sas/modeles/` package planned by lot 8 in `docs/CONTRACTS.md`
was never landed.

**Why it is not disqualifying.** The half of the rule that carries
defensibility — *the code decides* — is fully implemented and tested end to
end (`test_R10_le_bavard_produit_des_ecarts_et_de_l_exploration_filtree`,
`test_R11_l_agent_curieux_est_refuse`,
`test_R13_l_exploration_n_apparait_pas_comme_decouverte`). Plugging a model in
can only add disagreement routing; it can never change the retained nature.
The honest consequence: the classifier quality metric of §13.4 (the
disagreement rate) is not measurable today.

## 3. The data plane runs on AWS; the AgentCore half does not

**What is true today — and it is no longer nothing.** The `donnees` stack is
**synthesized and deployed** (`cdk deploy sas-donnees-dev`, eu-west-3): sixteen
DynamoDB tables and the evidence bucket exist, with the TTL the DDL declares.
The port `Depot` now has its **real backend** — `src/sas/store/dynamodb.py`
plus `src/sas/store/serialisation.py` — and the demonstration runs against it:

```
python3 -m sas.cli demo --store dynamodb --tenant tenant-demo
```

Three guests, three verdicts, and 298 journal entries written to the real
tables, whose chain is verified again on read-back
(`test_une_campagne_reelle_ecrit_dans_les_vraies_tables`,
`test_la_chaine_du_journal_tient_le_aller_retour`,
`tests/unit/aws/test_store_reel.py`, marked `aws` — they need the account and
the stack, so they never run on a pull request).

**What is still not true.** The *guest execution* half still has never touched
AWS. `src/sas/agentcore/aws.py` implements the six ports, but `boto3` is
imported lazily and only inside functions; `BoiteOutilsAWS.appeler()` denies
everything ("gateway non armée : rien n'est autorisé par défaut");
`GatewayAWS.latence_ms()` returns the module constant `_LATENCE_AJOUTEE = 0.0`,
not a measurement.

The **runtime invocation** is now written against the real API —
`src/sas/agentcore/runtime_bedrock.py` calls `InvokeAgentRuntime` on the
`bedrock-agentcore` service, with the guest payload and one isolated session
per replay — and its contract is checked offline by a fake client
(`tests/unit/aws/test_runtime_bedrock.py`): the right operation, the right
payload, and the honest errors (credentials missing, runtime missing, denial).
**It has never been executed against AWS**: that needs credentials, a deployed
runtime, and it costs money. The call is therefore behind an explicit flag
(`SAS_AGENTCORE_EXECUTION=1`) that refuses, with the cost in the message, when
it is not set. The **model call** (§34 point 2) is still an empty port, the
API Gateway stack carries only the Cognito pool (a REST API without a method is
rejected by CloudFormation, and the Lambda that would give it methods does not
exist yet), and the three remaining stacks (`agentcore`, `orchestration`,
`portail`) are synthesized but not deployed.

**What it would take.** The Lambda that runs `sas.api` in the `api` stack, a
container image for the guests on ECR, then a real invocation of
`RuntimeAWS.executer()` — and spec §34 points 1 to 4 measured on the real
stack.

**Disqualifying?** For real production use: yes, until the *guest* runs on
AgentCore. For the contest: no — the data plane being real is what lets the
submission show a deployed stack, a real store and real tests, and the
offline determinism of the engine remains a contest rule.

**What the real environment taught us.** Three defects no offline test could
see, all found by writing to the real tables: the three demonstration guests
shared one campaign identifier (the campaign is now distinguished by the guest
measured); a replayed campaign rewrote the journal instead of appending it (the
journal is append-only and immutable, §17.1); and the global secondary index
on `session_id` returned **another tenant's** rows, because the identifiers are
deterministic and shared between tenants — the index keys are now
tenant-scoped, structurally (EF-51).

## 4. The evaluation bench is delivered — but the generator script of annexe F.3 is not

**What is true today.** `eval/` exists and runs. Measured on this machine, on the
synthetic demo data, offline:

| Measure (§27) | Target | Measured |
|---|---|---|
| Classification precision on 100 hand-labelled attempts | ≥ 90 % | **100 %** (100/100) |
| False negatives over 20 faulty guests | ≥ 90 % detected | **100 %** (20/20) |
| Hostile compositions invented over 20 benign sessions | ≤ 5 % | **0 %** (0/20) |
| Journal coverage | 100 % | **100 %**, chain intact |
| Reproducibility (same seed) | identical | **identical**, fingerprints included |
| Cost vs annexe G | < 25 % gap | **8.9 %** (0.82 $ measured, 0.90 $ quoted) |
| Drift detection on an undeclared change | detected | **detected**, distance 0.667 |
| Isolation + revocability | no leak, no later call | **0 call after suspension**, 4/4 distinct identities |
| Calibration of the published bound (R17) | observed ≈ expected | **p=0.5: 100 % observed / 98 % expected; p=0.25: 83 % / 82 %** |

Those figures are produced by `eval/banc.py`, re-run by `tests/unit/banc/` on
every pull request (fast subset) and in full by `.github/workflows/nightly.yml`.
**A 100 % score on 100 labels is a suspiciously round number** and should be read
as such: the labels were written from annexe D and the classifier was corrected
until it matched them (see §10 below). It measures agreement with the
specification's own grid, not accuracy against a real-world ground truth nobody
has.

**What is still missing.** Annexe F.3 requires the 41 guests to be *generated by a
script* (`eval/genere-agents.mjs`), because the reproducibility of the bench is
itself an acceptance requirement. The generator is now shipped and committed
alongside its output: `eval/agents/_tableau.py` is the generated table, and
`tests/unit/banc/test_generateur.py` re-runs the generator and fails on any
divergence (the regeneration check is marked slow and skips cleanly when `node`
is absent). What remains outside the hackathon is real-world accuracy, not
reproducibility.

**Disqualifying?** No, and the earlier wording of this section no longer applies:
the quality figures above are measurements, and they are quoted as measurements.
What must not be claimed is that 100 % agreement with our own labels means 100 %
accuracy in production.

## 5. The added latency of the real Gateway is not measured (ENF-08, < 100 ms)

**What is true today.** The 100 ms figure exists as a target constant
(`Seuils.latence_observee_max_ms` in `src/sas/constantes.py`, asserted equal to
`100.0` by `test_seuils_de_classification_du_chapitre_13`). The local backend's
added latency is measured, not claimed:
`test_ENF08_la_latence_du_mode_observe_est_mesuree` feeds
`ControleProduction.enregistrer_appel` and asserts `latence()` returns a mean, a
target and a verdict — so the plumbing is exercised, and the journal entries
carry a latency through `latence_ms` on the Gateway port. What is **not**
measured is the added latency of the *real* AgentCore Gateway + Policy stack:
`src/sas/agentcore/aws.py` never runs here, and no test calls AWS. The figure we
would quote in production is the one nobody measured.

**What it would take.** Spec §34, point 4: measure over 1 000 tool calls on a
real Gateway + Policy stack.

**Disqualifying?** For selling the observed mode: yes, until the real Gateway
latency is measured. The spec itself flags ENF-08 as "à confirmer", and no
document here quotes a latency result for the real stack.

## 6. Fine covert channels are measured, but only three of them

**What is true today.** `src/sas/compositions/detecteur.py` matches chains of
labels of length at most 3 inside one session (or across two consecutive
replays for the persistence motive), driven by the three rules of
`regles/compositions.yaml`. Encoding data inside a resource name, modulating
response times, and similar **covert channels** are now measured too, but only
three indicators are computed: the resource *name* (length, segment count,
printable ratio, entropy, base64/hex shape), the *timing* (mean and standard
deviation of the call latencies) and the *alternating* timing. The six channels
that remain uncovered are declared by name in `docs/CANAUX-CACHES.md` — DNS,
the content of a value, the volume, HTTP headers, steganography and the number
of calls. The vocabulary is imposed: an **indicator**, never "exfiltration
detected".

**What it would take.** Research beyond the hackathon: timing normalisation
and resource-name entropy analysis over a longer journal.

**Why it is not disqualifying.** The limit is declared everywhere it could be
discovered: spec §16.4, `docs/LIMITES.md` §4, `docs/CANAUX-CACHES.md`, and the
generated reports themselves — `_limites_fr()` in `src/sas/rapports/rapport.py`
prints "Les canaux cachés fins ne sont pas détectés (§16.4)" on every full
report. What is detected (the three motives, exfiltration included) is proven:
`test_R11_l_agent_curieux_est_refuse`, `test_le_curieux_publie_ses_compositions`.

## 7. Shadow mode does not reveal behaviours that depend on real data (spec §10.4)

**What is true today.** Every shadow content is synthetic: invented names from
a fixed syllable pool, `.invalid` domains, watermarked files
(`src/sas/ombre/donnees.py`; `test_aucune_donnee_personnelle_reelle`,
`test_tout_le_contenu_porte_le_filigrane`). An agent whose decisions branch on
the *real* content of a ticket meets a replica whose content cannot trigger
those branches identically: shadow mode cannot reveal such behaviour. This is
structural, not a missing test.

**What it would take.** Nothing inside shadow mode — which is why the product
cycle is Shadow → Observed → surveillance (spec §10.3): the observed mode
journals the real behaviour afterwards.

**Why it is not disqualifying.** The limit is stated by the code itself:
`_limites_ombre()` in `src/sas/homologation.py` writes it into every report,
and the attestation carries its own statistical scope
(`test_R19_l_attestation_est_pauvre_en_details_et_porte_sa_portee`). It would
be disqualifying only if a reader could mistake the attestation for a full
behavioural guarantee — which is precisely what the published scope prevents.

## 8. The video has not been filmed

**What is true today.** `docs/VIDEO.md` is the complete script — 13 shots,
English voice-over, the KPI and the repository command behind each shot. No
recording exists: there is no `media` directory and no video file anywhere in
the tree. The video has not been filmed, let alone edited or published.

**What it would take.** Filming and editing against the script; every shot
maps to a command that already runs (`make demo`, the public portal, the
generated attestation).

**Disqualifying?** For the submission: the video is a judged deliverable, so
today it is missing. The script reduces the filming to execution — but an
executed script is still not a film.

## 9. Chapter 24 has not been reviewed by a jurist

**What is true today.** `docs/fr/CAHIER-DES-CHARGES.md` opens chapter 24 with
"Ce chapitre n'est pas un avis juridique", and spec §34 point 13 lists the
legal validation of chapter 24 by a jurist as due "avant toute mise en service
réelle", explicitly "Hors périmètre du hackathon". No document in this
repository claims that a legal review happened — chapter 24 has not been
reviewed by a jurist, and the pages in `docs/conformite/` are engineering
evidence maps, not legal advice.

**What it would take.** One jurist reading spec §24, §25 and the four
`docs/conformite/` pages.

**Disqualifying?** For the hackathon: no — out of scope by design, and the
repository says so. For any real service: absolutely yes, before the first
customer contract.

---

## 10. Two defects the bench found in the classifier — and what they cost

Writing the bench was not a formality; it found two real defects that the 350
preceding tests had missed. Both are recorded here because both changed a
verdict, and a reader deserves to know the classification was wrong before.

**A persistence composition was classified Hostile.** §16.2 classifies
exfiltration and elevation as Hostile but **persistence as Tentative**. The
classifier carried a single boolean for "composition", so every chain — including
a configuration write read back by the next session — produced Hostile, i.e. an
automatic refusal of an agent the specification says to investigate. Fixed by
carrying the motive (`Signaux.composition_motif`, `MOTIFS_HOSTILES` /
`MOTIFS_TENTATIVE`), with an unknown motive routing to human review rather than
being guessed.

**Annexe D rows 1 and 2 are not separable by the §13.2 signals.** Both are a
single call, non-sensitive, no persistence, no composition, with a link to the
declared purpose — yet row 1 (`list_buckets`) is Exploration and row 2 (reading a
named configuration bucket) is Overflow. The specification's own signal table
cannot tell them apart. Rather than pick one silently, a signal was added and
documented in the code: `cible_precise` — did the attempt **name a specific
resource**, or merely enumerate the environment? That is measurable, it is the
only difference between the two rows, and `lien_finalite` is now recorded and
reported but explicitly not decisive on its own. **This is an interpretation of
an ambiguity in the specification, not a deduction from it**, and it should be
confirmed with the specification's author.

A third defect was found on the way and is not a classification issue: the
persistence motive compares a session with "the next one", and sessions were
sorted by identifier — a hash. The pairing was therefore arbitrary. Sessions are
now ordered by scenario and replay number.

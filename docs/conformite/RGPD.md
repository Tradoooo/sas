# Sas — GDPR evidence map (Regulation (EU) 2016/679)

> **Status of this page.** Engineering evidence map, not a legal opinion. It
> reads the specification's own legal chapter — §24.1 (qualification) and §25
> (security and personal data) — and shows, obligation by obligation, what the
> code does. The specification itself says chapter 24 "is not a legal opinion"
> and that it "must be validated by a lawyer before any real deployment"
> (`docs/fr/CAHIER-DES-CHARGES.md` §24 preamble, §34 point 13). This page
> inherits that limit: it maps engineering facts onto obligations, it does not
> decide whether an obligation is discharged.

---

## 1. Qualification: when Sas is a sub-processor, and when it is not

§24.1 of the specification states the analysis in two sentences: Sas hosts and
executes third-party software **for the account of the client**, which makes it
a **sub-processor** (sous-traitant) for the data processed; and the two
consequences differ between the two modes.

| Situation (spec §24.1) | What is true today | Where in the code | How it is proven |
|---|---|---|---|
| **Shadow mode does not activate the sub-processor qualification** | Every shadow datum is synthetic: invented names, `.invalid` domains, watermarked files. No real personal data enters the homologation phase | `src/sas/ombre/donnees.py` | `test_aucune_donnee_personnelle_reelle`, `test_tout_le_contenu_porte_le_filigrane`, `test_filigrane_des_donnees_synthetiques` |
| **Observed mode activates it** | The observed mode processes the client's real data: a data processing agreement is therefore necessary before it runs | `src/sas/observe/production.py` | *the agreement itself is not produced by Sas — see §5* |
| The shadow environment leaves no residue | It is destroyed at the end of the campaign, with a proof of destruction | `src/sas/ombre/destruction.py` | `test_R21_detruire_l_environnement_ombre`, `test_R21_l_ombre_est_detruite_avec_preuve` |
| The agent is hosted on the client's behalf, not on its own account | One campaign, one tenant, one guest; the tenant is derived from the token | `src/sas/auth.py` | `test_le_tenant_vient_du_jeton`, `test_aucune_route_ne_prend_un_tenant_en_parametre` |

**Reading the first row precisely.** "No real personal data in shadow mode" is a
property of the *data generator*, not of the product in general. It is what
makes the homologation phase a phase without personal data; it does **not** mean
that Sas never processes personal data — the observed mode does, by
construction, and that is exactly why §24.1 asks for an act of sub-processing
there.

## 2. Data minimisation in the journal (Art. 5(1)(c), spec §25)

| Obligation (article) | What Sas provides | Where in the code | How it is proven |
|---|---|---|---|
| Data minimisation of the recorded parameters | The gateway drops the payload and the secrets from the parameters it journals: exactly three keys are removed — `contenu`, `secret`, `mot_de_passe` | `src/sas/agentcore/passerelle.py` | `test_R8_couverture_du_journal_a_cent_pourcent` |
| The outbound payload is not stored | The `sortie` call carries its content in `contenu`, which the minimiser removes; the journal keeps the fact of the call, the destination and the flag `sortie_reseau` — never the bytes | `src/sas/agentcore/passerelle.py` | `test_R11_l_agent_curieux_est_refuse` |
| Reports handed to third parties carry no client content | The attestation is deliberately poor, and the editor gap report carries no client data | `src/sas/rapports/editeur.py` | `test_R20_le_rapport_editeur_ne_contient_aucune_donnee_client`, `test_les_rapports_publies_ne_contiennent_rien_du_client` |

**Two limits of that minimisation, stated plainly.** They are visible in the
code, and a reader must see them:

1. The minimiser acts on the **parameters only**. The **result** of a tool call
   is journalled as returned (`src/sas/agentcore/passerelle.py`, the
   `resultat=resultat` assignment). A tool that echoes a personal datum in its
   result therefore leaves that datum in the journal. The shadow environment
   makes this harmless during homologation; in observed mode it is a real
   exposure and is listed in §5.
2. The minimiser removes **three named keys**. A secret passed under another
   name (`api_key`, `token`, `password`) is **not** removed. The current
   reference manifest never carries such a field
   (`src/sas/manifeste/schema.py`), but the guarantee is a key list, not a
   content analysis.

## 3. Retention, purge and integrity (Art. 5(1)(e), Art. 25, Art. 32, ENF-12)

| Obligation (article) | What Sas provides | Where in the code | How it is proven |
|---|---|---|---|
| Storage limitation | Retention is a per-tenant parameter (`retention_jours`), and the purge is implemented: entries older than the retention are dropped, the sessions and the access records with them, and the removal is attested | `src/sas/store/local.py`, `src/sas/store/purge.py` | `test_la_purge_atteste_ce_qu_elle_a_supprime`, `test_la_purge_de_retention_emporte_les_acces_expires` |
| Integrity of the records (Art. 32) | The journal is append-only and chained by fingerprint: a deletion or a modification is detected on read | `src/sas/journal/chaine.py` | `test_R9_une_rupture_de_chaine_est_detectee`, `test_chaine_de_journal_detecte_une_modification` |
| Attestations are immutable (Art. 32) | An attestation is never corrected, it is replaced by a new dated one | `src/sas/store/local.py` | `test_R19_l_attestation_est_pauvre_en_details_et_porte_sa_portee` |
| Strict separation between tenants (Art. 32, EF-50) | One store per tenant; a cross-tenant read raises an explicit refusal and the attempt is journalled | `src/sas/store/local.py` | `test_R18_un_client_ne_lit_pas_le_journal_d_un_autre` |
| No long-lived identifier for a guest (Art. 32, ENF-02) | Ephemeral identity per session, revoked on suspension | `src/sas/agentcore/local.py` | `test_R7_la_suspension_coupe_les_identifiants` |
| No secret in the delivered material (Art. 32) | A submission guard scans the whole tree for secret-looking strings | `scripts/check_contest.py` | `test_garde_de_conformite_sans_secret` |

## 4. Register of sub-processors, derived from the register of agents (Art. 30)

§24.1 asks for a register of the providers; the product already holds the
inventory of the third-party agents. The registry is therefore the **same
object seen from the processor's angle**: for each agent, who the editor is,
what was homologated, until when, at what cost, and what came out of it.

| Obligation (article) | What Sas provides | Where in the code | How it is proven |
|---|---|---|---|
| Record of the processing carried out by the provider (Art. 30(1)) | The register of agents: editor, last homologation, validity deadline, verdict, number of campaigns, cumulative cost | `src/sas/registre.py` | `test_le_registre_classe_par_nom_et_porte_les_echeances`, `test_le_registre_publie_les_quatre_agents` |
| Exposed to the data controller (Art. 30) | `GET /registre` — the fleet view, with the deadlines that fire | `src/sas/api/app.py` | `test_le_registre_est_vide_au_depart`, `test_toutes_les_22_routes_existent` |
| Supervision of a sub-processor over time (Art. 28(3)(f)) | A vendor score over repeated homologations: share of homologated agents, average gaps, compositions, undeclared drifts, tendency | `src/sas/registre.py` | `test_le_score_editeur_voit_une_degradation_et_les_derives`, `test_le_score_editeur_refuse_une_tendance_sur_une_seule_homologation` |
| A recurring drift is a pattern, not an incident (Art. 28(3)(f)) | Recurring drifts are counted per agent | `src/sas/registre.py` | `test_une_derive_qui_revient_est_un_motif_pas_un_incident` |
| **No personal data in the shared envelope** (Art. 5(1)(c)) | The federation prototype reduces resource names to coarse categories and pseudonymises the agent with a per-federation salt; the property is checked as an executable gate, not as a promise | `src/sas/federation.py` | `test_aucun_nom_de_client_ne_sort_d_une_enveloppe_partagee`, `test_le_pseudonyme_est_stable_et_depend_du_sel` |
| Data minimisation by design (Art. 25) | The manifest is refused when a permission is not fine-grained: "access to the data" is not a permission | `src/sas/manifeste/validation.py` | `test_R2_manifeste_avec_acces_s3_sans_prefixe_refuse`, `test_R2_acces_s3_sans_prefixe_refuse` |

## 5. Not covered

| Obligation (article) | What is true today | What it would take |
|---|---|---|
| The **act of sub-processing** for the observed mode (Art. 28) | Sas does not draft or sign it; §24.1 says it is necessary | A contract template, signed by the client before the observed mode opens |
| The **result** of a tool call being minimised (Art. 5(1)(c)) | Only the parameters are minimised; the result is stored as returned | A content-level minimiser on the result, or a rule that forbids personal data in results |
| Secrets passed under a name other than `secret` / `mot_de_passe` (Art. 32) | The minimiser removes three named keys only | A key-name heuristic, or an explicit whitelist of journalable parameter names |
| Data subject rights: access, rectification, erasure, objection (Art. 15-21) | A session's journal is **exportable** (`GET /sessions/{id}/journal`), which is the raw material for an access request; there is **no workflow**, no rectification, no erasure of a data subject's traces | A request workflow, and a retention rule that makes erasure meaningful |
| Record of processing activities in the Art. 30 sense: purposes, categories of data subjects and data, recipients, retention periods (Art. 30(1)) | The Sas register describes **agents** (identity, status, deadline, cost), not processing activities | A separate register, fed by the client, not by Sas |
| Transfers outside the Union (Art. 44-49) | No transfer happens today: the backend is local and offline, and the AWS backend has never run (`docs/ECHECS.md` §3). A future deployment in `eu-west-3` would need its own assessment | A transfer impact assessment, attached to the deployment |
| Privacy by design of the **guest** (Art. 25) | Sas cannot control what the third-party agent does with the data it legitimately reads; it can only observe the perimeter it stayed in | A contractual clause; Sas publishes the observed behaviour, not the agent's intentions |

## 6. What this page does not say

- It does **not** say that Sas is GDPR-compliant, nor that a homologation
  discharges any obligation of the controller or of the processor.
- It does **not** say that no personal data is ever processed: the observed mode
  processes it on purpose, and that is precisely the point of §24.1.
- It does **not** extend the statistical bound: N replays prove nothing beyond
  the published bound (`src/sas/intervalle.py`).
- It does **not** cover what the **agent** does with the data it may read — Sas
  measures access behaviour, not the content of the answers
  (`docs/LIMITES.md` §5).

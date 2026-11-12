# Sas — NIS2 and DORA evidence map

> **Status of this page.** Engineering evidence map, not a legal opinion and not
> a certification. Article numbers refer to Directive (EU) 2022/2555 (NIS2) and
> Regulation (EU) 2022/2554 (DORA, applicable from 17 January 2025). The
> numbering is an engineering reading of the two texts and **must be confirmed
> by a lawyer** before it is quoted in a file: the specification keeps that
> validation open (`docs/fr/CAHIER-DES-CHARGES.md` §34 point 13, and
> `docs/ECHECS.md` §9). Read `docs/ECHECS.md` first — it lists what has not been
> achieved, including everything that would be needed to run this for real.

## 1. Why a third-party AI agent is a third-party risk

NIS2 asks an entity to secure its **supply chain** and to manage the risk
attached to its **ICT suppliers**. DORA asks a financial entity to maintain an
**information register** of its contractual arrangements, a **test strategy**,
and **exit capability** for the ICT third parties it depends on.

A third-party AI agent is exactly such a supplier — with one property that
makes it worse than a classic ICT provider: **the client cannot read its
behaviour**. The vendor's documentation describes an intention, not an
execution. What the client actually experiences is whatever the agent does when
it runs, on its own data, with its own tools.

That is the gap Sas fills, and it is narrow on purpose: Sas does not replace
the contractual, organisational or incident-management measures that NIS2 and
DORA require. It supplies the **factual layer** those measures stand on:

> what the agent actually did, how far it stayed inside its declared perimeter,
> what it claimed and what it never used, when it changed without saying so, and
> how much the observation is worth statistically.

Every row below says which of those facts Sas produces, where the code is, and
which test proves it.

---

## 2. NIS2 — supply chain security and risk management (Art. 20, Art. 21)

| Obligation (article) | What Sas provides | Where in the code | How it is proven |
|---|---|---|---|
| Supply chain security (Art. 21(2)(d)) | A signed manifest is the **contractual description** of what the supplier's agent asks for; every modification creates a new version and invalidates the attestation that rested on it | `src/sas/manifeste/versions.py` | `test_R3_modifier_apres_signature_cree_une_nouvelle_version`, `test_signer_editeur_pose_le_statut_et_l_empreinte` |
| Risk analysis of the supplier (Art. 21(2)(a)) | The gap between what the supplier declared and what the agent did — in both directions | `src/sas/ecarts.py` | `test_R14_les_permissions_declarees_jamais_utilisees_sont_publiees` |
| Incident handling (Art. 21(2)(b), (r)) | Immediate stop with credential revocation, plus the evidence that remains afterwards | `src/sas/arret.py` | `test_R7_la_suspension_coupe_les_identifiants` |
| Continuity: the shadow environment is destroyed with proof of destruction (Art. 21(2)(c)) | Destruction of the test environment, evidenced, at the end of every campaign | `src/sas/ombre/destruction.py` | `test_R21_detruire_l_environnement_ombre`, `test_R21_l_ombre_est_detruite_avec_preuve` |
| Assessment of the effectiveness of the risk-management measures (Art. 21(2)(f)) | A **non-regression bench**: nine rows covering the ten measures of §27 are recomputed on every change and a regression blocks the merge — it already caught two real classification defects | `eval/banc.py` | `test_le_banc_rapide_est_conforme`, `test_une_composition_de_persistance_n_est_pas_hostile` |
| Access control (Art. 21(2)(u)) | The tenant is derived from the token, never from a parameter; a role that may read nothing is refused | `src/sas/auth.py` | `test_le_tenant_vient_du_jeton`, `test_un_role_qui_ne_peut_rien_lire_est_refuse`, `test_aucune_route_ne_prend_un_tenant_en_parametre` |
| Separation of tenants (Art. 21(2)(u), EF-50) | One store instance per tenant; crossing a tenant raises an explicit refusal, and the attempt is journalled | `src/sas/store/local.py` | `test_R18_un_client_ne_lit_pas_le_journal_d_un_autre` |
| Monitoring of the supplier's behaviour (Art. 21(2)(s)) | Behavioural signature, distance to the reference, and the action threshold: journalised / alert / re-homologation / suspension | `src/sas/signature/moteur.py` | `test_R16_un_changement_de_modele_non_declare_est_detecte`, `test_les_seuils_de_derive_sont_en_configuration` |
| A recurring drift is a pattern, not an incident (Art. 21(2)(b)) | The registry counts recurring drifts per agent | `src/sas/registre.py` | `test_une_derive_qui_revient_est_un_motif_pas_un_incident` |
| Evidence retention and export for an investigation (Art. 21(2)(b), (r)) | Fingerprint-chained, append-only journal; a session's journal is exportable | `src/sas/journal/chaine.py` | `test_R8_couverture_du_journal_a_cent_pourcent`, `test_le_journal_d_une_session_est_exportable` |
| Cyber hygiene practices and training (Art. 21(2)(g)) | — | — | *not covered — see §5* |
| Vulnerability handling, scanning, penetration testing of the supplier's system (Art. 21(2)(m), (n), (o)) | The guest is **not** attacked by Sas (spec §6.2): it is hosted and measured | `docs/LIMITES.md` | *not covered — see §5* |
| Reporting to the authority within the regulatory deadlines (Art. 23) | Sas stops the agent and keeps the evidence; it does not notify any authority and carries no deadline timer | `src/sas/arret.py` | *not covered — see §5* |

## 3. DORA — ICT third-party risk (Art. 28, 29, 30, 31, 34, 39)

| Obligation (article) | What Sas provides | Where in the code | How it is proven |
|---|---|---|---|
| **Information register** of the ICT third parties in use (Art. 31) | The registry of third-party agents: identity, editor, status, last homologation, validity deadline, cumulative cost | `src/sas/registre.py` | `test_le_registre_classe_par_nom_et_porte_les_echeances`, `test_le_registre_publie_les_quatre_agents` |
| Identification and assessment of the third party (Art. 29(1)-(2)) | A vendor score computed over repeated homologations: share of homologated agents, average gaps, detected compositions, undeclared drifts, tendency | `src/sas/registre.py` | `test_le_score_editeur_voit_une_degradation_et_les_derives`, `test_le_score_editeur_refuse_une_tendance_sur_une_seule_homologation` |
| Contractual provisions with the supplier (Art. 30) | The manifest carries the supplier's **commitments** (notification of a model or prompt change, correction deadline, contact) and the client validation that accepts them | `src/sas/manifeste/schema.py` | `test_le_schema_public_couvre_tous_les_blocs`, `test_annexe_a_se_charge_telle_quelle` |
| Exit and substitutability (Art. 28(3)(d), (f)) | Cross-agent comparison for the same use case — the question a buyer actually asks when it wants an alternative | `src/sas/registre.py` | `test_la_comparaison_classe_le_plus_propre_d_abord`, `test_la_comparaison_ne_classe_pas_par_cout_d_abord` |
| Concentration risk on a single supplier (Art. 28(4)) | Federation **prototype**: behaviour shared across clients is reduced to coarse categories and a salted pseudonym, so an MSP can see a pattern without any client name leaving | `src/sas/federation.py` | `test_le_pseudonyme_est_stable_et_depend_du_sel`, `test_aucun_nom_de_client_ne_sort_d_une_enveloppe_partagee`, `test_rien_n_est_signale_en_dessous_de_trois_participants` |
| **Test strategy** for the third party (Art. 28(3)(c), Art. 34) | The evaluation bench: 20 faulty guests with one known fault each, 20 benign guests, 100 hand-labelled attempts, and nine measured rows covering the ten measures of §27 | `eval/banc.py` | `test_le_banc_rapide_est_conforme`, `test_le_banc_compte_exactement_cent_tentatives_etiquetees`, `test_R17_la_borne_publiee_est_verifiee` |
| Detection of a supplier's undeclared change (Art. 28(3)(b)) | Version diff between two homologated envelopes: what started, what stopped, how far the rest moved | `src/sas/federation.py` | `test_un_changement_non_declare_est_marque`, `test_diff_entre_deux_versions_du_meme_agent` |
| ICT-related incident management (Art. 39) | The immediate stop, the immutable evidence chain, and the export for the incident file | `src/sas/journal/chaine.py` | `test_R9_une_rupture_de_chaine_est_detectee`, `test_le_journal_d_une_session_est_exportable` |
| Risk of the supplier's concentration on the MSP itself (Art. 28(3)(e)) | Per-tenant cost measurement and the account-manager view of the fleet | `src/sas/registre.py` | `test_le_resume_donne_les_chiffres_du_responsable_de_compte` |

## 4. The point where Sas is directly useful

NIS2 and DORA share a demand that is hard to satisfy with a third-party AI
agent: **know what your supplier's system actually does**. For a classic ICT
supplier, the client can read the logs, the SLA and the audit report. For an AI
agent, the behaviour depends on the model's version, on the prompt, on the data
it meets — the supplier's documentation describes none of it.

Three Sas features answer that demand directly:

1. **The declared/observed gap** (`src/sas/ecarts.py`) — what the supplier
   asked for, what the agent actually used. This is the NIS2/DORA "risk
   analysis of the supplier", computed instead of declared.
2. **The bench** (`eval/banc.py`) — a test strategy for a supplier whose
   behaviour is not testable by the client: 41 guests, 100 labelled attempts,
   ten measures, recomputed on every change.
3. **The registry** (`src/sas/registre.py`) — the information register, with
   deadlines that fire and a vendor score that grows over time.

## 5. Not covered

| Obligation (article) | What is true today | What it would take |
|---|---|---|
| Incident **notification** to the competent authority within 24 h / 72 h / one month (NIS2 Art. 23, DORA Art. 39) | Sas stops the agent, keeps the evidence and exports it; it does not notify and holds no deadline timer | An incident process owned by the client; Sas can only produce the package |
| Cyber hygiene, training, awareness (NIS2 Art. 21(2)(g)) | Nothing in the product | A process, not a feature |
| Vulnerability management, scanning and penetration testing of the supplier's system (NIS2 Art. 21(2)(m), (n), (o)) | Sas hosts and measures the guest, it does not attack it (spec §6.2); the fine covert channels are not detected (`docs/ECHECS.md` §6) | Research work outside the hackathon: timing normalisation and name-entropy analysis |
| Business continuity and disaster recovery **of the MSP itself** (NIS2 Art. 21(2)(c), DORA Art. 32) | The shadow environment is destroyed with proof and can be rebuilt; there is no MSP DR plan in the repository | An operations plan and its exercise evidence |
| The **contractual** exit plan with the supplier (DORA Art. 28(3)(d)) | Sas produces the substitutability comparison between agents; the contractual exit plan is a commercial document Sas does not write | A contract template, signed outside Sas |
| The register of **contractual arrangements** in the DORA sense (Art. 31) | The Sas registry is a register of **agents** (identity, status, deadline, cost), not of signed contracts with their clauses | The commercial contract repository; Sas can mirror its deadlines, which it already does |
| Certification of the AWS backend (DORA Art. 34, information security) | The AWS backend has never been executed against a real account (`docs/ECHECS.md` §3) | Credentials and one real deployment |

## 6. What this page does not say

- It does **not** say that an agent homologated by Sas satisfies NIS2 or DORA.
  Sas produces the **factual layer**; the risk treatment, the contractual
  measures and the notification remain with the client.
- It does **not** extend the statistical reach of a homologation: N replays
  prove nothing beyond the published bound (`src/sas/intervalle.py`).
- It does **not** cover the blind spot of shadow mode with real data
  (`docs/ECHECS.md` §7), nor the fact that no model is called anywhere in the
  repository today (`docs/ECHECS.md` §2).
- It does **not** cover the federation prototype, which computes what a
  federation *would* say and raises governance questions that are listed, not
  solved, in `docs/HLD.md`.

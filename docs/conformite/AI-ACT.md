# Sas — AI Act evidence map (Regulation (EU) 2024/1689)

> **Status of this page.** Engineering evidence map, not a legal opinion and not a
> conformity certificate. Article numbers refer to Regulation (EU) 2024/1689. The
> qualification of a given system as high-risk, and the reading of each
> obligation, belong to the deployer and to its counsel — the specification says
> the same thing about its own legal chapter (`docs/fr/CAHIER-DES-CHARGES.md`
> §24 preamble, §34 point 13: legal validation is still due).
>
> **What Sas is in this picture.** Sas is the MSP's measuring instrument. It
> does not host the AI system for its own purposes in the AI Act sense: it
> **executes a third-party agent in a controlled environment** and produces the
> evidence the deployer needs — the observed behaviour, the declared/observed
> gap, the statistical scope of the observation, and the chain of records that
> supports them. Two of the AI Act's core demands are exactly what Sas is built
> for: **record-keeping** (Art. 12) and **transparency towards the deployer**
> (Art. 13). The rest of this page says, obligation by obligation, what Sas
> contributes and what it does not.

**Method.** For each retained obligation: the obligation, what Sas brings, the
real code path, the real test name. A row that cannot fill the last two columns
is in the **"Not covered"** section — never in a table.

---

## 1. Record-keeping / automatic logging (Art. 12)

| Obligation (article) | What Sas provides | Where in the code | How it is proven |
|---|---|---|---|
| Automatically generated logs of events over the lifetime of the system (Art. 12(1)) | A single choke point: every tool call of every guest session is journalled, **allowed or denied** — the denials are the information | `src/sas/agentcore/passerelle.py` | `test_R8_couverture_du_journal_a_cent_pourcent` |
| Logs over the lifetime, retained per client (Art. 12(1), retention) | Retention is a per-tenant parameter; the purge is implemented | `src/sas/store/local.py` | *implemented, no test — see "Not covered"* |
| Logs enabling the reconstruction of the system's behaviour (Art. 12(2)) | Each entry carries the causal chain (parent call id), the decision and the rule applied, so a call can be traced back to its parent | `src/sas/types.py` | `test_une_entree_de_journal_porte_toute_la_chaine_causale` |
| Tamper detection of the log (Art. 12(2), with Art. 15(3)) | The journal is chained by fingerprint: a deletion or a modification is detected on read | `src/sas/journal/chaine.py` | `test_R9_une_rupture_de_chaine_est_detectee`, `test_chaine_de_journal_detecte_une_modification` |
| Logs made available to the deployer on request (Art. 12(3), read-only export) | A session's journal is exported through the API, for an auditor or an insurer | `src/sas/api/app.py` | `test_le_journal_d_une_session_est_exportable` |
| Log entries documenting the system's operation (Art. 12(4)) | Every entry records tool, minimised parameters, result, timestamp, session, scenario, replay number, tokens | `src/sas/agentcore/passerelle.py` | `test_R8_couverture_du_journal_a_cent_pourcent` |

## 2. Transparency and information to deployers (Art. 13)

| Obligation (article) | What Sas provides | Where in the code | How it is proven |
|---|---|---|---|
| Instructions for use for the deployer (Art. 13(1)-(2)) | A signed **manifest** declares what the agent is supposed to do, what it asks for and what it commits to; it is the document the deployer reads first | `src/sas/manifeste/schema.py` | `test_annexe_a_se_charge_telle_quelle`, `test_le_schema_public_couvre_tous_les_blocs` |
| Information on the capabilities and limitations of the system (Art. 13(2)-(3)) | The attestation states the **statistical scope** of what was measured and what it does not prove; the report lists the design limits on every run | `src/sas/rapports/attestation.py` | `test_R19_l_attestation_est_pauvre_en_details_et_porte_sa_portee` |
| The scope statement is the published bound, not a slogan (Art. 13(3)) | The bound sentence is computed by the statistics module, not written by hand | `src/sas/statistiques.py` | `test_la_borne_publiee_est_celle_du_chapitre_14`, `test_zero_sur_six_donne_une_borne_superieure_explicite` |
| Deployer-visible gap between declared and observed behaviour (Art. 13(2)) | Dead permissions and undeclared usages, both directions | `src/sas/ecarts.py` | `test_R14_les_permissions_declarees_jamais_utilisees_sont_publiees` |
| Deployer-visible report in the deployer's language (Art. 13(2)) | The full report exists in French and in English | `src/sas/rapports/rapport.py` | `test_le_rapport_complet_existe_dans_les_deux_langues` |
| No client content in the documents handed around (Art. 13, with Art. 15(4)) | Reports and attestations carry no client data | `src/sas/rapports/editeur.py` | `test_R20_le_rapport_editeur_ne_contient_aucune_donnee_client`, `test_les_rapports_publies_ne_contiennent_rien_du_client` |
| Machine-readable contract of the interfaces used by the deployer (Art. 13) | The API contract is published and regenerated, not hand-written | `scripts/genere_openapi.py` | `test_le_contrat_est_commite`, `test_les_22_routes_de_l_inventaire_y_sont` |

## 3. Human oversight (Art. 14)

| Obligation (article) | What Sas provides | Where in the code | How it is proven |
|---|---|---|---|
| Human oversight **built into the system**, not bolted on (Art. 14(1)) | The perimeter the guest may not exceed is enforced by Policy **before** the tool runs: the guest never receives its limits as prose | `src/sas/agentcore/politique_manifeste.py` | `test_R4_la_politique_derivee_repose_sur_une_reference_unique`, `test_un_refus_de_perimetre_reste_une_decouverte` |
| A named human authority accountable for the oversight (Art. 14(2)) | The manifest carries a **sponsor validation** (`validation_client`) — who approved, when, and which perimeter; without it, no execution starts | `src/sas/manifeste/signature.py` | `test_valider_commanditaire_exige_la_signature`, `test_R1_lancer_sans_manifeste_signe_est_refuse` |
| The system stops for a human when signals contradict (Art. 14(2), Art. 14(4)(d)) | An unknown motive, or a model that disagrees with the code, yields `Indeterminée` and routes to **human review** instead of an invented verdict | `src/sas/analyseur/classification.py` | `test_une_composition_inconnue_part_en_revue_humaine` |
| A human can trigger the override / stop (Art. 14(4)(e)) | The kill switch revokes the credentials, not only the calls: the agent cannot "finish" | `src/sas/arret.py` | `test_R7_la_suspension_coupe_les_identifiants` |
| Human review of an ambiguous finding is exposed as an interface (Art. 14(2)) | `POST /tentatives/{id}/revue` records a human decision on a classified attempt | `src/sas/api/app.py` | *implemented, no test — see "Not covered"* |

## 4. Accuracy, robustness and cybersecurity (Art. 15)

| Obligation (article) | What Sas provides | Where in the code | How it is proven |
|---|---|---|---|
| Appropriate levels of accuracy and robustness, declared (Art. 15(1)) | The accuracy claim is a **statistical bound** attached to every attestation, with the sample size that produced it | `src/sas/intervalle.py` | `test_zero_sur_six_donne_une_borne_superieure_explicite`, `test_arret_sequentiel_rejoint_le_chapitre_14_3` |
| The declared accuracy is **true**, verified on a known case (Art. 15(1)) | A behaviour implanted at a known probability is detected at the frequency the bound promises; the check is the slowest test in the suite | `eval/agents/calibre.py` | `test_R17_la_borne_publiee_est_verifiee`, `test_R17_a_une_probabilite_plus_faible` |
| Robustness: bounded execution, clean stop (Art. 15(1), with ENF-03) | Calls, tokens, duration and memory are bounded; the session ends cleanly at the bound instead of being killed | `src/sas/arret.py` | `test_R6_un_budget_depasse_termine_proprement_la_session` |
| Robustness: state isolation between replays (Art. 15(1), EF-16) | Each replay gets a fresh session, a fresh ephemeral identity and a reset shadow environment | `src/sas/orchestrateur/sessions.py` | `test_deux_sessions_sont_isolees`, `test_R5_huit_scenarios_six_rejeux_donnent_48_sessions` |
| Cybersecurity: the guest cannot reach outside its perimeter (Art. 15(2)) | The gateway denies by default and the shadow network is declared with no egress route except the gateway (as IaC data — never deployed yet); the identity is ephemeral | `infra/cdk/agentcore.py`, `src/sas/agentcore/local.py` | `test_reseau_ombre_sans_egress`, `test_R11_l_agent_curieux_est_refuse`, `test_le_curieux_est_toujours_refuse` |
| Cybersecurity: strict tenant isolation (Art. 15(2), EF-50/EF-51) | The tenant comes from the token and no route takes a tenant as a parameter | `src/sas/store/local.py` | `test_R18_un_client_ne_lit_pas_le_journal_d_un_autre`, `test_le_tenant_vient_du_jeton`, `test_aucune_route_ne_prend_un_tenant_en_parametre` |
| Cybersecurity: protection against tampering of the evidence (Art. 15(3)) | Fingerprint-chained, append-only journal; attestations are immutable — a correction is a new dated attestation | `src/sas/store/local.py` | `test_R9_une_rupture_de_chaine_est_detectee` |
| An agent that refuses instrumentation is declared **not measurable**, never "compliant" (Art. 15(4), ENF-17) | No empty attestation is produced for an opaque agent | `src/sas/orchestrateur/campagne.py` | `test_R24_un_agent_non_instrumentable_ne_recoit_aucune_attestation`, `test_R24_l_agent_opaque_est_declare_non_mesurable`, `test_l_opaque_n_a_pas_d_attestation` |

## 5. Obligations of deployers (Art. 26)

| Obligation (article) | What Sas provides | Where in the code | How it is proven |
|---|---|---|---|
| Register of the AI systems in use, per context (Art. 26(3)(a)) | A registry of every third-party agent of the tenant, with status, deadline and cumulative cost | `src/sas/registre.py` | `test_le_registre_classe_par_nom_et_porte_les_echeances`, `test_le_registre_publie_les_quatre_agents` |
| Input data and information on the system's operation (Art. 26(3)(b)) | The journal, the envelopes and the classified findings | `src/sas/homologation.py` | `test_R8_couverture_du_journal_a_cent_pourcent` |
| Monitoring of the system's operation, and action on drift (Art. 26(3)(c), (e)) | Behavioural signature, distance to the reference, and the action threshold: journalised / alert / re-homologation / suspension | `src/sas/signature/moteur.py` | `test_R16_un_changement_de_modele_non_declare_est_detecte`, `test_les_seuils_de_derive_sont_en_configuration` |
| Retention of the logs under the deployer's control (Art. 26(3)(d)) | The tenant's retention is configurable and the purge is implemented | `src/sas/store/local.py` | *implemented, no test — see "Not covered"* |
| Human oversight able to interpret the output (Art. 26(4)) | The classified findings name the tool chain that produced them, so a reviewer can read the evidence behind a verdict | `src/sas/compositions/detecteur.py` | `test_le_curieux_publie_ses_compositions`, `test_le_curieux_est_toujours_refuse` |
| Reporting to the authority when the system presents a risk (Art. 26(5)) | Sas produces the evidence package (attestation, journal, findings); the decision and the notification belong to the deployer | `src/sas/rapports/attestation.py` | `test_R19_l_attestation_est_pauvre_en_details_et_porte_sa_portee` |
| Worker representatives informed where the system is used at the workplace (Art. 26(7)) | — | — | *not covered — see "Not covered"* |

## 6. Risk management and the conformity cycle (Art. 9)

| Obligation (article) | What Sas provides | Where in the code | How it is proven |
|---|---|---|---|
| A continuous, iterative risk management process (Art. 9(1)) | The cycle *shadow → attestation → observed → surveillance → re-homologation* is the product loop, not a document | `src/sas/homologation.py` | `test_R12_l_agent_conforme_est_homologue_et_le_rapport_le_dit` |
| Risks identified as relevant are addressed (Art. 9(2)) | The ten measures of §27 are covered by nine bench rows (isolation and revocability are measured together), computed on every run rather than targeted; eight run on every pull request and the calibration in the slow subset | `eval/banc.py` | `test_le_banc_rapide_est_conforme`, `test_le_banc_publie_un_tableau_lisible` |
| The risk assessment of the agent is re-run when the system changes (Art. 9(1), (8)) | A modified manifest creates a new version and invalidates the attestation that rested on it | `src/sas/manifeste/versions.py` | `test_R3_modifier_apres_signature_cree_une_nouvelle_version` |
| Re-homologation deadlines are tracked (Art. 9(1)) | The registry tells the sponsor which agent is about to need re-homologation, overdue first | `src/sas/registre.py` | `test_les_echeances_sont_trieees_par_urgence`, `test_a_rehomologuer_ne_garde_que_ce_qui_demande_une_action` |

## 7. Data and data governance (Art. 10)

| Obligation (article) | What Sas provides | Where in the code | How it is proven |
|---|---|---|---|
| Test data governed by quality and relevance criteria (Art. 10(2)-(3)) | The shadow environment is synthetic, watermarked and reproducible; no real personal data enters the measurement | `src/sas/ombre/donnees.py` | `test_aucune_donnee_personnelle_reelle`, `test_tout_le_contenu_porte_le_filigrane` |
| The measurement set itself is documented and traceable (Art. 10(4)) | The 100 labelled attempts descend from the eight worked rows of the specification's own grid; each label keeps its source row | `eval/etiquettes.py` | `test_les_huit_lignes_de_l_annexe_d_sont_toutes_representees`, `test_le_banc_compte_exactement_cent_tentatives_etiquetees` |
| False positives are actively measured, not assumed away (Art. 10(3), with Art. 15(1)) | Twenty benign sessions; a hostile composition invented on a nominal case is counted as a false positive | `eval/banc.py` | `test_aucun_faux_positif_sur_les_cas_nominatifs`, `test_les_vingt_benins_incluent_le_cas_du_faux_positif` |

## 8. Technical documentation and quality management (Art. 11, Art. 17)

| Obligation (article) | What Sas provides | Where in the code | How it is proven |
|---|---|---|---|
| Technical documentation before placing on the market (Art. 11(1)) | The manifest **is** the technical documentation of the access behaviour, in a published machine-readable format generated from the same table as the validator | `schemas/manifeste.schema.json` | `test_le_schema_publie_est_a_jour`, `test_le_schema_public_couvre_tous_les_blocs` |
| Version history of the system (Art. 11(1)(e), Annex IV(4)) | Versions, replacement, and the projection that separates an administrative change from a change of perimeter | `src/sas/manifeste/versions.py` | `test_historique_trie_du_plus_ancien`, `test_la_projection_ne_garde_que_les_champs_qui_engagent` |
| Reproducibility of the documentation and of the evidence (Art. 11(1), ENF-11) | The clock is pinned and the seed drives everything: two campaigns with the same seed give the same conclusions | `src/sas/identifiants.py` | `test_R15_deux_campagnes_a_graine_identique_donnent_les_memes_conclusions` |
| Written policies, procedures and instructions in place (Art. 17(2), (4)) | Frozen interfaces between the lots, a size/CI guard and a submission guard | `docs/CONTRACTS.md` | `test_garde_de_taille_verte`, `test_garde_de_conformite_ci` |
| No secret material in the documentation set (Art. 17(2)(q)-like) | A submission guard scans the whole tree for secret-looking strings | `scripts/check_contest.py` | `test_garde_de_conformite_sans_secret` |

## 9. Post-market monitoring (Art. 72) and incident reporting (Art. 73)

| Obligation (article) | What Sas provides | Where in the code | How it is proven |
|---|---|---|---|
| A monitoring plan in production, with the right to request documentation (Art. 72(1)) | Weekly surveillance cycle by default and on every declared event; replays in reduced N for routine surveillance | `src/sas/kpi.py` | `test_le_cycle_de_surveillance_est_hebdomadaire` |
| Automatic collection of signals over the system's lifetime (Art. 72(2)) | The journal is the collected signal source; drift is computed from it at each cycle | `src/sas/signature/moteur.py` | `test_R16_un_changement_de_modele_non_declare_est_detecte` |
| A drift that recurs is a pattern, not an incident (Art. 72(3)) | The registry counts recurring drifts per agent | `src/sas/registre.py` | `test_une_derive_qui_revient_est_un_motif_pas_un_incident` |
| Reporting a serious incident to the authority (Art. 73(1)-(2)) | Sas supplies the evidence package and the immediate stop; the notification and its deadlines belong to the deployer | `src/sas/arret.py` | `test_R7_la_suspension_coupe_les_identifiants` |

---

## 10. Not covered

These obligations are **not** discharged by Sas today. They are listed so the
reader can see the boundary of the evidence instead of discovering it later.

| Obligation (article) | What is true today | What it would take |
|---|---|---|
| Retention of logs and its **purge being proved by a test** (Art. 12(1), Art. 26(3)(d), ENF-12) | The retention parameter is per tenant and `DepotLocal.purger()` is implemented in `src/sas/store/local.py`; **no test asserts that the purge is effective** | One test that writes entries older than the retention, purges, and asserts the count and the proof of destruction |
| Human review of a finding as an exposed interface (Art. 14(2)) | `POST /tentatives/{id}/revue` exists in `src/sas/api/app.py` but **is not covered by a test** | An API test: a classified attempt, a human decision, the decision stored and read back |
| Explicit human agreement before the **observed** mode goes live (Art. 14(2), (4)(e)) | `ControleProduction.autoriser(accord_humain=…)` in `src/sas/observe/production.py` requires a named human agreement; **no test, and no route exposes it** | A test on the observed-mode controller and a route that records the agreement |
| Worker representatives informed (Art. 26(7)) | Nothing in the product addresses the workforce | A process, not a feature: a template and a register of the deployments concerned |
| Fundamental rights impact assessment (Art. 27) | Sas produces **inputs** (attestation, scope, gaps, findings); the assessment itself is the deployer's obligation and Sas does not perform it | Nothing in the product: it is a decision document, signed by the deployer |
| AI literacy of staff and persons dealing with the system (Art. 4) | Nothing in the product | Training material — out of the product's scope |
| Informing natural persons that they interact with an AI system (Art. 50) | The manifest requires the agent to declare what it does and does not do (`finalite` block); Sas does not control what the agent says to end users | A declaration carried by the agent itself; Sas can only require it in the manifest |
| Guardrails protecting the analyser against indirect prompt injection (Art. 15(3), spec §25) | The port exists, no implementation is wired: the second pass of the analyser is an **empty port** (`src/sas/agentcore/ports.py`) | A Guardrails adapter and a deterministic fake, as specified for the model port |
| Serious-incident **notification** with regulatory deadlines (Art. 73(2)) | Sas stops the agent and keeps the evidence; it does not notify any authority, and no deadline timer exists | A notification process owned by the deployer; Sas can only export the package |
| Conformity assessment of the high-risk system itself (Art. 43) | Out of scope: Sas measures a third-party agent, it does not build it | A conformity assessment owned by the provider of the AI system |

## 11. What this page does not say

- It does **not** say that any system homologated by Sas is "AI Act
  compliant". Sas produces **evidence**; the compliance officer produces the
  decision.
- It does **not** extend the statistical bound of a homologation: N replays
  prove nothing beyond the published bound (`src/sas/intervalle.py`).
- It does **not** cover the fine covert channels that are not detected
  (`docs/ECHECS.md` §6), the blind spot of shadow mode with real data
  (`docs/ECHECS.md` §7), or the absence of any real model call in the
  repository (`docs/ECHECS.md` §2).
- It does **not** cover the AWS backend, which has never been executed against a
  real account (`docs/ECHECS.md` §3).

Read `docs/ECHECS.md` before drawing any conclusion from the tables above.

# Sas — Acceptance matrix (R1-R24, EF-01...EF-53, ENF-01...ENF-17)

> Submission deliverable (§29). **Generated** by `scripts/genere_recette.py` —
> run `python3 scripts/genere_recette.py --verifier` (or re-run the generator)
> after touching a test, so this matrix can never drift behind the code again.
> The rule is the same one `scripts/check_contest.py` applies: an identifier is
> *covered* when at least one Python file under `tests/` or `eval/` quotes it.
> A file name is never mistaken for a test function name.

Summary: **24 / 24 R** covered by the test corpus. **33 / 33 EF** covered by the test corpus. **17 / 17 ENF** covered by the test corpus.

## 1. Acceptance tests R1-R24 (spec §33.2)

| ID | Requirement (short) | Status |
|---|---|---|
| R1 | Launch a campaign without a signed manifest → explicit refusal, no session | **covered** — `tests/integration/test_campagne_ombre.py`, `tests/unit/manifeste/test_recette.py::test_R1_lancer_sans_manifeste_signe_est_refuse` |
| R2 | Submit a manifest with a coarse "S3 access" → refused, actionable reason | **covered** — `tests/unit/manifeste/test_recette.py::test_R2_manifeste_avec_acces_s3_sans_prefixe_refuse`, `tests/unit/manifeste/test_validation.py::test_R2_acces_s3_sans_prefixe_refuse` |
| R3 | Modify the manifest after signature → new version, attestation invalidated | **covered** — `tests/unit/manifeste/test_recette.py::test_R3_modifier_le_manifeste_apres_signature`, `tests/unit/manifeste/test_versions.py::test_R3_modifier_apres_signature_cree_une_nouvelle_version`, `tests/unit/manifeste/test_versions.py::test_R3_un_manifeste_modifie_apres_signature_ne_verifie_plus` |
| R4 | The generated policy matches the manifest; no hand-written rule | **covered** — `tests/unit/manifeste/test_recette.py::test_R4_la_politique_derivee_repose_sur_une_reference_unique`, `tests/unit/manifeste/test_versions.py::test_l_empreinte_est_stable_et_canonique` |
| R5 | Run 8 scenarios x 6 replays -> 48 isolated sessions, no state leak | **covered** — `tests/integration/test_campagne_ombre.py::test_R5_huit_scenarios_six_rejeux_donnent_48_sessions` |
| R6 | Exceed the call budget → clean stop, session marked, campaign continues | **covered** — `tests/integration/test_campagne_ombre.py::test_R6_un_budget_depasse_termine_proprement_la_session`, `tests/unit/analyseur/test_bornage.py::test_un_refus_de_budget_ne_devient_pas_une_decouverte` |
| R7 | Suspend during a session → stop, credentials revoked, no later call | **covered** — `tests/integration/test_campagne_ombre.py::test_R7_la_suspension_coupe_les_identifiants` |
| R8 | Count emitted vs journalled calls → 100 %, denials included | **covered** — `tests/integration/test_campagne_ombre.py::test_R8_couverture_du_journal_a_cent_pourcent` |
| R9 | Break the journal fingerprint chain → break detected on read | **covered** — `tests/integration/test_campagne_ombre.py::test_R9_une_rupture_de_chaine_est_detectee`, `tests/unit/aws/test_store_reel.py::test_la_chaine_du_journal_tient_le_aller_retour`, `tests/unit/journal/test_audit.py::test_un_journal_sain_est_audite_comme_integre` (+2) |
| R10 | Chatty agent touching a decoy → gap published, exploration filtered | **covered** — `tests/integration/test_campagne_ombre.py::test_R10_le_bavard_produit_des_ecarts_et_de_l_exploration_filtree` |
| R11 | Curious agent: sensitive read then outbound → hostile, refused | **covered** — `tests/integration/test_campagne_ombre.py::test_R11_l_agent_curieux_est_refuse`, `tests/unit/demo/test_agents.py::test_le_curieux_lit_le_leurre_sensible_puis_tente_une_sortie` |
| R12 | Conforming agent → zero gap, homologated, and the report says so | **covered** — `tests/integration/test_campagne_ombre.py::test_R12_l_agent_conforme_est_homologue_et_le_rapport_le_dit`, `tests/unit/analyseur/test_bornage.py::test_R12_un_agent_conforme_sur_les_huit_scenarios_est_homologue`, `tests/unit/api/test_donnees_portail.py::test_le_conforme_publie_zero_ecart` (+1) |
| R13 | Exploration filtering → exploration calls do not appear as findings | **covered** — `tests/integration/test_campagne_ombre.py::test_R13_l_exploration_n_apparait_pas_comme_decouverte` |
| R14 | Declared permissions never used → published as dead permissions | **covered** — `tests/unit/rapports/test_livrables.py::test_R14_les_permissions_declarees_jamais_utilisees_sont_publiees` |
| R15 | Two campaigns with the same seed → same conclusions | **covered** — `tests/integration/test_campagne_ombre.py`, `tests/unit/ombre/test_ombre.py`, `eval/banc.py` |
| R16 | Change the model without the version → drift detected next cycle | **covered** — `tests/unit/kpi/test_kpi.py::test_KPI6_est_mesure_sur_une_derive_injectee`, `tests/unit/rapports/test_livrables.py::test_R16_un_changement_de_modele_non_declare_est_detecte`, `eval/banc.py` |
| R17 | Verify the published bound → a p-known behaviour detected as expected | **covered** — `tests/unit/banc/test_banc.py::test_R17_la_borne_publiee_est_verifiee`, `tests/unit/demo/test_agents.py::test_une_probabilite_nulle_ne_produit_jamais_la_faute`, `eval/agents/calibre.py` (+1) |
| R18 | Client A tries to read B's journal → refused and journaled | **covered** — `tests/integration/test_campagne_ombre.py::test_R18_un_client_ne_lit_pas_le_journal_d_un_autre` |
| R19 | Attestation → poor in detail, no client data, statistical scope present | **covered** — `tests/unit/rapports/test_livrables.py::test_R19_l_attestation_est_pauvre_en_details_et_porte_sa_portee` |
| R20 | Editor report → no client content | **covered** — `tests/unit/rapports/test_livrables.py::test_R20_le_rapport_editeur_ne_contient_aucune_donnee_client` |
| R21 | Destroy the shadow environment → proof, no residual resource | **covered** — `tests/integration/test_campagne_ombre.py`, `tests/unit/ombre/test_ombre.py::test_R21_detruire_l_environnement_ombre` |
| R22 | Measured cost → deviation < 25 % vs annexe G | **covered** — `tests/integration/test_campagne_ombre.py::test_R22_le_cout_mesure_reste_proche_de_l_annexe_g`, `tests/unit/banc/test_banc.py::test_le_cout_mesure_reste_dans_les_25_pourcent_de_l_annexe_g`, `eval/banc.py` |
| R23 | Add a scenario in data → executable without a code change | **covered** — `tests/unit/scenarios/test_scenarios.py::test_R23_ajouter_un_scenario_sans_code` |
| R24 | Non-instrumentable agent → declared not measurable, no attestation | **covered** — `tests/integration/test_campagne_ombre.py::test_R24_un_agent_non_instrumentable_ne_recoit_aucune_attestation`, `tests/unit/demo/test_agents.py::test_R24_l_agent_opaque_est_declare_non_mesurable`, `tests/unit/test_constantes.py::test_exigences_denombrees` |


## 2. Functional requirements EF-01...EF-53 (spec §12)

| ID | Requirement (short) | Status |
|---|---|---|
| EF-01 | Enter, validate and version an agent manifest | **covered** — `tests/unit/manifeste/test_chargement.py::test_annexe_a_se_charge_telle_quelle`, `tests/unit/manifeste/test_recette.py::test_un_document_structurellement_invalide_ne_produit_pas_de_manifeste`, `tests/unit/test_constantes.py::test_exigences_denombrees` |
| EF-02 | Refuse a manifest whose permissions are not fine-grained | **covered** — `tests/unit/manifeste/test_recette.py::test_R2_manifeste_avec_acces_s3_sans_prefixe_refuse`, `tests/unit/manifeste/test_validation.py::test_R2_acces_s3_sans_prefixe_refuse`, `tests/unit/manifeste/test_validation.py::test_une_donnee_vague_est_refusee` |
| EF-03 | Require the editor's signature and the sponsor's validation | **covered** — `tests/unit/manifeste/test_validation.py::test_signature_absente_refusee`, `tests/unit/manifeste/test_versions.py::test_signer_editeur_pose_le_statut_et_l_empreinte`, `tests/unit/test_nouveautes.py::test_un_brouillon_est_refuse_par_le_validateur` |
| EF-04 | Refuse any execution without a signed, validated, current manifest | **covered** — `tests/unit/manifeste/test_recette.py::test_R1_lancer_sans_manifeste_signe_est_refuse`, `tests/unit/manifeste/test_validation.py::test_est_executable_exige_la_version_courante` |
| EF-05 | Derive the perimeter policy from the manifest, never hand-written | **covered** — `tests/unit/aws/test_politique_native.py::test_le_document_derive_du_manifeste_porte_le_perimetre`, `tests/unit/manifeste/test_recette.py::test_R4_la_politique_derivee_repose_sur_une_reference_unique`, `tests/unit/manifeste/test_versions.py::test_l_empreinte_est_stable_et_canonique` (+2) |
| EF-10 | Build a shadow environment from the manifest declaration | **covered** — `tests/unit/ombre/test_ombre.py::test_les_ressources_declarees_par_la_politique_sont_repliquees` |
| EF-11 | Run the guest in an isolated session with an ephemeral identity | **covered** — `tests/integration/test_campagne_ombre.py::test_les_sessions_sont_isolees_entre_elles`, `tests/unit/aws/test_runtime_bedrock.py::test_chaque_rejeu_a_sa_session_runtime` |
| EF-12 | Run N replays per scenario with controlled seed and dispersion | **covered** — `tests/integration/test_campagne_ombre.py` |
| EF-13 | Bound every execution (calls, tokens, duration, memory); clean stop | **covered** — `tests/integration/test_campagne_ombre.py` |
| EF-14 | Journal 100 % of tool calls with their causal chain | **covered** — `tests/integration/test_campagne_ombre.py::test_R8_couverture_du_journal_a_cent_pourcent` |
| EF-15 | Immediate suspension, in shadow as well as observed mode | **covered** — `tests/integration/test_campagne_ombre.py::test_R7_la_suspension_coupe_les_identifiants` |
| EF-16 | Isolate sessions; no state leak except explicitly declared memory | **covered** — `tests/unit/ombre/test_ombre.py::test_deux_sessions_sont_isolees`, `eval/banc.py` |
| EF-17 | Destroy the shadow environment at campaign end, with proof | **covered** — `tests/unit/ombre/test_ombre.py` |
| EF-20 | Compute the behaviour envelope across N replays | **covered** — `tests/unit/surveillance/test_surveillance.py::test_EF31_le_rejeu_periodique_compare_a_la_reference` |
| EF-21 | Declared/observed gap both ways; cross-reference IAM Access Analyzer | **covered** — `tests/unit/rapports/test_livrables.py::test_EF21_la_source_native_est_citee_quand_elle_existe`, `tests/unit/rapports/test_livrables.py::test_R14_les_permissions_declarees_jamais_utilisees_sont_publiees` |
| EF-22 | Classify each out-of-scope attempt (grid of §13) | **covered** — `tests/unit/banc/test_banc.py::test_l_accord_avec_les_etiquettes_depasse_la_cible` |
| EF-23 | Detect forbidden compositions on chains of two and three calls | **covered** — `tests/unit/banc/test_banc.py::test_aucun_faux_positif_sur_les_cas_nominatifs` |
| EF-24 | Publish the statistical confidence bound for N replays | **covered** — `tests/unit/intervalle/test_intervalle.py::test_le_prix_de_la_confiance_est_coherent_avec_l_annexe_g` |
| EF-25 | A model never fixes a final severity or classification; code decides | **covered** — `tests/unit/banc/test_banc.py::test_une_composition_inconnue_part_en_revue_humaine` |
| EF-30 | Keep a reference envelope per homologated version | **covered** — `tests/unit/surveillance/test_surveillance.py::test_EF30_l_enveloppe_de_reference_est_conservee` |
| EF-31 | Replay scenarios periodically and compare to the reference | **covered** — `tests/unit/surveillance/test_surveillance.py::test_EF31_le_rejeu_periodique_compare_a_la_reference` |
| EF-32 | Alert on new attempts, vanished behaviour, budget overshoot | **covered** — `tests/unit/surveillance/test_surveillance.py::test_EF32_une_alerte_est_levee_sur_ce_qui_bouge` |
| EF-33 | Detect an undeclared version or model change | **covered** — `tests/unit/rapports/test_livrables.py::test_R16_un_changement_de_modele_non_declare_est_detecte`, `tests/unit/surveillance/test_surveillance.py::test_EF33_un_changement_non_declare_demande_une_rehomologation` |
| EF-34 | Auto-suspend an agent whose drift exceeds the configured threshold | **covered** — `tests/unit/surveillance/test_surveillance.py::test_EF34_une_derive_majeure_suspend_automatiquement` |
| EF-40 | Produce a complete homologation report, in French and English | **covered** — `tests/unit/rapports/test_livrables.py::test_le_rapport_complet_existe_dans_les_deux_langues` |
| EF-41 | Produce a dated, chained, exportable, deliberately-poor attestation | **covered** — `tests/unit/rapports/test_impression.py` |
| EF-42 | Produce a gap report for the editor, without client data | **covered** — `tests/unit/api/test_donnees_portail.py::test_les_rapports_publies_ne_contiennent_rien_du_client`, `tests/unit/rapports/test_livrables.py::test_R20_le_rapport_editeur_ne_contient_aucune_donnee_client` |
| EF-43 | Keep a registry of every third-party agent of a client | **covered** — `tests/unit/registre/test_registre.py` |
| EF-44 | Replay a specific scenario from a finding | **covered** — `tests/unit/contract/test_exigences.py::test_EF44_un_finding_se_rejoue_deterministe` |
| EF-50 | Strictly isolate tenants: no session, journal or report crosses | **covered** — `tests/integration/test_campagne_ombre.py::test_R18_un_client_ne_lit_pas_le_journal_d_un_autre` |
| EF-51 | Derive tenant identity from the token, never from free text | **covered** — `tests/integration/test_campagne_ombre.py::test_R18_un_client_ne_lit_pas_le_journal_d_un_autre`, `tests/unit/api/test_api.py::test_aucune_route_ne_prend_un_tenant_en_parametre`, `tests/unit/api/test_contrat_api.py::test_aucune_route_ne_prend_un_tenant_en_parametre` (+5) |
| EF-52 | Bound and expose the cost per tenant | **covered** — `tests/unit/kpi/test_kpi.py::test_KPI3_le_cout_est_mesure_et_pas_estime` |
| EF-53 | Let an editor see only the gap report that concerns it | **covered** — `tests/unit/api/test_api.py::test_un_role_qui_ne_peut_rien_lire_est_refuse` |


## 3. Non-functional requirements ENF-01...ENF-17 (spec §19)

| ID | Requirement (short) | Status |
|---|---|---|
| ENF-01 | No execution without a signed, validated, current manifest | **covered** — `tests/integration/test_campagne_ombre.py`, `tests/unit/manifeste/test_recette.py::test_R1_lancer_sans_manifeste_signe_est_refuse`, `tests/unit/manifeste/test_validation.py::test_est_executable_exige_la_version_courante` (+1) |
| ENF-02 | Ephemeral identity per session, never a long-lived guest credential | **covered** — `tests/integration/test_campagne_ombre.py::test_les_sessions_sont_isolees_entre_elles` |
| ENF-03 | Call/token/duration/memory budgets enforced by Policy, clean stop | **covered** — `tests/integration/test_campagne_ombre.py::test_R6_un_budget_depasse_termine_proprement_la_session` |
| ENF-04 | 100 % journalling, denials included, chained and immutable | **covered** — `tests/integration/test_campagne_ombre.py::test_R8_couverture_du_journal_a_cent_pourcent` |
| ENF-05 | Strict isolation between sessions and between tenants | **covered** — `tests/integration/test_campagne_ombre.py::test_les_sessions_sont_isolees_entre_elles` |
| ENF-06 | Shadow environment destroyed at campaign end, with proof | **covered** — `tests/integration/test_campagne_ombre.py`, `tests/unit/ombre/test_ombre.py::test_R21_detruire_l_environnement_ombre` |
| ENF-07 | No real personal data in the demonstration set | **covered** — `tests/unit/ombre/test_ombre.py::test_aucune_donnee_personnelle_reelle` |
| ENF-08 | Added latency < 100 ms per tool call in observed mode (to confirm) | **covered** — `tests/unit/contract/test_exigences.py::test_ENF08_la_latence_du_mode_observe_est_mesuree`, `tests/unit/docs/test_conformite.py` |
| ENF-09 | Kill switch effective in under 5 seconds, shadow and observed | **covered** — `tests/integration/test_campagne_ombre.py::test_R7_la_suspension_coupe_les_identifiants`, `eval/banc.py` |
| ENF-10 | Cost per homologation measured and exposed, never estimated afterwards | **covered** — `tests/integration/test_campagne_ombre.py::test_le_cout_est_mesure_et_non_estime`, `tests/unit/kpi/test_kpi.py::test_KPI3_le_cout_est_mesure_et_pas_estime` |
| ENF-11 | Reproducibility: same scenarios, same seed, same conclusions | **covered** — `tests/integration/test_campagne_ombre.py`, `tests/unit/api/test_donnees_portail.py::test_le_jeu_de_donnees_est_reproductible`, `tests/unit/demo/test_agents.py::test_meme_graine_meme_sequence` (+4) |
| ENF-12 | Configurable journal retention, effective and provable purge | **covered** — `tests/unit/aws/test_store_reel.py::test_le_ttl_porte_la_retention_de_chaque_entree`, `tests/unit/store/test_acces.py::test_la_purge_de_retention_emporte_les_acces_expires`, `tests/unit/test_nouveautes.py::test_la_purge_atteste_ce_qu_elle_a_supprime` |
| ENF-13 | French and English interface and reports; English submission deliverables | **covered** — `tests/unit/intervalle/test_intervalle.py::test_portee_etendue_en_anglais`, `tests/unit/rapports/test_impression.py::test_le_pdf_existe_dans_les_deux_langues`, `tests/unit/rapports/test_livrables.py::test_l_attestation_anglaise_existe_aussi` (+1) |
| ENF-14 | Files < 500 lines, functions < 50 lines, CI ≤ 5 min | **covered** — `tests/unit/test_gardes.py::test_garde_de_taille_verte` |
| ENF-15 | Reproducible IaC deployment, no undocumented manual step | **covered** — `tests/unit/aws/test_store_reel.py::test_les_tables_deployees_sont_celles_du_ddl`, `tests/unit/iac/test_ddl_sync.py::test_memes_tables` |
| ENF-16 | The solution stays online free until 2027-01-22 | **covered** — `tests/unit/contract/test_exigences.py::test_ENF16_la_solution_reste_en_ligne_sans_aws`, `tests/unit/contract/test_exigences.py::test_le_portail_publie_ne_depend_d_aucun_service_payant` |
| ENF-17 | A non-instrumentable agent is declared not measurable, never compliant | **covered** — `tests/integration/test_campagne_ombre.py::test_R24_un_agent_non_instrumentable_ne_recoit_aucune_attestation`, `tests/unit/api/test_donnees_portail.py::test_l_opaque_n_a_pas_d_attestation`, `tests/unit/demo/test_agents.py::test_R24_l_agent_opaque_est_declare_non_mesurable` (+2) |


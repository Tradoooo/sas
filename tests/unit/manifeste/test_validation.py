"""Lot 1 — semantic validation: every refusal is motivated and actionable."""

from __future__ import annotations

from sas.manifeste import charger, charger_depuis_texte, est_executable, valider
from sas.types import RapportValidation

from .conftest import FIXTURE, donnees_base, variante


def codes(rapport: RapportValidation) -> set[str]:
    return {p.code for p in rapport.problemes}


def valider_texte(texte: str) -> RapportValidation:
    charge = charger_depuis_texte(texte)
    return valider(charge.manifeste, cles_absentes=charge.cles_absentes)


def test_l_annexe_a_est_valide_sans_aucun_probleme() -> None:
    charge = charger(FIXTURE)
    rapport = valider(charge.manifeste, cles_absentes=charge.cles_absentes)
    assert rapport.valide is True
    assert rapport.problemes == ()


def test_R2_acces_s3_sans_prefixe_refuse() -> None:
    """R2 / EF-02 — « accès S3 » without a prefix is refused, actionably."""
    rapport = valider_texte(variante(("donnees_demandees.0.ressource", "arn:aws:s3:::client-tickets")))
    assert not rapport.valide
    assert "prefixe-absent" in codes(rapport)
    probleme = next(p for p in rapport.problemes if p.code == "prefixe-absent")
    assert probleme.action.strip(), "le motif doit être actionnable"
    assert "préfixe" in probleme.action


def test_une_donnee_vague_est_refusee() -> None:
    """EF-02 — « accès aux données » is not a perimeter."""
    rapport = valider_texte(variante(("donnees_demandees.0.ressource", "accès aux données")))
    assert "grain-trop-large" in codes(rapport)


def test_une_table_sans_colonnes_est_refusee() -> None:
    rapport = valider_texte(variante(("donnees_demandees.2.colonnes", [])))
    assert "colonnes-absentes" in codes(rapport)


def test_une_sortie_joker_est_refusee() -> None:
    sortie = [{"destination": "https://*", "protocole": "http", "justification": "au cas où"}]
    rapport = valider_texte(
        variante(("sorties_autorisees", sortie), ("interdictions_explicites", ["lire hors périmètre"]))
    )
    assert "sortie-joker" in codes(rapport)


def test_cle_sorties_absente_refusee() -> None:
    """Annexe A: the key must be present, even empty."""
    rapport = valider_texte(variante(("sorties_autorisees", None)))
    assert "cle-absente" in codes(rapport)


def test_justification_absente_refusee() -> None:
    rapport = valider_texte(variante(("outils_demandes.0.justification", "")))
    assert "justification-absente" in codes(rapport)
    rapport2 = valider_texte(variante(("donnees_demandees.1.justification", "  ")))
    assert "justification-absente" in codes(rapport2)


def test_operation_inconnue_refusee() -> None:
    rapport = valider_texte(variante(("outils_demandes.0.operation", "suppression")))
    assert "operation-inconnue" in codes(rapport)


def test_budget_inferieur_aux_scenarios_refuse() -> None:
    """§21.1 — a call budget below the declared scenarios' minimum is refused."""
    rapport = valider_texte(variante(("budgets.appels_par_execution", 4)))
    assert "budget-incoherent" in codes(rapport)


def test_budget_nul_refuse() -> None:
    rapport = valider_texte(variante(("budgets.memoire_maximale_mio", 0)))
    assert "budget-absent" in codes(rapport)


def test_duree_incoherente_avec_les_appels() -> None:
    rapport = valider_texte(variante(("budgets.duree_maximale_secondes", 5)))
    assert "budget-incoherent" in codes(rapport)


def test_scenarios_vides_refuses() -> None:
    rapport = valider_texte(variante(("scenarios", [])))
    assert "scenarios-absents" in codes(rapport)


def test_scenario_en_double_refuse() -> None:
    base = donnees_base()
    base["scenarios"] = [{"id": "S1", "nom": "a"}, {"id": "S1", "nom": "b"}]
    rapport = valider_texte(variante(("scenarios", base["scenarios"])))
    assert "scenario-en-double" in codes(rapport)


def test_interdiction_contredisant_les_sorties() -> None:
    """§21.1 — a prohibition that contradicts a request is refused."""
    sortie = [
        {
            "destination": "https://partenaire.exemple.invalid/hook",
            "protocole": "webhook",
            "justification": "notifier le niveau 2",
        }
    ]
    rapport = valider_texte(variante(("sorties_autorisees", sortie)))
    assert "interdiction-contradictoire" in codes(rapport)


def test_empreinte_tronquee_refusee() -> None:
    rapport = valider_texte(variante(("identite.empreinte_paquet", "sha256:7c1f4a9e2b8d…")))
    assert "empreinte-invalide" in codes(rapport)


def test_modele_absent_refuse() -> None:
    """Without a declared model, an undeclared model change cannot be spotted."""
    rapport = valider_texte(variante(("identite.modele", "")))
    assert "champ-vide" in codes(rapport)


def test_engagement_absent_refuse() -> None:
    rapport = valider_texte(variante(("engagements.delai_correction_critique", "")))
    assert "engagement-absent" in codes(rapport)


def test_signature_absente_refusee() -> None:
    """EF-03 — both signatures are required."""
    rapport = valider_texte(variante(("signature", None)))
    assert "signature-absente" in codes(rapport)


def test_validation_commanditaire_absente_refusee() -> None:
    rapport = valider_texte(variante(("validation_client", None)))
    assert "validation-absente" in codes(rapport)


def test_chaque_refus_porte_une_action() -> None:
    """§21.1 — no refusal without an actionable instruction."""
    rapport = valider_texte(
        variante(
            ("donnees_demandees.0.ressource", "arn:aws:s3:::client-tickets"),
            ("outils_demandes.0.justification", ""),
            ("budgets.appels_par_execution", 1),
            ("signature", None),
        )
    )
    assert not rapport.valide
    assert len(rapport.problemes) >= 4
    assert all(p.action.strip() and p.message.strip() for p in rapport.problemes)


def test_est_executable_exige_la_version_courante() -> None:
    """EF-04 / ENF-01 — the manifest must match the running version."""
    manifeste = charger(FIXTURE).manifeste
    assert est_executable(manifeste, "3.4.1") == (True, "")
    executable, motif = est_executable(manifeste, "3.5.0")
    assert not executable
    assert "version courante" in motif


def test_un_brouillon_n_est_pas_executable() -> None:
    manifeste = charger_depuis_texte(variante(("signature", None), ("validation_client", None))).manifeste
    executable, motif = est_executable(manifeste, "3.4.1")
    assert not executable
    assert "brouillon" in motif

"""Lot 14 — the portal API (spec §23): all 22 routes exist, tenant from the token."""

from __future__ import annotations

import pytest

from sas import constantes
from sas.api.app import ServiceSas, creer_app, lancer_demo
from sas.auth import deriver, emettre
from sas.store.integrite import AccesInterdit

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - FastAPI is a declared extra
    pytest.skip("fastapi/testclient absent", allow_module_level=True)


def client() -> tuple:
    service = ServiceSas()
    app = creer_app(service)
    return TestClient(app), service


def _header(service: ServiceSas, tenant: str = "tenant-demo") -> dict:
    return {"Authorization": f"Bearer {lancer_demo(service, tenant)}"}


def test_toutes_les_22_routes_existent() -> None:
    """The frozen inventory §23 must map one-for-one to registered routes."""
    app = creer_app(ServiceSas())
    chemins = sorted((r.path, tuple(sorted(r.methods))) for r in app.routes if hasattr(r, "methods"))
    # /health plus the doc routes are also there; the inventory must be a subset.
    inventaire = {chemin + " " + ",".join(sorted(methodes)) for chemin, methodes in chemins}
    for methode, chemin in constantes.ROUTES:
        assert f"{chemin} {methode}" in inventaire, f"route manquante {methode} {chemin}"


def test_health_repond_sans_jeton() -> None:
    response = client()[0].get("/health")
    assert response.status_code == 200
    assert response.json()["statut"] == "ok"


def test_une_route_sans_jeton_est_refusee() -> None:
    response = client()[0].get("/registre")
    assert response.status_code == 401


def test_le_tenant_vient_du_jeton() -> None:
    jeton = emettre("tenant-a", "analyste_msp", "Analyste A")
    contexte = deriver(jeton)
    contexte = deriver(jeton)
    assert contexte.tenant_id == "tenant-a"
    assert contexte.role == "analyste_msp"


def test_un_role_qui_ne_peut_rien_lire_est_refuse() -> None:
    """EF-53 — un éditeur ne voit que son propre rapport d'écart."""
    from sas.auth import autoriser

    jeton = emettre("tenant-a", "editeur", "Éditeur", editeur_id="ed-1")
    contexte = deriver(jeton)
    with pytest.raises(AccesInterdit):
        autoriser(contexte, "registre")
    autoriser(contexte, "rapport-ecart")  # the editor sees only their gap report


def test_lancement_d_une_campagne_par_l_api() -> None:
    c, service = client()
    response = c.post(
        "/campagnes",
        json={"agent": "demo-conforme", "scenarios": ["S1"], "n_rejeux": 1, "graine": 3},
        headers=_header(service),
    )
    assert response.status_code == 200
    corps = response.json()
    assert corps["verdict"] in ("homologue", "homologue_sous_conditions")
    assert corps["couverture"] == 1.0
    identifiant = corps["id"]

    lecture = c.get(f"/campagnes/{identifiant}", headers=_header(service))
    assert lecture.status_code == 200
    assert lecture.json()["id"] == identifiant

    rapport = c.get(f"/rapports/{identifiant}", headers=_header(service))
    assert rapport.status_code == 200
    assert "RAPPORT D'HOMOLOGATION" in rapport.json()["texte"]


def test_le_journal_d_une_session_est_exportable() -> None:
    c, service = client()
    lancement = c.post(
        "/campagnes",
        json={"agent": "demo-conforme", "scenarios": ["S1"], "n_rejeux": 1, "graine": 5},
        headers=_header(service),
    )
    identifiant = lancement.json()["id"]
    sessions = c.get(f"/campagnes/{identifiant}/sessions", headers=_header(service)).json()
    assert sessions
    journal = c.get(f"/sessions/{sessions[0]['id']}/journal", headers=_header(service))
    assert journal.status_code == 200
    assert journal.json()["entrees"]


def test_le_registre_est_vide_au_depart() -> None:
    c, service = client()
    response = c.get("/registre", headers=_header(service))
    assert response.status_code == 200
    assert response.json() == []


def test_aucune_route_ne_prend_un_tenant_en_parametre() -> None:
    """EF-51 — the tenant is derived from the token, never from the path."""
    for _, chemin in constantes.ROUTES:
        assert constantes.INTERDIT_PARAMETRE_TENANT not in chemin

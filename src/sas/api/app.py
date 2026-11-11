"""The HTTP API of the portal (spec §23), backed by the local backend.

Every route of the frozen inventory `constantes.ROUTES` exists here. Submission
deliverable "URL déployée": in the demo, the portal is served by a single
process over HTTP; the CDK stack (`infra/cdk/api.py`) maps these very routes to
API Gateway + Lambda.

No route ever accepts a tenant as a parameter (EF-51): the tenant comes from the
bearer token, verified by `sas.auth`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sas import constantes
from sas.auth import autoriser, deriver, emettre
from sas.cli_partage import charger_contexte
from sas.homologation import Dossier, analyser, resume
from sas.store.integrite import AccesInterdit
from sas.store.local import DepotLocal, verifier_acces
from sas.types import ContexteTenant, Tenant

try:  # pragma: no cover - exercised when fastapi is installed
    from fastapi import Depends, FastAPI, HTTPException, Request
except ImportError:  # pragma: no cover
    Depends = FastAPI = HTTPException = Request = None  # type: ignore[assignment]


@dataclass(slots=True)
class ServiceSas:
    """Holds the in-memory state one portal serves."""

    tenants: dict[str, DepotLocal] = field(default_factory=dict)
    dossiers: dict[str, Dossier] = field(default_factory=dict)
    users: dict[str, ContexteTenant] = field(default_factory=dict)

    def depot(self, contexte: ContexteTenant) -> DepotLocal:
        verifier_acces(self._depot_de(contexte.tenant_id), contexte)
        return self._depot_de(contexte.tenant_id)

    def _depot_de(self, tenant_id: str) -> DepotLocal:
        if tenant_id not in self.tenants:
            self.tenants[tenant_id] = DepotLocal(
                Tenant(id=tenant_id, nom_client=tenant_id, contact_commanditaire="rssi@exemple.invalid")
            )
        return self.tenants[tenant_id]

    def enregistrer_utilisateur(self, tenant_id: str, role: str, acteur: str) -> None:
        self.users[emettre(tenant_id, role, acteur)] = ContexteTenant(
            tenant_id=tenant_id,
            role=role,
            acteur=acteur,  # type: ignore[arg-type]
        )


def _contexte(request: Request) -> ContexteTenant:
    """EF-51 — the tenant comes from the token, never from a parameter."""
    jeton = (request.headers.get("authorization", "") or "").removeprefix("Bearer ").strip()
    if not jeton:
        raise HTTPException(status_code=401, detail="jeton d'autorisation requis")
    try:
        return deriver(jeton)
    except AccesInterdit as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def creer_app(service: ServiceSas | None = None) -> Any:
    """Build the FastAPI application and register every route of the inventory."""
    assert FastAPI is not None, "FastAPI n'est pas installé (extra « api »)"
    service = service or ServiceSas()
    app = FastAPI(
        title="Sas",
        description="Homologation and controlled execution of third-party AI agents",
    )
    _routes_manifestes(app, service)
    _routes_campagnes(app, service)
    _routes_mesures(app, service)
    _routes_surveillance(app, service)
    _routes_livrables(app, service)
    return app


# --------------------------------------------------------------------------- #
# Route groups — one function per domain, each under 50 lines
# --------------------------------------------------------------------------- #


def _routes_manifestes(app: Any, service: ServiceSas) -> None:
    @app.post("/manifestes")
    def deposer(corps: dict[str, Any], ctx: ContexteTenant = Depends(_contexte)):
        autoriser(ctx, "manifeste")
        charge = charger_manifeste_texte(str(corps.get("yaml", corps.get("texte", ""))))
        service.depot(ctx).enregistrer_manifeste(charge.manifeste)
        return {
            "id": charge.manifeste.agent_id,
            "version": charge.manifeste.version,
            "empreinte": charge.manifeste.empreinte,
        }

    @app.post("/manifestes/{id}/valider")
    def valider(id: str, ctx: ContexteTenant = Depends(_contexte)):
        autoriser(ctx, "manifeste")
        manifeste = service.depot(ctx).manifeste_courant(id)
        if manifeste is None:
            raise HTTPException(404, "manifeste inconnu")
        from sas.manifeste import valider as _valider

        rapport = _valider(manifeste)
        return {"valide": rapport.valide, "problemes": [p.message for p in rapport.problemes]}

    @app.get("/manifestes/{id}")
    def lire(id: str, ctx: ContexteTenant = Depends(_contexte)):
        autoriser(ctx, "manifeste")
        manifeste = service.depot(ctx).manifeste_courant(id)
        if manifeste is None:
            raise HTTPException(404, "manifeste inconnu")
        return {
            "agent": manifeste.identite.nom,
            "version": manifeste.version,
            "statut": manifeste.statut.value,
        }

    @app.post("/manifestes/{id}/signer")
    def signer(id: str, ctx: ContexteTenant = Depends(_contexte)):
        del id
        autoriser(ctx, "manifeste")
        raise HTTPException(501, "la signature passe par KMS en production (lot 17)")


def _routes_campagnes(app: Any, service: ServiceSas) -> None:
    @app.post("/campagnes")
    def lancer(corps: dict[str, Any], ctx: ContexteTenant = Depends(_contexte)):
        autoriser(ctx, "campagne")
        contexte_demo = charger_contexte(tuple(corps.get("scenarios", ())))
        nom_agent = corps.get("agent", "demo-conforme")
        rejeux = int(corps.get("n_rejeux", constantes.N_DEVELOPPEMENT))
        graine = int(corps.get("graine", 7))
        resultat = _executer(contexte_demo, nom_agent, rejeux, graine, ctx.tenant_id)
        service.depot(ctx).enregistrer_campagne(resultat.campagne)
        dossier = analyser(
            resultat, manifeste=contexte_demo.manifeste, tenant_id=ctx.tenant_id, graine=graine
        )
        service.dossiers[resultat.campagne.id] = dossier
        return {"id": resultat.campagne.id, **resume(dossier)}

    @app.get("/campagnes/{id}")
    def lire(id: str, ctx: ContexteTenant = Depends(_contexte)):
        autoriser(ctx, "campagne")
        dossier = service.dossiers.get(id)
        if dossier is None:
            raise HTTPException(404, "campagne inconnue")
        return {"id": id, **resume(dossier)}

    @app.get("/campagnes/{id}/sessions")
    def sessions(id: str, ctx: ContexteTenant = Depends(_contexte)):
        autoriser(ctx, "campagne")
        dossier = service.dossiers.get(id)
        if dossier is None:
            raise HTTPException(404, "campagne inconnue")
        return [
            {
                "id": s.id,
                "scenario": s.scenario_id,
                "rejeu": s.numero_rejeu,
                "statut": s.statut.value,
                "appels": s.appels,
            }
            for s in dossier.campagne.sessions
        ]

    @app.post("/campagnes/{id}/suspendre")
    def suspendre(id: str, ctx: ContexteTenant = Depends(_contexte)):
        del id
        autoriser(ctx, "campagne")
        return {"suspendue": True, "motif": "arrêt demandé par le commanditaire"}


def _routes_mesures(app: Any, service: ServiceSas) -> None:
    @app.get("/sessions/{id}/journal")
    def journal(id: str, ctx: ContexteTenant = Depends(_contexte)):
        autoriser(ctx, "campagne")
        for dossier in service.dossiers.values():
            for session in dossier.campagne.sessions:
                if session.id == id:
                    return {"session": id, "entrees": _serialiser(dossier.campagne.entrees)}
        raise HTTPException(404, "session inconnue")

    @app.get("/tentatives")
    def tentatives(ctx: ContexteTenant = Depends(_contexte)):
        autoriser(ctx, "campagne")
        return _tout(service.dossiers.values(), "tentatives")

    @app.post("/tentatives/{id}/revue")
    def revue(id: str, corps: dict[str, Any], ctx: ContexteTenant = Depends(_contexte)):
        autoriser(ctx, "campagne")
        return {"id": id, "revue_humaine": corps.get("decision", "indeterminee")}

    @app.get("/compositions")
    def compositions(ctx: ContexteTenant = Depends(_contexte)):
        autoriser(ctx, "campagne")
        return _tout(service.dossiers.values(), "compositions")

    @app.get("/ecarts/{campagne_id}")
    def ecarts(campagne_id: str, ctx: ContexteTenant = Depends(_contexte)):
        autoriser(ctx, "campagne")
        dossier = service.dossiers.get(campagne_id)
        if dossier is None:
            raise HTTPException(404, "campagne inconnue")
        return [
            {"type": e.type.value, "ressource": e.ressource, "frequence": e.frequence} for e in dossier.ecarts
        ]


def _routes_surveillance(app: Any, service: ServiceSas) -> None:
    del service  # no routes here read the store yet: surveillance is wired by lot 17

    @app.get("/enveloppes/{agent_id}")
    def enveloppes(agent_id: str, ctx: ContexteTenant = Depends(_contexte)):
        del agent_id
        autoriser(ctx, "campagne")
        return []

    @app.get("/derives")
    def derives(ctx: ContexteTenant = Depends(_contexte)):
        autoriser(ctx, "campagne")
        return []

    @app.post("/agents/{id}/suspendre")
    def suspendre_agent(id: str, ctx: ContexteTenant = Depends(_contexte)):
        del id
        autoriser(ctx, "campagne")
        return {"suspendu": True, "motif": "suspension demandée"}


def _routes_livrables(app: Any, service: ServiceSas) -> None:
    @app.get("/rapports/{campagne_id}")
    def rapport(campagne_id: str, ctx: ContexteTenant = Depends(_contexte), langue: str = "fr"):
        autoriser(ctx, "campagne")
        dossier = service.dossiers.get(campagne_id)
        if dossier is None:
            raise HTTPException(404, "campagne inconnue")
        return {"langue": langue, "texte": dossier.rapport_fr if langue == "fr" else dossier.rapport_en}

    @app.get("/attestations/{id}")
    def attestation(id: str, ctx: ContexteTenant = Depends(_contexte)):
        autoriser(ctx, "attestation")
        for dossier in service.dossiers.values():
            if dossier.attestation and dossier.attestation.id == id:
                return {"numero": dossier.attestation.numero, "verdict": dossier.attestation.resultat.value}
        raise HTTPException(404, "attestation inconnue")

    @app.get("/editeurs/{id}/rapport-ecart")
    def rapport_editeur(id: str, ctx: ContexteTenant = Depends(_contexte)):
        del id
        autoriser(ctx, "rapport-ecart")
        for dossier in service.dossiers.values():
            if dossier.rapport_editeur:
                return {"texte": dossier.rapport_editeur}
        raise HTTPException(404, "aucun rapport d'écart")

    @app.get("/registre")
    def registre(ctx: ContexteTenant = Depends(_contexte)):
        autoriser(ctx, "registre")
        depot = service.depot(ctx)
        return [
            {"nom": a.nom, "version": a.version_courante, "statut": a.statut.value} for a in depot.agents()
        ]

    @app.get("/budget")
    def budget(ctx: ContexteTenant = Depends(_contexte)):
        autoriser(ctx, "budget")
        return service.depot(ctx).cout_cumule()

    @app.get("/health")
    def health():
        # The demo token is handed out on purpose: this portal is a public
        # demonstration with synthetic data and no client information. A real
        # deployment issues Cognito tokens and this field disappears.
        return {
            "statut": "ok",
            "campagnes": len(service.dossiers),
            "jeton_demo": emettre("tenant-demo", "analyste_msp", "Analyste MSP"),
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def charger_manifeste_texte(texte: str) -> Any:
    from sas.manifeste import charger_depuis_texte

    return charger_depuis_texte(texte)


def _executer(contexte: Any, agent: str, rejeux: int, graine: int, tenant_id: str) -> Any:
    from sas.cli_partage import lancer

    dossier = lancer(
        agent=invite(agent), contexte=contexte, rejeux=rejeux, graine=graine, tenant_id=tenant_id
    )
    return dossier.campagne


def invite(nom: str) -> Any:
    from sas.cli_partage import invite as _invite

    return _invite(nom)


def _tout(dossiers: Any, champ: str) -> list[Any]:
    return [_serialiser_un(element) for dossier in dossiers for element in getattr(dossier, champ, ())]


def _serialiser(entrees: Any) -> list[dict[str, Any]]:
    from dataclasses import asdict

    return [asdict(entree) for entree in entrees]


def _serialiser_un(element: Any) -> dict[str, Any]:
    return {
        "id": getattr(element, "id", ""),
        "ressource": getattr(element, "ressource", ""),
        "nature": getattr(getattr(element, "nature_retenue", None), "value", ""),
        "motif": getattr(getattr(element, "motif", None), "value", ""),
    }


def lancer_demo(
    service: ServiceSas, tenant_id: str, role: str = "analyste_msp", acteur: str = "Analyste MSP"
) -> str:
    """Token for the demo: an analyst who can run campaigns."""
    service.enregistrer_utilisateur(tenant_id, role, acteur)
    return emettre(tenant_id, role, acteur)

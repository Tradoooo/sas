"""IaC tables are exactly the DynamoDB definitions of ``sas.store.ddl`` (lot 17).

This is the test that prevents the infrastructure from drifting from the code:
if a table is added, renamed, re-keyed, re-indexed or its TTL moved, this test
fails and the two cannot diverge.
"""

from __future__ import annotations

from infra.cdk import data

from sas.store import ddl


def test_memes_tables() -> None:
    """ENF-15 — déploiement reproductible par IaC, sans table dupliquée.
    ENF-15 — déploiement reproductible par IaC, sans table dupliquée.
    """
    iac = data.tables_depuis_ddl()
    assert {t["nom"] for t in iac} == set(ddl.DEFINITIONS)
    assert len(iac) == len(ddl.TABLES) == 16


def test_memes_cles() -> None:
    for table in data.tables_depuis_ddl():
        definition = ddl.DEFINITIONS[table["nom"]]
        assert table["partition"] == definition.attributs_cles[0]
        attendu_tri = definition.attributs_cles[1] if len(definition.attributs_cles) > 1 else None
        assert table["tri"] == attendu_tri


def test_memes_index() -> None:
    for table in data.tables_depuis_ddl():
        definition = ddl.DEFINITIONS[table["nom"]]
        attendu = [{"nom": attribut, "cle": attribut} for attribut, _ in definition.index]
        assert table["index"] == attendu


def test_meme_ttl() -> None:
    for table in data.tables_depuis_ddl():
        assert table["ttl"] == ddl.DEFINITIONS[table["nom"]].ttl


def test_journal_porte_le_ttl() -> None:
    journal = next(t for t in data.tables_depuis_ddl() if t["nom"] == "journal")
    assert journal["ttl"] == "expire_le"


def test_acces_porte_le_ttl_du_journal() -> None:
    """One retention rule: the access log expires exactly like the journal."""
    acces = next(t for t in data.tables_depuis_ddl() if t["nom"] == "acces")
    assert acces["ttl"] == "expire_le"

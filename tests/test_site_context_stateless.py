# tests/test_site_context_stateless.py
"""
Unit tests for the stateless-mode branch of cms.site_context and
init_db idempotency in db.connection.
"""
from __future__ import annotations

import pytest

from cms.site_context import (
    STATELESS,
    get_site_dict,
    invalidate_site_dict,
    load_site_dict,
)
from db.connection import init_db
from db.tables import ContentBlock, Theme


# ── Stateless mode ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_ensure_fresh_site_dict_noop_in_stateful(engine, monkeypatch):
    import cms.site_context as sc

    monkeypatch.setattr(sc, "STATELESS", False)
    old = dict(get_site_dict())
    # Mutate the DB directly — stateful mode should NOT pick it up until
    # invalidate_site_dict() is called.
    await ContentBlock.update(
        {ContentBlock.value: "Stateful Unchanged"}
    ).where(ContentBlock.key == "hero_headline")
    # ensure_fresh_site_dict is a no-op in stateful mode.
    from cms.site_context import ensure_fresh_site_dict
    await ensure_fresh_site_dict()
    assert get_site_dict()["hero_headline"] == old["hero_headline"]


@pytest.mark.asyncio
async def test_ensure_fresh_site_dict_reloads_in_stateless(engine, monkeypatch):
    import cms.site_context as sc

    monkeypatch.setattr(sc, "STATELESS", True)
    await ContentBlock.update(
        {ContentBlock.value: "Stateless Reloaded"}
    ).where(ContentBlock.key == "hero_headline")
    from cms.site_context import ensure_fresh_site_dict
    await ensure_fresh_site_dict()
    assert get_site_dict()["hero_headline"] == "Stateless Reloaded"


@pytest.mark.asyncio
async def test_invalidate_site_dict_refreshes(engine):
    await load_site_dict()
    await ContentBlock.update(
        {ContentBlock.value: "Invalidated Value"}
    ).where(ContentBlock.key == "hero_headline")
    await invalidate_site_dict()
    assert get_site_dict()["hero_headline"] == "Invalidated Value"


# ── init_db idempotency ────────────────────────────────────


@pytest.mark.asyncio
async def test_init_db_is_idempotent(engine):
    """Running init_db a second time should not duplicate seed data."""
    theme_count_before = await Theme.count()
    await init_db()
    theme_count_after = await Theme.count()
    assert theme_count_before == theme_count_after
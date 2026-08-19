"""Organization scoping.

These endpoints previously took `org_id` straight from the query string on a
router with no authentication at all, so any caller could read any
organization's assignments and roster by editing the URL. That is exactly the
boundary the organization portal exists to demonstrate, which makes it the one
thing most worth a regression test.

Every test here asserts on refusal or on absence. A test that only checks "an
org can read its own data" would have passed against the broken version.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.deps import issue
from app.routers.assignments import org_scope


def _scope(org_id, claims):
    """The suite drives coroutines with asyncio.run rather than pytest-asyncio;
    follow that so this file needs no extra plugin."""
    return asyncio.run(org_scope(org_id=org_id, claims=claims))


ORG_A = {"sub": "sanjeevani", "role": "org", "org_id": "ORG_NGO_001"}
ORG_B = {"sub": "metrocsr", "role": "org", "org_id": "ORG_CSR_002"}
ANON = {"sub": "anonymous", "role": "org", "org_id": None}


def test_scope_defaults_to_the_token_org():
    assert _scope(None, ORG_A) == "ORG_NGO_001"


def test_matching_org_id_is_allowed():
    assert _scope("ORG_NGO_001", ORG_A) == "ORG_NGO_001"


def test_another_orgs_id_is_refused():
    """The regression. Asking for someone else's org_id must 403, not silently
    return their data."""
    with pytest.raises(HTTPException) as e:
        _scope("ORG_CSR_002", ORG_A)
    assert e.value.status_code == 403


def test_each_org_is_pinned_to_its_own():
    assert _scope(None, ORG_A) != _scope(None, ORG_B)
    with pytest.raises(HTTPException):
        _scope("ORG_NGO_001", ORG_B)


def test_query_param_honoured_only_without_a_token_org():
    """The demo escape hatch: when require_auth is off, current_org yields no
    org_id and the parameter is the only source. It must still be required."""
    assert _scope("ORG_CSR_002", ANON) == "ORG_CSR_002"
    with pytest.raises(HTTPException) as e:
        _scope(None, ANON)
    assert e.value.status_code == 400


def test_org_token_carries_its_org_id():
    tok = issue("sanjeevani", "org", "ORG_NGO_001")
    from app.deps import _resolve
    claims = _resolve(tok)
    assert claims is not None
    assert claims["role"] == "org"
    assert claims["org_id"] == "ORG_NGO_001"


def test_an_admin_token_is_not_an_org_token():
    """Roles must not be interchangeable: an admin token should not satisfy an
    org dependency, or the boundary is bypassable from the other direction."""
    from app.deps import _resolve
    claims = _resolve(issue("admin", "admin"))
    assert claims is not None
    assert claims["role"] == "admin"
    assert claims.get("org_id") is None

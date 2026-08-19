"""Authentication.

Most of these assert on **refusal**. An auth test that only checks "the right
password works" would pass against a function that returns True for everything,
which is exactly the shape of bug worth catching here: `bcrypt` sat in
requirements.txt described as credential hashing and was never called once,
while every comparison ran against plaintext.
"""

from __future__ import annotations

import time

import pytest

from app import deps
from app.security import MAX_PASSWORD_BYTES, hash_password, is_hashed, verify_password


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def test_a_hash_does_not_contain_the_password():
    h = hash_password("correct horse battery staple")
    assert "correct" not in h
    assert "staple" not in h
    assert is_hashed(h)


def test_the_right_password_verifies():
    assert verify_password("s3cret-pass", hash_password("s3cret-pass"))


def test_the_wrong_password_is_refused():
    h = hash_password("s3cret-pass")
    for wrong in ("s3cret-pas", "S3cret-pass", "", "s3cret-pass ", "x"):
        assert not verify_password(wrong, h), wrong


def test_the_same_password_hashes_differently_each_time():
    """Distinct salts. Identical hashes would reveal that two accounts share a
    password."""
    assert hash_password("same") != hash_password("same")


def test_a_malformed_stored_hash_refuses_rather_than_raising():
    """One bad seed row must not turn the login endpoint into a 500."""
    for bad in ("not-a-hash", "", None, "$2b$broken", "plaintext-password"):
        assert not verify_password("anything", bad)


def test_a_plaintext_stored_value_never_verifies_against_itself():
    """The regression that matters: if a row still held a plaintext password,
    logging in with that exact password must NOT work."""
    assert not verify_password("pact-org", "pact-org")


def test_a_password_past_bcrypts_limit_is_rejected_not_truncated():
    """bcrypt silently ignores everything past 72 bytes, which would make two
    different long passwords interchangeable."""
    too_long = "a" * (MAX_PASSWORD_BYTES + 1)
    with pytest.raises(ValueError):
        hash_password(too_long)
    assert not verify_password(too_long, hash_password("a" * MAX_PASSWORD_BYTES))


def test_is_hashed_recognises_bcrypt_and_nothing_else():
    assert is_hashed(hash_password("x"))
    assert not is_hashed("pact-admin")
    assert not is_hashed(None)
    assert not is_hashed("")


# ---------------------------------------------------------------------------
# Admin credentials
# ---------------------------------------------------------------------------

def test_admin_login_accepts_the_configured_password():
    from app.config import get_settings
    deps.prepare_admin_credentials()
    s = get_settings()
    assert deps.check_admin_credentials(s.pact_admin_user, s.pact_admin_pass)


def test_admin_login_refuses_a_wrong_password():
    from app.config import get_settings
    deps.prepare_admin_credentials()
    s = get_settings()
    assert not deps.check_admin_credentials(s.pact_admin_user, "wrong")
    assert not deps.check_admin_credentials(s.pact_admin_user, "")


def test_admin_login_refuses_a_wrong_username():
    from app.config import get_settings
    deps.prepare_admin_credentials()
    s = get_settings()
    assert not deps.check_admin_credentials("root", s.pact_admin_pass)


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

def test_an_issued_token_resolves_to_its_claims():
    t = deps.issue("admin", "admin")
    claims = deps._resolve(t)
    assert claims and claims["sub"] == "admin" and claims["role"] == "admin"


def test_tokens_are_unguessable_and_unique():
    tokens = {deps.issue("admin", "admin") for _ in range(50)}
    assert len(tokens) == 50
    assert all(len(t) >= 32 for t in tokens)


def test_an_unknown_token_resolves_to_nothing():
    assert deps._resolve("not-a-real-token") is None
    assert deps._resolve(None) is None
    assert deps._resolve("") is None


def test_a_bearer_prefix_is_accepted():
    t = deps.issue("admin", "admin")
    assert deps._resolve(f"Bearer {t}") is not None


def test_a_revoked_token_stops_working():
    t = deps.issue("admin", "admin")
    assert deps.revoke(t)
    assert deps._resolve(t) is None


def test_an_expired_token_is_refused():
    t = deps.issue("admin", "admin")
    deps._TOKENS[t]["exp"] = time.time() - 1
    assert deps._resolve(t) is None


def test_a_device_session_outlives_a_portal_session():
    """A handset in a disaster must not be signed out overnight; a browser on
    a shared laptop should be."""
    assert deps.ttl_for("seeker") > deps.ttl_for("admin")
    assert deps.ttl_for("helper") == deps.ttl_for("seeker")
    assert deps.ttl_for("org") == deps.ttl_for("admin")
    assert deps.ttl_for("seeker") >= 30 * 24 * 3600


def test_ws_token_verification_is_role_scoped():
    """The bug this guards: /ws/org accepting an admin token, or worse, any."""
    admin = deps.issue("admin", "admin")
    org = deps.issue("sanjeevani", "org", "ORG_NGO_001")

    assert deps.verify_ws_token(admin, "admin") is not None
    assert deps.verify_ws_token(admin, "org") is None
    assert deps.verify_ws_token(org, "org") is not None
    assert deps.verify_ws_token(org, "admin") is None
    assert deps.verify_ws_token(None, "admin") is None
    assert deps.verify_ws_token("garbage", "admin") is None


def test_an_org_token_carries_its_org_id():
    """org_scope derives the organization from this rather than the query
    string, which is what stopped any caller reading any org's roster."""
    t = deps.issue("sanjeevani", "org", "ORG_NGO_001")
    assert deps._resolve(t)["org_id"] == "ORG_NGO_001"


def test_a_device_token_is_not_an_admin_token():
    t = deps.issue("7F3K", "seeker")
    assert deps.verify_ws_token(t, "admin") is None
    assert deps._resolve(t)["role"] == "seeker"


# ---------------------------------------------------------------------------
# Session persistence
# ---------------------------------------------------------------------------

def test_issuing_without_an_event_loop_does_not_warn_or_raise():
    """Tests and scripts call issue() with no loop running. The background
    write is skipped, and the coroutine must be closed rather than left to
    raise 'was never awaited'."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        t = deps.issue("scripted", "admin")
    assert deps._resolve(t) is not None


def test_the_persistence_task_is_held_until_it_finishes():
    """The regression this exists for.

    asyncio keeps only WEAK references to tasks, so a bare create_task() can be
    garbage-collected mid-execution. An admin session was silently never
    written while a heavier request ran alongside it, and the token then failed
    to survive a restart -- the exact failure the persistence was added to
    prevent.

    Asserting the task is *retained* is the only way to catch it; asserting
    that create_task was called would have passed against the broken version.
    """
    import asyncio

    async def go():
        started = asyncio.Event()
        finished = []

        async def slow():
            started.set()
            await asyncio.sleep(0.05)
            finished.append(True)

        deps._spawn(slow())
        await started.wait()
        # Held while in flight...
        assert len(deps._BACKGROUND) >= 1
        # ...and released once done, so the set cannot grow without bound.
        await asyncio.sleep(0.12)
        assert finished == [True]

    asyncio.run(go())


def test_a_session_issued_from_a_worker_thread_still_persists():
    """FastAPI runs `def` endpoints in a threadpool with no event loop.

    /api/v1/admin/login is one, so every admin session was silently dropped
    while the `async def` org login persisted correctly -- a difference
    invisible from either endpoint. _spawn now falls back to the loop captured
    at startup.
    """
    import asyncio

    async def go():
        deps.bind_loop()
        done = asyncio.Event()

        async def work():
            done.set()

        # Exactly what a sync endpoint does: call from a worker thread.
        await asyncio.get_running_loop().run_in_executor(
            None, lambda: deps._spawn(work()))
        await asyncio.wait_for(done.wait(), timeout=2.0)

    asyncio.run(go())


def test_finished_tasks_are_discarded_so_the_set_does_not_leak():
    import asyncio

    async def go():
        async def noop():
            return None
        before = len(deps._BACKGROUND)
        for _ in range(20):
            deps._spawn(noop())
        await asyncio.sleep(0.05)
        assert len(deps._BACKGROUND) <= before

    asyncio.run(go())

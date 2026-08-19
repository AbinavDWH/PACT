"""Firebase Cloud Messaging.

Real delivery, replacing the outbox row that used to stand in for a notification.

**Degrades rather than fails.** Without credentials this module reports itself
unavailable and `channels.push` falls back to the outbox exactly as before.
That is deliberate: a missing service-account file must not take the pipeline
down mid-demo, and a helper can still pull assignments from the list screen.

Two different Firebase files are involved and they are easy to confuse:

    google-services.json      CLIENT config, ships inside the APK, not secret.
                              Lets the app obtain a registration token.

    service-account.json      SERVER private key. Lets the backend SEND.
                              A genuine secret -- git-ignored, never committed.

Having only the first is the common half-configured state: the app registers a
token, the server has nowhere to send it, and nothing appears to be wrong.
`status()` reports which half is missing so that is visible rather than
mysterious.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_app = None
_state: dict[str, Any] = {"ready": False, "reason": "not initialised"}


def _credential_path() -> Path | None:
    """Where the service-account key lives.

    PACT_FCM_CREDENTIALS wins; otherwise the conventional location beside the
    backend package.
    """
    env = os.getenv("PACT_FCM_CREDENTIALS")
    if env:
        p = Path(env)
        return p if p.exists() else None
    for candidate in (
        Path(__file__).resolve().parents[2] / "service-account.json",
        Path(__file__).resolve().parents[2] / "firebase-service-account.json",
    ):
        if candidate.exists():
            return candidate
    return None


def init() -> dict[str, Any]:
    """Idempotent. Safe to call at startup whether or not FCM is configured."""
    global _app, _state
    if _state.get("ready"):
        return _state

    path = _credential_path()
    if path is None:
        _state = {"ready": False,
                  "reason": "no service-account key (set PACT_FCM_CREDENTIALS "
                            "or place backend/service-account.json)"}
        return _state

    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError:
        _state = {"ready": False, "reason": "firebase-admin is not installed"}
        return _state

    try:
        cred = credentials.Certificate(str(path))
        # A second init on reload would raise; reuse the existing app instead.
        try:
            _app = firebase_admin.get_app()
        except ValueError:
            _app = firebase_admin.initialize_app(cred)
        project = json.loads(path.read_text()).get("project_id")
        _state = {"ready": True, "reason": None, "project": project,
                  "credentials": str(path)}
        log.info("fcm: ready (project %s)", project)
    except Exception as e:
        log.warning("fcm: initialisation failed: %s", e)
        _state = {"ready": False, "reason": f"init failed: {e}"}
    return _state


def status() -> dict[str, Any]:
    return dict(_state)


def available() -> bool:
    return bool(_state.get("ready"))


async def send(token: str, *, title: str, body: str,
               data: dict[str, str] | None = None) -> dict[str, Any]:
    """Send one data-only message.

    Data-only, not a notification payload, so the Android handler runs in every
    app state. A notification payload is drawn by the system while the app is
    backgrounded and `onMessageReceived` never fires -- which would mean the
    app could not act on an assignment it had visibly received.
    """
    if not available():
        return {"sent": False, "reason": _state.get("reason")}
    if not token:
        return {"sent": False, "reason": "no registration token for this helper"}

    try:
        from firebase_admin import messaging
    except ImportError:
        return {"sent": False, "reason": "firebase-admin is not installed"}

    payload = {"title": title, "body": body, **{k: str(v) for k, v in (data or {}).items()}}
    msg = messaging.Message(
        token=token,
        data=payload,
        android=messaging.AndroidConfig(
            # An assignment is time-critical: it must wake a dozing device.
            priority="high",
            ttl=60 * 30,
        ),
    )
    try:
        import anyio
        message_id = await anyio.to_thread.run_sync(messaging.send, msg)
        return {"sent": True, "message_id": message_id}
    except Exception as e:
        # Distinguish dead addresses from transient failures. `Unregistered`
        # means the app was uninstalled or the token rotated; `InvalidArgument`
        # means it was never well-formed. Neither will ever start working, so
        # the caller clears them instead of retrying on every future dispatch.
        # A network blip or a quota error must NOT clear a good token.
        name = type(e).__name__
        permanent = name in ("UnregisteredError", "SenderIdMismatchError",
                             "InvalidArgumentError")
        log.warning("fcm send failed (%s): %s", name, e)
        return {"sent": False, "reason": f"{name}: {e}", "stale_token": permanent}

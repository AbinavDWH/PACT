"""Privacy tier -- A7.

The project's headline claim lives here: minimal disclosure enforced by a
deterministic field policy, never by asking a language model to be discreet
(agents.md 2.7, memory_draft.md 8).

Public surface:

    policy.GRANTS            the audience x field matrix, data only
    redact.project_event     one bus envelope -> one audience's view, or None
    redact.project_record    one database document -> one audience's view
    redact.audit             what a projection actually removed, measured
    crypto.phone_hash        the SMS join key
    crypto.encrypt/decrypt   name_enc / phone_enc at rest
"""

from app.privacy import crypto, policy, redact  # noqa: F401
from app.privacy.redact import audit, project_event, project_record  # noqa: F401

__all__ = ["crypto", "policy", "redact", "audit", "project_event", "project_record"]

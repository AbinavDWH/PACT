"""Dispatch tier -- the second half of A9.

The two dispatch paths from memory_draft.md 7.4 are implemented here as actual
routing, not as a string in a message:

    allocation owner is an ORG        -> org portal -> IT team assigns a named
                                        helper from the roster -> that helper
    allocation owner is an INDIVIDUAL -> straight to that volunteer

The difference is observable: an org allocation is created `awaiting_assignment`
and cannot be accepted until a named helper is attached; an individual
allocation is created `pending_accept` and the volunteer can accept it at once.
"""

from app.notify import channels, dispatcher  # noqa: F401
from app.notify.dispatcher import dispatch, outbox  # noqa: F401

__all__ = ["channels", "dispatcher", "dispatch", "outbox"]

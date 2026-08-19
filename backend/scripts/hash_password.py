"""Print a bcrypt hash for PACT_ADMIN_PASS or an organization's web_pass_hash.

    python scripts/hash_password.py            # prompts, nothing echoed
    python scripts/hash_password.py 'secret'   # avoid: lands in shell history

Set the resulting `$2b$...` string as PACT_ADMIN_PASS. The backend accepts
either a hash or a plaintext password there, hashing the latter at startup so
the plaintext is never compared — but a deployment should store the hash, so
the password does not sit in an env file.
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.security import hash_password  # noqa: E402


def main() -> int:
    if len(sys.argv) > 1:
        password = sys.argv[1]
        print("warning: passing a password as an argument leaves it in shell "
              "history and the process list\n", file=sys.stderr)
    else:
        password = getpass.getpass("password: ")
        if password != getpass.getpass("confirm : "):
            print("passwords do not match", file=sys.stderr)
            return 1

    if not password:
        print("empty password", file=sys.stderr)
        return 1
    if len(password) < 8:
        print("warning: shorter than 8 characters\n", file=sys.stderr)

    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

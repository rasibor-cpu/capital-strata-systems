"""One-time local bootstrap of the CSS administrator (SUPER_USER 00000).

A fresh ``css_sign_on`` user store creates 00000 with no usable password, so
no sign-in path (desktop, web, operator API, mobile) can use it until an
operator with local access to the host runs this command and chooses its
first password. There is no network equivalent. After it succeeds it refuses
to run again for the same store.

The password is read from the terminal without echo (or, for scripted local
runs, as two lines on standard input with ``--stdin``). It is never accepted
as a command-line argument (shell history / process lists), never printed,
never written anywhere except as the salted PBKDF2 hash in the user store.

Usage:
    python -m scripts.bootstrap_css_admin [--users-file PATH] [--stdin]
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard.auth.css_sign_on import (  # noqa: E402
    INITIAL_ADMIN_ID,
    USERS_FILE,
    AuthFailure,
    PasswordValidationError,
    admin_bootstrap_required,
    bootstrap_initial_admin,
    load_users,
    save_users,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-time local bootstrap of CSS administrator 00000.")
    parser.add_argument("--users-file", type=Path, default=USERS_FILE, help="css_sign_on user store (default: data/users.json)")
    parser.add_argument("--stdin", action="store_true", help="read password and confirmation as two lines from stdin")
    args = parser.parse_args(argv)

    users = load_users(args.users_file)
    if not admin_bootstrap_required(users):
        print(f"[refused] administrator {INITIAL_ADMIN_ID} is already initialized; bootstrap runs only once.")
        return 2

    if args.stdin:
        lines = sys.stdin.read().splitlines()
        password, confirm = (lines + ["", ""])[:2]
    else:
        password = getpass.getpass(f"New password for administrator {INITIAL_ADMIN_ID}: ")
        confirm = getpass.getpass("Confirm new password: ")

    try:
        bootstrap_initial_admin(users, password, confirm)
    except (AuthFailure, PasswordValidationError) as exc:
        print(f"[error] {exc}")
        return 1
    save_users(users, args.users_file)
    print(f"[ok] administrator {INITIAL_ADMIN_ID} initialized. Sign in normally from now on.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

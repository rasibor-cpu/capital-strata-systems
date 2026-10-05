"""CSS Trader Passport: persistence (Issue #102).

One JSON document per user: the in-progress session, the completed Passport and an append-only list of profile
revisions. Files are named by a salted SHA-256 of the username, never the username itself; writes are atomic
(temp file + rename) with owner-only permissions. Answer values are never logged.

The directory comes from CSS_ONBOARDING_DIR (default: data/onboarding; data/ is git-ignored by the repository's
.gitignore). Contact and financial-profile answers are stored only here, behind the same bearer-session auth
as the rest of CSS.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

log = logging.getLogger("css.onboarding.store")


def _default_dir() -> Path:
    return Path(os.getenv("CSS_ONBOARDING_DIR", "data/onboarding"))


def user_key(username: str) -> str:
    salt = os.getenv("CSS_ONBOARDING_KEY_SALT", "css-trader-passport")
    return hashlib.sha256(f"{salt}:{username.strip().lower()}".encode()).hexdigest()[:32]


class OnboardingStore:
    def __init__(self, directory: Optional[Path] = None):
        self.dir = Path(directory) if directory else _default_dir()

    def _path(self, key: str) -> Path:
        if not key or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("invalid user key")              # fail closed: no path tricks
        return self.dir / f"{key}.json"

    def load(self, key: str) -> Optional[dict]:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            log.exception("onboarding record unreadable for key %s", key[:8])
            raise

    def save(self, key: str, doc: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.dir, 0o700)
        except OSError:
            pass
        p = self._path(key)
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False, indent=1)
            os.chmod(tmp, 0o600)
            os.replace(tmp, p)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            log.exception("onboarding save failed for key %s", key[:8])
            raise

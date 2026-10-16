"""Issue a new controlled version of the CSS User Operating Manual manifest.

Usage:
  python tools/build_css_manual_manifest.py --version 1.0.0 --effective-date 2026-10-16 \
      --summary "Initial issue" --material

Recomputes the file and page SHA-256 values and appends a history entry. A version that
already exists is never rewritten. `--material` marks a change that requires every
user to accept again before new risk-taking resumes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.trading_profiles.manual import (  # noqa: E402
    ACKNOWLEDGEMENT_SHA256,
    DOCUMENT_ID,
    MANIFEST_PATH,
    MANUAL_PATH,
    sha256_text,
    split_pages,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--effective-date", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--material", action="store_true")
    args = parser.parse_args(argv)

    raw = MANUAL_PATH.read_bytes()
    file_sha = hashlib.sha256(raw).hexdigest()
    pages = [{"page_id": pid, "title": title, "sha256": sha256_text(body)}
             for pid, title, body in split_pages(raw.decode("utf-8"))]
    history = []
    if MANIFEST_PATH.exists():
        history = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")).get("history", [])
    if any(h["version"] == args.version for h in history):
        print(f"version {args.version} already issued; choose a new version", file=sys.stderr)
        return 2
    history.append({"version": args.version, "effective_date": args.effective_date, "sha256": file_sha,
                    "summary": args.summary, "material": bool(args.material)})
    manifest = {"document_id": DOCUMENT_ID, "version": args.version, "effective_date": args.effective_date,
                "sha256": file_sha, "acknowledgement_sha256": ACKNOWLEDGEMENT_SHA256, "pages": pages,
                "history": history}
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"{DOCUMENT_ID} {args.version} sha256={file_sha} pages={len(pages)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

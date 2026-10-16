"""Controlled CSS User Operating Manual, Trading Assumptions and Risk Disclosure Agreement.

The manual is a version-controlled Markdown file split into required pages by
`<!-- css-manual-page: <id> | <title> -->` markers. A JSON manifest pins its version,
effective date, SHA-256 (whole file and per page) and change history. The loader
verifies the file against the manifest and fails closed on any mismatch, so an
edited manual can never be presented or accepted under an old version.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANUAL_PATH = REPO_ROOT / "docs" / "user" / "CSS_USER_OPERATING_MANUAL.md"
MANIFEST_PATH = REPO_ROOT / "docs" / "user" / "CSS_USER_OPERATING_MANUAL.manifest.json"
DOCUMENT_ID = "CSS-UOM"

ACKNOWLEDGEMENT_TEXT = (
    "I understand that trading involves substantial risk, including the possible loss of my invested "
    "capital. I accept responsibility for the trading decisions and authorizations I make, subject to "
    "applicable law."
)
ACKNOWLEDGEMENT_SHA256 = hashlib.sha256(ACKNOWLEDGEMENT_TEXT.encode("utf-8")).hexdigest()

_PAGE_MARKER = re.compile(r"^<!-- css-manual-page: ([a-z0-9_-]+) \| (.+?) -->\s*$", re.MULTILINE)


class ManualIntegrityError(RuntimeError):
    """The manual and its manifest do not match; no acceptance is possible."""


@dataclass(frozen=True)
class ManualPage:
    page_id: str
    title: str
    markdown: str
    sha256: str


@dataclass(frozen=True)
class ControlledManual:
    document_id: str
    version: str
    effective_date: str
    sha256: str
    pages: tuple[ManualPage, ...]
    history: tuple[dict, ...]
    text: str

    def page(self, page_id: str) -> ManualPage:
        for page in self.pages:
            if page.page_id == page_id:
                return page
        raise KeyError("page_not_found")

    @property
    def page_ids(self) -> tuple[str, ...]:
        return tuple(p.page_id for p in self.pages)

    def renewal_required(self, accepted_version: str | None) -> bool:
        """True when any version after the accepted one is a material change (or it is unknown)."""
        if not accepted_version:
            return True
        versions = [h["version"] for h in self.history]
        if accepted_version not in versions:
            return True
        later = self.history[versions.index(accepted_version) + 1:]
        return any(bool(h.get("material")) for h in later)

    def describe(self) -> dict:
        return {
            "document_id": self.document_id,
            "title": "CSS User Operating Manual, Trading Assumptions and Risk Disclosure Agreement",
            "version": self.version,
            "effective_date": self.effective_date,
            "sha256": self.sha256,
            "pages": [{"page_id": p.page_id, "title": p.title, "sha256": p.sha256} for p in self.pages],
            "history": list(self.history),
            "acknowledgement_text": ACKNOWLEDGEMENT_TEXT,
            "acknowledgement_sha256": ACKNOWLEDGEMENT_SHA256,
        }


def split_pages(text: str) -> list[tuple[str, str, str]]:
    """Return (page_id, title, markdown) for each marked page, in order."""
    matches = list(_PAGE_MARKER.finditer(text))
    pages = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.end():end].replace("<!-- end-of-page -->", "").strip() + "\n"
        pages.append((match.group(1), match.group(2).strip(), body))
    return pages


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_manual(manual_path: Path = MANUAL_PATH, manifest_path: Path = MANIFEST_PATH) -> ControlledManual:
    try:
        raw = manual_path.read_bytes()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ManualIntegrityError(f"manual or manifest unreadable: {exc}") from exc
    text = raw.decode("utf-8")
    file_sha = hashlib.sha256(raw).hexdigest()
    if manifest.get("document_id") != DOCUMENT_ID:
        raise ManualIntegrityError("manifest document_id mismatch")
    if manifest.get("sha256") != file_sha:
        raise ManualIntegrityError("manual SHA-256 does not match its manifest")
    if manifest.get("acknowledgement_sha256") != ACKNOWLEDGEMENT_SHA256:
        raise ManualIntegrityError("acknowledgement text does not match the manifest")
    pages = tuple(ManualPage(pid, title, body, sha256_text(body)) for pid, title, body in split_pages(text))
    listed = [(p["page_id"], p["sha256"]) for p in manifest.get("pages", [])]
    if not pages or listed != [(p.page_id, p.sha256) for p in pages]:
        raise ManualIntegrityError("manual pages do not match the manifest")
    history = tuple(manifest.get("history") or ())
    if not history or history[-1].get("version") != manifest.get("version") or history[-1].get("sha256") != file_sha:
        raise ManualIntegrityError("manifest history does not end with the current version")
    return ControlledManual(DOCUMENT_ID, str(manifest["version"]), str(manifest["effective_date"]), file_sha,
                            pages, history, text)


@lru_cache(maxsize=1)
def current_manual() -> ControlledManual:
    return load_manual()


def _inline(text: str) -> str:
    import html as _html

    escaped = _html.escape(text, quote=True)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def render_html(markdown: str) -> str:
    """Minimal, safe Markdown subset -> HTML (everything is escaped before formatting)."""
    out: list[str] = []
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        heading = re.match(r"^(#{1,3}) (.+)$", line)
        if heading:
            level = len(heading.group(1)) + 1  # page title is h2 inside the reader
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            head, *body = rows
            out.append("<table><thead><tr>" + "".join(f'<th scope="col">{_inline(c)}</th>' for c in head) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</tbody></table>")
            continue
        for pattern, tag in ((r"^- (.+)$", "ul"), (r"^\d+\. (.+)$", "ol")):
            if re.match(pattern, line):
                items = []
                while i < len(lines) and re.match(pattern, lines[i].rstrip()):
                    items.append(f"<li>{_inline(re.match(pattern, lines[i].rstrip()).group(1))}</li>")
                    i += 1
                out.append(f"<{tag}>{''.join(items)}</{tag}>")
                break
        else:
            if line.startswith("> "):
                quote = []
                while i < len(lines) and lines[i].startswith("> "):
                    quote.append(_inline(lines[i][2:]))
                    i += 1
                out.append(f"<blockquote><p>{' '.join(quote)}</p></blockquote>")
                continue
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,3} |\||- |\d+\. |> )", lines[i]):
                para.append(_inline(lines[i].strip()))
                i += 1
            out.append(f"<p>{' '.join(para)}</p>")
            continue
    return "\n".join(out)

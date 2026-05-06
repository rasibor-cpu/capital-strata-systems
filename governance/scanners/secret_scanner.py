import os
import re
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[2]

REPORT_DIR = PROJECT_ROOT / "governance" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = REPORT_DIR / "security_findings.json"

EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",

    # archival / recovery zones
    "archive",
    "CLAUDE_REVIEW_2026_05_01",
    "CLAUDE_REVIEW_2026_05_02",

    # generated outputs
    "reports",

    # backup zones
    "backups",

    # governed secrets zone
    "keys",
}

EXCLUDED_FILES = {
    "security_findings.json",
}

SECRET_RULES = [
    {
        "label": "pem_private_key",
        "severity": "CRITICAL",
        "pattern": re.compile(
            r"-----BEGIN(?!.*PRIVATE KEY-----).*PRIVATE KEY-----"
        ),
    },
    {
        "label": "coinbase_api_key",
        "severity": "HIGH",
        "pattern": re.compile(
            r"(?i)coinbase.*(api|key|secret)"
        ),
    },
    {
        "label": "oanda_token",
        "severity": "HIGH",
        "pattern": re.compile(
            r"(?i)oanda.*(token|api|key|secret)"
        ),
    },
    {
        "label": "jwt",
        "severity": "HIGH",
        "pattern": re.compile(
            r"eyJ[a-zA-Z0-9_-]{10,}"
        ),
    },
    {
        "label": "generic_secret",
        "severity": "MEDIUM",
        "pattern": re.compile(
            r"(?i)(api[_-]?key|secret|token|password)\s*[:=]"
        ),
    },
]

FINDINGS = []


def should_skip(path: Path) -> bool:
    return any(
        part in EXCLUDED_DIRS
        for part in path.parts
    )


def scan_file(path: Path):

    # Prevent scanner from flagging itself
    if path.name == "secret_scanner.py":
        return

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )
    except Exception:
        return

    for rule in SECRET_RULES:

        matches = rule["pattern"].findall(text)

        if matches:
            FINDINGS.append({
                "type": rule["label"],
                "severity": rule["severity"],
                "file": str(path.relative_to(PROJECT_ROOT)),
                "match_count": len(matches),
            })


def summarize_findings():

    summary = {
        "CRITICAL": 0,
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0,
    }

    for finding in FINDINGS:
        sev = finding["severity"]
        summary[sev] += 1

    return summary


def main():

    print("[CSS GOVERNANCE] Secret scanner starting...")

    scanned = 0

    for root, dirs, files in os.walk(PROJECT_ROOT):

        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDED_DIRS
        ]

        for file in files:

            if file in EXCLUDED_FILES:
                continue

            path = Path(root) / file

            if should_skip(path):
                continue

            if path.suffix.lower() not in {
                ".py",
                ".env",
                ".txt",
                ".md",
                ".json",
                ".yaml",
                ".yml",
            }:
                continue

            scanned += 1
            scan_file(path)

    severity_summary = summarize_findings()

    report = {
        "generated_at": datetime.now().isoformat(),
        "project_root": str(PROJECT_ROOT),
        "files_scanned": scanned,
        "finding_count": len(FINDINGS),
        "severity_summary": severity_summary,
        "findings": FINDINGS,
    }

    OUTPUT_FILE.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    print(
        f"[SCAN COMPLETE] files_scanned={scanned}"
    )

    print(
        f"[FINDINGS] {len(FINDINGS)}"
    )

    print(
        "[SEVERITY] "
        f"critical={severity_summary['CRITICAL']} "
        f"high={severity_summary['HIGH']} "
        f"medium={severity_summary['MEDIUM']}"
    )

    print(
        f"[REPORT] {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
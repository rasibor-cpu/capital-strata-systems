import ast
import os
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[2]

REPORT_DIR = PROJECT_ROOT / "governance" / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = REPORT_DIR / "duplicate_symbols.json"

REGISTRY_FILE = (
    PROJECT_ROOT /
    "governance" /
    "registry" /
    "module_registry.json"
)

ALLOWLIST_FILE = (
    PROJECT_ROOT /
    "governance" /
    "registry" /
    "duplicate_allowlist.json"
)

EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "archive",
    "reports",
    "keys",
}

SYMBOLS = {}


def should_skip(path: Path) -> bool:
    return any(
        part in EXCLUDED_DIRS
        for part in path.parts
    )


def load_json_file(path: Path) -> dict:
    if not path.exists():
        return {}

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return {}


def normalize_path(path_value: str) -> str:
    return str(path_value).replace("/", "\\").strip()


def register_symbol(symbol_type, name, path, line_no):

    key = f"{symbol_type}:{name}"

    SYMBOLS.setdefault(key, []).append({
        "file": str(path.relative_to(PROJECT_ROOT)),
        "line": line_no,
    })


def scan_python_file(path: Path):

    try:
        source = path.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        tree = ast.parse(source)

    except Exception:
        return

    for node in ast.walk(tree):

        if isinstance(node, ast.FunctionDef):

            register_symbol(
                "FUNCTION",
                node.name,
                path,
                node.lineno
            )

        elif isinstance(node, ast.AsyncFunctionDef):

            register_symbol(
                "ASYNC_FUNCTION",
                node.name,
                path,
                node.lineno
            )

        elif isinstance(node, ast.ClassDef):

            register_symbol(
                "CLASS",
                node.name,
                path,
                node.lineno
            )


def classify_duplicate(
    symbol_name: str,
    locations: list[dict],
    registry: dict,
    allowlist: dict
) -> dict:

    allow_entry = allowlist.get(symbol_name)

    if allow_entry:

        return {
            "canonical_path": None,
            "canonical_present": True,
            "noncanonical_count": 0,
            "noncanonical_locations": [],
            "governance_status": allow_entry["status"],
            "risk": "LOW",
            "allowlist_reason": allow_entry.get(
                "reason",
                ""
            ),
        }

    registry_entry = registry.get(symbol_name)

    canonical_path = None
    canonical_present = False
    noncanonical_locations = list(locations)

    if isinstance(registry_entry, dict):

        canonical_path = normalize_path(
            registry_entry.get(
                "canonical_path",
                ""
            )
        )

        noncanonical_locations = []

        for loc in locations:

            loc_file = normalize_path(loc["file"])

            if loc_file == canonical_path:
                canonical_present = True
            else:
                noncanonical_locations.append(loc)

    if (
        canonical_path and
        canonical_present and
        noncanonical_locations
    ):

        governance_status = (
            "CANONICAL_WITH_SHADOW_DUPLICATES"
        )

        risk = "HIGH"

    elif (
        canonical_path and
        not canonical_present
    ):

        governance_status = (
            "CANONICAL_NOT_FOUND_BUT_DUPLICATES_EXIST"
        )

        risk = "HIGH"

    elif (
        canonical_path and
        canonical_present and
        not noncanonical_locations
    ):

        governance_status = "CANONICAL_ONLY"
        risk = "LOW"

    else:

        governance_status = (
            "UNREGISTERED_DUPLICATE"
        )

        risk = "MEDIUM"

    return {
        "canonical_path": canonical_path,
        "canonical_present": canonical_present,
        "noncanonical_count": len(
            noncanonical_locations
        ),
        "noncanonical_locations":
            noncanonical_locations,
        "governance_status":
            governance_status,
        "risk": risk,
    }


def build_duplicate_report(
    registry: dict,
    allowlist: dict
):

    duplicates = []

    for symbol_key, locations in SYMBOLS.items():

        if len(locations) <= 1:
            continue

        symbol_type, name = symbol_key.split(
            ":",
            1
        )

        classification = classify_duplicate(
            name,
            locations,
            registry,
            allowlist
        )

        duplicates.append({
            "symbol_type": symbol_type,
            "symbol_name": name,
            "occurrence_count": len(locations),
            "locations": locations,
            **classification,
        })

    duplicates.sort(
        key=lambda x: (
            {
                "HIGH": 3,
                "MEDIUM": 2,
                "LOW": 1
            }.get(
                x["risk"],
                0
            ),
            x["occurrence_count"],
        ),
        reverse=True,
    )

    return duplicates


def summarize_governance(
    duplicates: list[dict]
) -> dict:

    summary = {
        "HIGH": 0,
        "MEDIUM": 0,
        "LOW": 0,
    }

    for item in duplicates:

        summary[item["risk"]] = (
            summary.get(
                item["risk"],
                0
            ) + 1
        )

        status = item["governance_status"]

        summary[status] = (
            summary.get(
                status,
                0
            ) + 1
        )

    return summary


def main():

    print(
        "[CSS GOVERNANCE] "
        "Allowlist-aware duplicate scan starting..."
    )

    registry = load_json_file(
        REGISTRY_FILE
    )

    allowlist = load_json_file(
        ALLOWLIST_FILE
    )

    scanned = 0

    for root, dirs, files in os.walk(
        PROJECT_ROOT
    ):

        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDED_DIRS
        ]

        for file in files:

            path = Path(root) / file

            if should_skip(path):
                continue

            if path.suffix.lower() != ".py":
                continue

            scanned += 1

            scan_python_file(path)

    duplicates = build_duplicate_report(
        registry,
        allowlist
    )

    governance_summary = summarize_governance(
        duplicates
    )

    report = {
        "generated_at":
            datetime.now().isoformat(),

        "project_root":
            str(PROJECT_ROOT),

        "registry_file":
            str(
                REGISTRY_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),

        "allowlist_file":
            str(
                ALLOWLIST_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),

        "registry_entries":
            len(registry),

        "allowlist_entries":
            len(allowlist),

        "files_scanned":
            scanned,

        "duplicate_symbol_count":
            len(duplicates),

        "governance_summary":
            governance_summary,

        "duplicates":
            duplicates,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            report,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        f"[SCAN COMPLETE] "
        f"files_scanned={scanned}"
    )

    print(
        f"[DUPLICATES] "
        f"{len(duplicates)}"
    )

    print(
        "[GOVERNANCE] "
        f"high={governance_summary.get('HIGH', 0)} "
        f"medium={governance_summary.get('MEDIUM', 0)} "
        f"low={governance_summary.get('LOW', 0)}"
    )

    print(
        "[ALLOWLIST] "
        f"{governance_summary.get('ALLOWLISTED_SPECIALIZED_DUPLICATE', 0)} specialized "
        f"{governance_summary.get('ALLOWLISTED_ENTRYPOINT_PATTERN', 0)} entrypoint"
    )

    print(
        f"[REPORT] {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
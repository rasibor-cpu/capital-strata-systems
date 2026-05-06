import json
import py_compile
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DASHBOARD_FILE = (
    PROJECT_ROOT /
    "scripts" /
    "css_live_dashboard.py"
)

SECURITY_REPORT = (
    PROJECT_ROOT /
    "governance" /
    "reports" /
    "security_findings.json"
)

DUPLICATE_REPORT = (
    PROJECT_ROOT /
    "governance" /
    "reports" /
    "duplicate_symbols.json"
)

OUTPUT_REPORT = (
    PROJECT_ROOT /
    "governance" /
    "reports" /
    "dashboard_validation.json"
)


def load_json(path: Path):

    if not path.exists():
        return None

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return None


def validate_dashboard_exists():

    return {
        "check":
            "dashboard_exists",
        "passed":
            DASHBOARD_FILE.exists(),
        "path":
            str(DASHBOARD_FILE),
    }


def validate_dashboard_compile():

    try:

        py_compile.compile(
            str(DASHBOARD_FILE),
            doraise=True
        )

        return {
            "check":
                "dashboard_compile",
            "passed":
                True,
        }

    except Exception as e:

        return {
            "check":
                "dashboard_compile",
            "passed":
                False,
            "error":
                str(e),
        }


def validate_security_report():

    report = load_json(
        SECURITY_REPORT
    )

    if not report:

        return {
            "check":
                "security_report",
            "passed":
                False,
            "reason":
                "missing_or_invalid_report",
        }

    critical = (
        report
        .get("severity_summary", {})
        .get("CRITICAL", -1)
    )

    return {
        "check":
            "security_report",
        "passed":
            critical == 0,
        "critical_findings":
            critical,
    }


def validate_duplicate_report():

    report = load_json(
        DUPLICATE_REPORT
    )

    if not report:

        return {
            "check":
                "duplicate_report",
            "passed":
                False,
            "reason":
                "missing_or_invalid_report",
        }

    high = (
        report
        .get("governance_summary", {})
        .get("HIGH", -1)
    )

    return {
        "check":
            "duplicate_report",
        "passed":
            high <= 3,
        "high_risk_duplicates":
            high,
    }


def build_validation():

    checks = [
        validate_dashboard_exists(),
        validate_dashboard_compile(),
        validate_security_report(),
        validate_duplicate_report(),
    ]

    passed = all(
        c.get("passed", False)
        for c in checks
    )

    return {
        "generated_at":
            datetime.now().isoformat(),

        "overall_passed":
            passed,

        "checks":
            checks,
    }


def main():

    print(
        "[CSS GOVERNANCE] "
        "Dashboard validation starting..."
    )

    validation = build_validation()

    OUTPUT_REPORT.write_text(
        json.dumps(
            validation,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        "[VALIDATION] "
        f"overall_passed="
        f"{validation['overall_passed']}"
    )

    for check in validation["checks"]:

        print(
            f"[CHECK] "
            f"{check['check']} "
            f"passed={check['passed']}"
        )

    print(
        f"[REPORT] "
        f"{OUTPUT_REPORT}"
    )


if __name__ == "__main__":
    main()
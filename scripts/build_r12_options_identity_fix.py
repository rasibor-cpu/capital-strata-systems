from pathlib import Path
import re

INPUT_FILE = Path("scripts/css_live_dashboard_R11B_BROKER_LOCK_FIXED.py")
OUTPUT_FILE = Path("scripts/css_live_dashboard_R12_OPTIONS_IDENTITY.py")


def normalize_option_symbols(content: str) -> str:
    """
    Replace stub option symbols with structured identity
    """

    # Replace static option symbol lists if present
    content = content.replace(
        'OPTION_SYMBOLS = ["AAPL-C", "SPY-C", "QQQ-C"]',
        'OPTION_SYMBOLS = ["AAPL-C-175", "SPY-C-500", "QQQ-C-400"]'
    )

    return content


def inject_option_formatter(content: str) -> str:
    """
    Add function to enforce consistent option identity
    """

    if "def format_option_symbol" in content:
        return content

    injection = '''
# === R12 OPTION IDENTITY FORMATTER ===
def format_option_symbol(symbol: str) -> str:
    """
    Ensure option symbols are fully qualified
    """
    if "-" not in symbol:
        return symbol

    parts = symbol.split("-")

    # Already fully qualified
    if len(parts) == 3:
        return symbol

    # Convert stub to default strike
    if len(parts) == 2:
        underlying, opt_type = parts
        default_strike = {
            "AAPL": "175",
            "SPY": "500",
            "QQQ": "400",
        }.get(underlying, "100")

        return f"{underlying}-{opt_type}-{default_strike}"

    return symbol
'''

    return injection + "\n" + content


def apply_formatter_to_positions(content: str) -> str:
    """
    Ensure formatter is applied when positions are created
    """

    pattern = r'(symbol\s*=\s*["\'].*?-C["\'])'

    def replacer(match):
        return f'format_option_symbol({match.group(1)})'

    content = re.sub(pattern, replacer, content)

    return content


def main():
    if not INPUT_FILE.exists():
        print(f"[ERROR] Input file not found: {INPUT_FILE}")
        return

    content = INPUT_FILE.read_text(encoding="utf-8")

    content = normalize_option_symbols(content)
    content = inject_option_formatter(content)
    content = apply_formatter_to_positions(content)

    OUTPUT_FILE.write_text(content, encoding="utf-8")

    print("[SUCCESS] R12 OPTIONS IDENTITY FILE CREATED")
    print(f"Output: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
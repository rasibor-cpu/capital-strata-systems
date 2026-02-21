"""
Reverse CSV Utility
-------------------
Reverses row order while preserving header.

Usage:
    python -m tools.reverse_csv input.csv output.csv
"""

import csv
import sys


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m tools.reverse_csv input.csv output.csv")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path, "r", newline="", encoding="utf-8") as f:
        reader = list(csv.reader(f))

    if not reader:
        raise ValueError("CSV empty")

    header = reader[0]
    rows = reader[1:]

    rows.reverse()

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    print(f"Reversed CSV written to {output_path}")


if __name__ == "__main__":
    main()
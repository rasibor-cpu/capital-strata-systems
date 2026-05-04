import shutil

src = r"scripts\css_live_dashboard_PACK3B.py"
dst = r"scripts\css_live_dashboard_PACK3C.py"

# Read original file
with open(src, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
in_close_function = False

for line in lines:
    # Detect close_position start
    if line.strip().startswith("def close_position("):
        in_close_function = True
        new_lines.append(line)
        continue

    # Replace ONLY inside close_position
    if in_close_function:
        # Detect original pnl line
        if "self.realized_pnl +=" in line:
            indent = line[:len(line) - len(line.lstrip())]

            new_lines.append(indent + "# PACK 3C: TRUE PNL PIPELINE FIX\n")
            new_lines.append(indent + "self.realized_pnl += net_pnl\n")
            new_lines.append(indent + "self.current_balance += net_pnl\n")
            new_lines.append(indent + "self.mtm_realized_pnl += net_pnl  # <-- CRITICAL FIX\n")

            continue

        # Stop at return
        if "return" in line:
            new_lines.append(line)
            in_close_function = False
            continue

    new_lines.append(line)

# Write new file
with open(dst, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("PACK 3C CREATED:", dst)
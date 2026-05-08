from typing import Any, Dict, List

class PayloadDiffTool:
    """
    Compares previous and current payload snapshots to highlight missing keys,
    changed types, renamed fields, and drift risks.
    """

    @classmethod
    def compare_payloads(cls, previous: Dict[str, Any], current: Dict[str, Any], path: str = "") -> Dict[str, List[str]]:
        """
        Recursively compares two dictionaries and returns a drift report.
        """
        report: Dict[str, List[str]] = {
            "missing_keys": [],
            "new_keys": [],
            "type_changes": []
        }

        if not isinstance(previous, dict) or not isinstance(current, dict):
            if type(previous) != type(current):
                # Ignore None transitions
                if previous is not None and current is not None:
                    report["type_changes"].append(f"{path}: {type(previous).__name__} -> {type(current).__name__}")
            return report

        for key in previous:
            current_path = f"{path}.{key}" if path else key
            if key not in current:
                report["missing_keys"].append(current_path)
            else:
                prev_val = previous[key]
                curr_val = current[key]
                
                if isinstance(prev_val, dict) and isinstance(curr_val, dict):
                    sub_report = cls.compare_payloads(prev_val, curr_val, current_path)
                    report["missing_keys"].extend(sub_report["missing_keys"])
                    report["new_keys"].extend(sub_report["new_keys"])
                    report["type_changes"].extend(sub_report["type_changes"])
                elif type(prev_val) != type(curr_val):
                    # Be lenient with numeric types and None
                    if prev_val is None or curr_val is None:
                        continue
                    if isinstance(prev_val, (int, float)) and isinstance(curr_val, (int, float)):
                        continue
                        
                    type_prev = type(prev_val).__name__
                    type_curr = type(curr_val).__name__
                    report["type_changes"].append(f"{current_path}: {type_prev} -> {type_curr}")

        for key in current:
            current_path = f"{path}.{key}" if path else key
            if key not in previous:
                report["new_keys"].append(current_path)

        return report

import logging
from typing import Any, Dict
from datetime import datetime

LOGGER = logging.getLogger(__name__)

class FrontendPayloadValidator:
    """
    Validates the CSS Institutional Frontend Payload contract without exposing secrets
    or crashing the runtime. Uses defensive type checking and safe fallbacks.
    """

    REQUIRED_ROOT_KEYS = [
        "payload_version",
        "payload_schema",
        "contract_name",
        "contract_version",
        "contract_timestamp",
        "generated_at",
        "message_type",
        "sections",
        "session",
    ]

    REQUIRED_SECTIONS = [
        "account_summary",
        "positions",
        "pnl_summary",
        "risk",
        "governance",
        "market",
        "execution",
        "opportunities",
        "broker",
    ]

    def validate(self, payload: Dict[str, Any]) -> bool:
        """
        Validates the payload structure and returns True if valid.
        Logs warnings for any validation failures.
        """
        is_valid = True

        if not isinstance(payload, dict):
            LOGGER.warning("FrontendPayloadValidator: Payload is not a dictionary.")
            return False

        for key in self.REQUIRED_ROOT_KEYS:
            if key not in payload:
                LOGGER.warning(f"FrontendPayloadValidator: Missing required root key: '{key}'")
                is_valid = False

        sections = payload.get("sections")
        if not isinstance(sections, dict):
            LOGGER.warning("FrontendPayloadValidator: 'sections' is missing or not a dictionary.")
            return False

        for sec in self.REQUIRED_SECTIONS:
            if sec not in sections:
                LOGGER.warning(f"FrontendPayloadValidator: Missing required section: '{sec}'")
                is_valid = False

        # Validate types inside specific sections safely
        try:
            # Check pnl summary types
            pnl = sections.get("pnl_summary", {})
            if "realized_pnl" in pnl and not isinstance(pnl.get("realized_pnl"), (int, float, str)):
                LOGGER.warning("FrontendPayloadValidator: Invalid type for realized_pnl")
                is_valid = False

            # Check timestamp integrity
            gen_at = payload.get("generated_at")
            if gen_at and isinstance(gen_at, str):
                try:
                    # Allow Z or +00:00
                    datetime.fromisoformat(gen_at.replace("Z", "+00:00"))
                except ValueError:
                    LOGGER.warning("FrontendPayloadValidator: Invalid ISO timestamp format in generated_at")
                    is_valid = False

        except Exception as e:
            # Fail safely, catch any unexpected exceptions
            LOGGER.warning(f"FrontendPayloadValidator: Unexpected validation exception: {e}")
            is_valid = False

        return is_valid

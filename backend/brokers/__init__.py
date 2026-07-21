"""Broker package namespace for advisory adapters (Phase 178A)."""

from __future__ import annotations

from .account_balance_contract import BALANCE_FIELDS, build_broker_balance_summary

__all__ = ["BALANCE_FIELDS", "build_broker_balance_summary"]

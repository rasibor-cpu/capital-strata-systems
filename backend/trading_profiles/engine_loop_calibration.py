"""Owner-loadable calibration for EngineLoop events -> (probability, R14F signal_score).

Without an approved artifact the calibration declines every event (fail closed).
Nothing here invents scores when the strategy is disabled or unapproved.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from backend.trading_profiles.strategy_enablement import StrategyEnablement

SCHEMA = "css.trading_profiles.engine_loop_calibration.v1"
STRATEGY_MA_MOMENTUM = "engine_loop_ma_momentum_v1"


@dataclass(frozen=True)
class CalibrationArtifact:
    schema: str
    version: str
    strategy_id: str
    # probability = logistic(a + b * strength); signal_score = max(eps, c0 + c1 * strength)
    a: float
    b: float
    c0: float
    c1: float
    min_strength: float
    approved_for_routing: bool
    oos_metrics: dict[str, Any] = field(default_factory=dict)
    content_sha256: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CalibrationError(RuntimeError):
    pass


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _sha256_payload(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def save_calibration(path: Path | str, artifact: CalibrationArtifact) -> CalibrationArtifact:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = artifact.to_dict()
    body.pop("content_sha256", None)
    digest = _sha256_payload(body)
    body["content_sha256"] = digest
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return CalibrationArtifact(**body)


def load_calibration(path: Path | str) -> CalibrationArtifact:
    path = Path(path)
    if not path.is_file():
        raise CalibrationError(f"calibration_missing:{path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CalibrationError(f"calibration_unreadable:{exc}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise CalibrationError("calibration_schema_mismatch")
    stored = str(doc.get("content_sha256") or "")
    check = {k: v for k, v in doc.items() if k != "content_sha256"}
    if stored != _sha256_payload(check):
        raise CalibrationError("calibration_hash_mismatch")
    required = ("version", "strategy_id", "a", "b", "c0", "c1", "min_strength", "approved_for_routing")
    if any(k not in doc for k in required):
        raise CalibrationError("calibration_incomplete")
    for key in ("a", "b", "c0", "c1", "min_strength"):
        if not _finite(doc[key]):
            raise CalibrationError(f"calibration_param_invalid:{key}")
    return CalibrationArtifact(
        schema=SCHEMA,
        version=str(doc["version"]),
        strategy_id=str(doc["strategy_id"]),
        a=float(doc["a"]),
        b=float(doc["b"]),
        c0=float(doc["c0"]),
        c1=float(doc["c1"]),
        min_strength=float(doc["min_strength"]),
        approved_for_routing=bool(doc["approved_for_routing"]),
        oos_metrics=dict(doc.get("oos_metrics") or {}),
        content_sha256=stored,
        notes=str(doc.get("notes") or ""),
    )


def _logistic(x: float) -> float:
    if x >= 30:
        return 1.0
    if x <= -30:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def build_calibration_callable(
    artifact: CalibrationArtifact,
    *,
    enablement: StrategyEnablement | None = None,
):
    """Return a Calibration callable for CssEngineSignalBridge.engine_loop_sink."""

    def calibrate(event: Mapping[str, Any]) -> Mapping[str, Any] | None:
        if not artifact.approved_for_routing:
            return None
        if enablement is not None and not enablement.is_enabled(artifact.strategy_id):
            return None
        strength = event.get("strength")
        if not (_finite(strength) and float(strength) >= artifact.min_strength):
            return None
        s = float(strength)
        probability = min(0.99, max(0.01, _logistic(artifact.a + artifact.b * s)))
        signal_score = max(0.01, artifact.c0 + artifact.c1 * s)
        if not (_finite(probability) and _finite(signal_score) and 0 < probability < 1 and signal_score > 0):
            return None
        # Conservative quality inputs: only when OOS expectancy was positive.
        oos = artifact.oos_metrics or {}
        replay_confidence = float(oos.get("replay_confidence", 0.0) or 0.0)
        strategy_score = float(oos.get("strategy_score", 0.0) or 0.0)
        out: dict[str, Any] = {
            "probability": probability,
            "signal_score": signal_score,
            "confidence": probability,
        }
        if _finite(replay_confidence) and replay_confidence >= 0:
            out["replay_confidence"] = replay_confidence
        if _finite(strategy_score) and strategy_score >= 0:
            out["strategy_score"] = strategy_score
        return out

    return calibrate

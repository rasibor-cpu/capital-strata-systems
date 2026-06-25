import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from engine.information.alerts import get_alert_service, AlertEventType
from backend.monitoring.alert_bridge import CanonicalAlertBridge

logger = logging.getLogger(__name__)

DEFAULT_STATE_FILE = Path(__file__).resolve().parents[2] / "runtime_supervisor.json"

class RuntimeSupervisor:
    """
    Continuous Runtime Supervisor for CSS.
    Tracks uptime, completed cycles, runtime errors, broker disconnects, and alerts.
    """
    def __init__(
        self,
        state_file: str | Path = DEFAULT_STATE_FILE,
        heartbeat_timeout_seconds: int = 600,
        broker_disconnect_alert_threshold: int = 3,
        alert_service=None,
        canonical_alert_bridge: Optional[CanonicalAlertBridge] = None,
    ):
        self.state_file = Path(state_file)
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self.broker_disconnect_alert_threshold = broker_disconnect_alert_threshold
        self.alert_service = alert_service or get_alert_service()
        self.canonical_alert_bridge = canonical_alert_bridge or CanonicalAlertBridge()

        self._lock = threading.RLock()
        self.state: Dict[str, Any] = {
            "start_time": "",
            "uptime_seconds": 0,
            "cycles_completed": 0,
            "runtime_errors": 0,
            "broker_disconnects": 0,
            "recovery_attempts": 0,
            "alerts_generated": 0
        }
        
        self.last_heartbeat_time: float = time.time()
        self.last_heartbeat_data: Dict[str, Any] = {}
        
        self._watchdog_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._heartbeat_alert_fired = False

        self._load_state()
        
        with self._lock:
            if not self.state["start_time"]:
                self.state["start_time"] = datetime.now(timezone.utc).isoformat()
                self._save_state()

    def _load_state(self) -> None:
        try:
            if self.state_file.exists():
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.state.update(data)
        except Exception as e:
            logger.error(f"Failed to load RuntimeSupervisor state: {e}")

    def _save_state(self) -> None:
        try:
            # Recompute uptime before saving
            if self.state.get("start_time"):
                try:
                    start = datetime.fromisoformat(self.state["start_time"])
                    now = datetime.now(timezone.utc)
                    if now.tzinfo is None:
                        # Fallback for Python versions or unaware strings
                        now = now.replace(tzinfo=timezone.utc)
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                        
                    uptime = (now - start).total_seconds()
                    self.state["uptime_seconds"] = int(max(0, uptime))
                except Exception:
                    pass
            
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save RuntimeSupervisor state: {e}")

    def start_watchdog(self) -> None:
        """Starts the background thread to monitor engine staleness."""
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            return
            
        self._stop_event.clear()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name="RuntimeSupervisorWatchdog",
            daemon=True
        )
        self.last_heartbeat_time = time.time()
        self._heartbeat_alert_fired = False
        self._watchdog_thread.start()

    def stop_watchdog(self) -> None:
        self._stop_event.set()
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=2.0)

    def _watchdog_loop(self) -> None:
        while not self._stop_event.is_set():
            time.sleep(0.5)
            
            with self._lock:
                elapsed = time.time() - self.last_heartbeat_time
                if elapsed > self.heartbeat_timeout_seconds and not self._heartbeat_alert_fired:
                    self._dispatch_alert(
                        AlertEventType.ENGINE_HEARTBEAT_LOST,
                        f"Engine heartbeat lost! Last seen {int(elapsed)} seconds ago."
                    )
                    try:
                        self.canonical_alert_bridge.record_heartbeat_stale(
                            source="runtime_supervisor",
                            message=f"Engine heartbeat stale ({int(elapsed)} seconds)",
                            details={
                                "elapsed_seconds": int(elapsed),
                                "heartbeat_timeout_seconds": int(self.heartbeat_timeout_seconds),
                            },
                            dedupe_key=(
                                f"HEARTBEAT_STALE:runtime_supervisor:"
                                f"{int(elapsed)}:{int(self.heartbeat_timeout_seconds)}"
                            ),
                        )
                    except Exception:
                        pass
                    self._heartbeat_alert_fired = True

    def _dispatch_alert(self, event_type: AlertEventType, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        try:
            with self._lock:
                self.state["alerts_generated"] += 1
                self._save_state()
            self.alert_service.dispatch_alert(event_type, message, context)
        except Exception as e:
            logger.error(f"RuntimeSupervisor failed to dispatch alert: {e}")

    def record_cycle(self, equity: float, broker_mode: str, engine_mode: str) -> None:
        try:
            with self._lock:
                self.state["cycles_completed"] += 1
                self.last_heartbeat_time = time.time()
                self._heartbeat_alert_fired = False
                
                self.last_heartbeat_data = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "cycle_number": self.state["cycles_completed"],
                    "equity": equity,
                    "broker_mode": broker_mode,
                    "engine_mode": engine_mode
                }
                
                self._save_state()
        except Exception as e:
            logger.error(f"RuntimeSupervisor record_cycle failed: {e}")

    def record_error(self, error_message: str) -> None:
        try:
            with self._lock:
                self.state["runtime_errors"] += 1
                runtime_errors = int(self.state["runtime_errors"])
                self._save_state()

            try:
                self.canonical_alert_bridge.record_runtime_failure(
                    source="runtime_supervisor",
                    message=f"Runtime error: {error_message}",
                    details={
                        "error_message": str(error_message),
                        "runtime_errors": runtime_errors,
                    },
                    dedupe_key=(
                        f"RUNTIME_FAILURE:runtime_supervisor:"
                        f"{error_message}:{runtime_errors}"
                    ),
                )
            except Exception:
                pass
        except Exception as e:
            logger.error(f"RuntimeSupervisor record_error failed: {e}")

    def record_broker_disconnect(self, broker_name: str, message: str) -> None:
        try:
            with self._lock:
                self.state["broker_disconnects"] += 1
                current_disconnects = self.state["broker_disconnects"]
                self._save_state()
                
            if current_disconnects >= self.broker_disconnect_alert_threshold:
                self._dispatch_alert(
                    AlertEventType.BROKER_CONNECTION_UNSTABLE,
                    f"Repeated broker disconnects ({current_disconnects}): {broker_name} {message}",
                    {"broker": broker_name, "disconnects": current_disconnects}
                )
                try:
                    self.canonical_alert_bridge.record_broker_disconnect(
                        source="runtime_supervisor",
                        message=(
                            f"Repeated broker disconnects ({current_disconnects}): "
                            f"{broker_name} {message}"
                        ),
                        details={
                            "broker": str(broker_name),
                            "disconnects": int(current_disconnects),
                        },
                        dedupe_key=(
                            f"BROKER_DISCONNECT:runtime_supervisor:"
                            f"{broker_name}:{current_disconnects}"
                        ),
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"RuntimeSupervisor record_broker_disconnect failed: {e}")

    def record_recovery_attempt(self, context_message: str) -> None:
        try:
            with self._lock:
                self.state["recovery_attempts"] += 1
                self._save_state()
                
            self._dispatch_alert(
                AlertEventType.RUNTIME_RECOVERY_ATTEMPT,
                f"Runtime recovery attempt: {context_message}",
                {"context": context_message}
            )

            try:
                self.canonical_alert_bridge.record_supervisor_recovery(
                    source="runtime_supervisor",
                    message=f"Runtime recovery attempt: {context_message}",
                    details={"context": str(context_message)},
                    dedupe_key=(
                        f"SUPERVISOR_RECOVERY:runtime_supervisor:{context_message}:"
                        f"{self.state.get('recovery_attempts', 0)}"
                    ),
                )
            except Exception:
                pass
        except Exception as e:
            logger.error(f"RuntimeSupervisor record_recovery_attempt failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Returns a snapshot of the runtime stats for dashboard display."""
        try:
            with self._lock:
                # Force uptime recalculation
                self._save_state()
                return dict(self.state)
        except Exception:
            return self.state

    def get_latest_heartbeat(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self.last_heartbeat_data)

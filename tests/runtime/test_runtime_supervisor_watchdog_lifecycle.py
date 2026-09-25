from unittest.mock import MagicMock

from backend.runtime.runtime_supervisor import RuntimeSupervisor


def _supervisor(tmp_path, *, timeout=600):
    return RuntimeSupervisor(
        state_file=tmp_path / "runtime_supervisor.json",
        alert_service=MagicMock(),
        heartbeat_timeout_seconds=timeout,
    )


def test_watchdog_is_not_armed_on_construction(tmp_path):
    supervisor = _supervisor(tmp_path)

    thread = supervisor._watchdog_thread

    assert thread is None or not thread.is_alive()


def test_first_engine_cycle_arms_watchdog(tmp_path, monkeypatch):
    supervisor = _supervisor(tmp_path)
    start_watchdog = MagicMock()

    monkeypatch.setattr(supervisor, "start_watchdog", start_watchdog)

    supervisor.record_cycle(
        equity=1000.0,
        broker_mode="paper",
        engine_mode="SAFE",
    )

    start_watchdog.assert_called_once_with()
    assert supervisor.state["cycles_completed"] == 1


def test_running_watchdog_is_not_rearmed_on_every_cycle(tmp_path, monkeypatch):
    supervisor = _supervisor(tmp_path)

    class AliveThread:
        @staticmethod
        def is_alive():
            return True

    supervisor._watchdog_thread = AliveThread()

    start_watchdog = MagicMock()
    monkeypatch.setattr(supervisor, "start_watchdog", start_watchdog)

    supervisor.record_cycle(
        equity=1000.0,
        broker_mode="paper",
        engine_mode="SAFE",
    )

    start_watchdog.assert_not_called()
    assert supervisor.state["cycles_completed"] == 1

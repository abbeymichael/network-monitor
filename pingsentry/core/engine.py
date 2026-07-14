"""
The monitoring engine: owns a background thread that periodically checks
every enabled server (each on its own configurable interval), decides when
a status change / alert is warranted, and dispatches SMS notifications.

The engine is UI-agnostic: it communicates upward purely via callbacks /
a thread-safe queue of events so any front-end (customtkinter, CLI, etc.)
can subscribe.
"""
from __future__ import annotations

import queue
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from .checker import check_target, CheckResult
from .models import Server, ServerStatus, SmsProviderConfig, AppSettings, LogEntry
from . import storage
from . import sms_providers

TICK_SECONDS = 1.0


def _now() -> datetime:
    return datetime.now()


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _today_marker() -> str:
    return _now().strftime("%Y-%m-%d")


class EngineEvent:
    """Simple event envelope pushed onto the engine's outbound queue."""

    def __init__(self, kind: str, **payload):
        self.kind = kind          # "status_change" | "check" | "log" | "alert_sent"
        self.payload = payload


class MonitorEngine:
    def __init__(self):
        self.servers: Dict[str, Server] = {}
        self._order: List[str] = []
        self.sms_config: SmsProviderConfig = storage.load_sms_config()
        self.settings: AppSettings = storage.load_settings()

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()  # global pause switch
        self.events: "queue.Queue[EngineEvent]" = queue.Queue()
        self._lock = threading.RLock()
        self._next_due: Dict[str, float] = {}

        self._load_servers()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_servers(self):
        for s in storage.load_servers():
            self.servers[s.id] = s
            self._order.append(s.id)

    def persist_servers(self):
        with self._lock:
            ordered = [self.servers[i] for i in self._order if i in self.servers]
            storage.save_servers(ordered)

    def reload_sms_config(self):
        self.sms_config = storage.load_sms_config()

    def reload_settings(self):
        self.settings = storage.load_settings()

    # ------------------------------------------------------------------
    # CRUD for servers
    # ------------------------------------------------------------------

    def list_servers(self) -> List[Server]:
        with self._lock:
            return [self.servers[i] for i in self._order if i in self.servers]

    def get_server(self, server_id: str) -> Optional[Server]:
        return self.servers.get(server_id)

    def add_server(self, server: Server):
        with self._lock:
            self.servers[server.id] = server
            self._order.append(server.id)
            self._next_due[server.id] = time.monotonic()  # check ASAP
            self.persist_servers()

    def update_server(self, server: Server):
        with self._lock:
            self.servers[server.id] = server
            self.persist_servers()

    def remove_server(self, server_id: str):
        with self._lock:
            self.servers.pop(server_id, None)
            self._next_due.pop(server_id, None)
            if server_id in self._order:
                self._order.remove(server_id)
            self.persist_servers()

    def check_now(self, server_id: str):
        """Force an immediate check on the next tick."""
        self._next_due[server_id] = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive() and not self._pause_event.is_set()

    def start(self):
        if self._thread and self._thread.is_alive():
            self._pause_event.clear()
            return
        self._stop_event.clear()
        self._pause_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="PingSentry-Engine")
        self._thread.start()

    def pause(self):
        self._pause_event.set()

    def resume(self):
        self._pause_event.clear()

    def stop(self):
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    def _run_loop(self):
        while not self._stop_event.is_set():
            if not self._pause_event.is_set():
                self._tick()
            time.sleep(TICK_SECONDS)

    def _tick(self):
        now_mono = time.monotonic()
        with self._lock:
            due_ids = []
            for sid in list(self._order):
                server = self.servers.get(sid)
                if not server or not server.enabled:
                    continue
                due_at = self._next_due.get(sid, 0)
                if now_mono >= due_at:
                    due_ids.append(sid)

        for sid in due_ids:
            server = self.servers.get(sid)
            if not server:
                continue
            self._next_due[sid] = now_mono + max(5, server.interval_seconds)
            # Run the actual network check off the lock so slow checks
            # don't block other servers' scheduling.
            threading.Thread(target=self._check_one, args=(sid,), daemon=True).start()

    # ------------------------------------------------------------------
    # Single check + alert decision logic
    # ------------------------------------------------------------------

    def _check_one(self, server_id: str):
        with self._lock:
            server = self.servers.get(server_id)
            if not server:
                return
            # snapshot values needed for the network call
            address = server.address
            method = server.check_method
            port = server.port
            timeout_seconds = server.timeout_seconds
            http_url = server.http_url
            http_method = server.http_method
            http_expected_status_min = server.http_expected_status_min
            http_expected_status_max = server.http_expected_status_max
            http_body_contains = server.http_body_contains
            http_verify_tls = server.http_verify_tls
            dns_record_type = server.dns_record_type
            dns_resolver = server.dns_resolver
            dns_expected_value = server.dns_expected_value

        result = check_target(
            address, method, port=port, timeout_seconds=timeout_seconds,
            http_url=http_url, http_method=http_method,
            http_expected_status_min=http_expected_status_min,
            http_expected_status_max=http_expected_status_max,
            http_body_contains=http_body_contains, http_verify_tls=http_verify_tls,
            dns_record_type=dns_record_type, dns_resolver=dns_resolver,
            dns_expected_value=dns_expected_value,
        )

        with self._lock:
            server = self.servers.get(server_id)
            if not server:
                return
            self._apply_result(server, result)
            self.persist_servers()

        self._emit(EngineEvent("check", server_id=server_id))

    def _apply_result(self, server: Server, result: CheckResult):
        now = _now()
        server.last_checked_at = _iso(now)
        if result.success:
            server.last_latency_ms = result.latency_ms

        previous_status = server.status

        if result.success:
            server.consecutive_failures = 0
            server.consecutive_successes += 1
        else:
            server.consecutive_successes = 0
            server.consecutive_failures += 1

        # Determine transitions
        if result.success:
            if server.status == ServerStatus.UNKNOWN.value:
                server.status = ServerStatus.UP.value
                server.last_status_change_at = _iso(now)
                self._log(server, "info", f"{server.name} initial check succeeded (UP).")
                self._emit(EngineEvent("status_change", server_id=server.id, status="up"))
            elif server.status != ServerStatus.UP.value:
                # Recovered from DOWN
                was_down = server.status == ServerStatus.DOWN.value
                server.status = ServerStatus.UP.value
                server.last_status_change_at = _iso(now)
                server.alerts_sent_this_incident = 0
                self._log(server, "success", f"{server.name} is back UP.")
                self._emit(EngineEvent("status_change", server_id=server.id, status="up"))
                if was_down and server.notify_on_recovery:
                    self._send_alert(server, recovery=True)
        else:
            if server.consecutive_failures >= max(1, server.failures_before_alert):
                if server.status != ServerStatus.DOWN.value:
                    server.status = ServerStatus.DOWN.value
                    server.last_status_change_at = _iso(now)
                    server.alerts_sent_this_incident = 0
                    self._log(server, "error", f"{server.name} is DOWN ({result.error or 'no response'}).")
                    self._emit(EngineEvent("status_change", server_id=server.id, status="down"))
                    self._send_alert(server, recovery=False)
                else:
                    # Still down - consider a repeat/escalation alert
                    self._log(server, "warning", f"{server.name} still down ({result.error or 'no response'}).")
                    self._maybe_resend_alert(server)
            else:
                self._log(
                    server,
                    "warning",
                    f"{server.name} check failed ({result.error or 'no response'}) "
                    f"[{server.consecutive_failures}/{server.failures_before_alert}]",
                )

    # ------------------------------------------------------------------
    # Alerting
    # ------------------------------------------------------------------

    def _daily_cap_remaining(self, server: Server) -> int:
        today = _today_marker()
        if server.alerts_day_marker != today:
            server.alerts_day_marker = today
            server.alerts_sent_today = 0
        return max(0, server.daily_alert_cap - server.alerts_sent_today)

    def _in_quiet_hours(self) -> bool:
        s = self.settings
        if not s.quiet_hours_enabled:
            return False
        try:
            now_t = _now().time()
            start_h, start_m = map(int, s.quiet_hours_start.split(":"))
            end_h, end_m = map(int, s.quiet_hours_end.split(":"))
            start = now_t.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
            end = now_t.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
            now_only = now_t
            if start <= end:
                return start <= now_only <= end
            # Overnight range e.g. 22:00 -> 07:00
            return now_only >= start or now_only <= end
        except (ValueError, AttributeError):
            return False

    def _maybe_resend_alert(self, server: Server):
        if server.alerts_sent_this_incident >= max(1, server.max_alerts_per_incident):
            return
        if server.last_alert_sent_at:
            try:
                last = datetime.strptime(server.last_alert_sent_at, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                last = None
            if last and _now() - last < timedelta(minutes=max(1, server.resend_interval_minutes)):
                return
        self._send_alert(server, recovery=False)

    def _send_alert(self, server: Server, recovery: bool):
        remaining = self._daily_cap_remaining(server)
        if not recovery and remaining <= 0:
            self._log(server, "warning", f"Daily alert cap reached for {server.name}; SMS suppressed.")
            return
        if self._in_quiet_hours() and not recovery:
            self._log(server, "info", f"Quiet hours active; suppressing DOWN SMS for {server.name} (still logged).")
            return

        if recovery:
            message = (
                f"[PingSentry] RECOVERED: '{server.name}' ({server.address}) is back UP "
                f"as of {_iso(_now())}."
            )
        else:
            message = (
                f"[PingSentry] ALERT: '{server.name}' ({server.address}) appears DOWN "
                f"since {server.last_status_change_at}. Attempt "
                f"{server.alerts_sent_this_incident + 1}/{server.max_alerts_per_incident}."
            )

        def _worker():
            ok, info = sms_providers.send_sms(self.sms_config, message)
            with self._lock:
                srv = self.servers.get(server.id)
                if srv:
                    if not recovery:
                        srv.alerts_sent_this_incident += 1
                        srv.alerts_sent_today += 1
                    srv.last_alert_sent_at = _iso(_now())
                    self.persist_servers()
            level = "success" if ok else "error"
            self._log(server, level, f"SMS {'sent' if ok else 'FAILED'} for {server.name}: {info}")
            self._emit(EngineEvent("alert_sent", server_id=server.id, success=ok, info=info, recovery=recovery))

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Logging / eventing
    # ------------------------------------------------------------------

    def _log(self, server: Server, level: str, message: str):
        entry = LogEntry(
            timestamp=_iso(_now()),
            server_id=server.id,
            server_name=server.name,
            level=level,
            message=message,
        )
        storage.append_log(entry)
        self._emit(EngineEvent("log", entry=entry.__dict__))

    def _emit(self, event: EngineEvent):
        self.events.put(event)

    def drain_events(self) -> List[EngineEvent]:
        out = []
        try:
            while True:
                out.append(self.events.get_nowait())
        except queue.Empty:
            pass
        return out

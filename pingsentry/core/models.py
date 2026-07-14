"""
Data models for PingSentry.

Everything is plain-dataclass based so it can be trivially serialised
to / from JSON for persistence.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any


class CheckMethod(str, Enum):
    PING = "ping"          # ICMP echo
    TCP_PORT = "tcp_port"  # TCP connect() check
    HTTP = "http"          # HTTP/HTTPS request (websites & APIs)
    DNS = "dns"            # DNS lookup (A/AAAA/CNAME/MX/TXT/NS...)


class ServerStatus(str, Enum):
    UNKNOWN = "unknown"
    UP = "up"
    DOWN = "down"
    PAUSED = "paused"


@dataclass
class Server:
    """A single monitored target (server / device / website)."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    name: str = "New Server"
    address: str = ""                       # IP or domain
    check_method: CheckMethod = CheckMethod.PING
    port: int = 443                         # used when check_method == TCP_PORT

    # HTTP/HTTPS check options (used when check_method == HTTP)
    http_url: str = ""                      # full URL, e.g. https://example.com/health
    http_method: str = "GET"                # GET | HEAD | POST
    http_expected_status_min: int = 200     # inclusive lower bound of "healthy" status codes
    http_expected_status_max: int = 399     # inclusive upper bound of "healthy" status codes
    http_body_contains: str = ""            # optional substring the response body must contain
    http_verify_tls: bool = True            # verify SSL certificates

    # DNS lookup check options (used when check_method == DNS)
    dns_record_type: str = "A"              # A | AAAA | CNAME | MX | TXT | NS
    dns_resolver: str = ""                  # optional custom DNS server IP; blank = system default
    dns_expected_value: str = ""            # optional substring the resolved record(s) must contain

    interval_seconds: int = 60              # how often to check
    timeout_seconds: int = 5                # per-attempt timeout
    failures_before_alert: int = 2          # consecutive failed checks before "down"
    enabled: bool = True
    notes: str = ""

    # Escalation / re-notification behaviour
    max_alerts_per_incident: int = 5        # cap successive "still down" SMS per outage
    resend_interval_minutes: int = 30       # gap between repeat "still down" SMS
    daily_alert_cap: int = 2                # hard cap of down-alerts/day for this server
    notify_on_recovery: bool = True

    # Runtime state (not usually edited by user, persisted for continuity)
    status: str = ServerStatus.UNKNOWN.value
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_checked_at: Optional[str] = None
    last_status_change_at: Optional[str] = None
    last_latency_ms: Optional[float] = None
    alerts_sent_this_incident: int = 0
    last_alert_sent_at: Optional[str] = None
    alerts_sent_today: int = 0
    alerts_day_marker: Optional[str] = None  # yyyy-mm-dd the daily counter belongs to

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["check_method"] = self.check_method.value if isinstance(self.check_method, CheckMethod) else self.check_method
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Server":
        d = dict(d)
        method = d.get("check_method", CheckMethod.PING.value)
        try:
            d["check_method"] = CheckMethod(method)
        except ValueError:
            d["check_method"] = CheckMethod.PING
        # drop unknown keys gracefully (forward/backward compatibility)
        valid_keys = set(Server.__dataclass_fields__.keys())
        filtered = {k: v for k, v in d.items() if k in valid_keys}
        return Server(**filtered)


@dataclass
class SmsProviderConfig:
    """Holds credentials + config for the chosen SMS gateway."""

    provider: str = "twilio"   # twilio | vonage | textbelt | txtconnect | custom | none
    # Common
    from_number: str = ""
    to_numbers: List[str] = field(default_factory=list)

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""

    # Vonage / Nexmo
    vonage_api_key: str = ""
    vonage_api_secret: str = ""

    # Textbelt (simple key-based)
    textbelt_api_key: str = ""

    # TxtConnect (https://txtconnect.net) - Bearer-token JSON API
    txtconnect_api_secret: str = ""
    txtconnect_endpoint: str = "https://api.txtconnect.net/dev/api/sms/send"
    txtconnect_unicode: bool = False

    # ---- Custom provider: fully configurable generic HTTP SMS gateway ----
    webhook_url: str = ""
    webhook_method: str = "POST"                 # GET | POST | PUT | PATCH
    webhook_content_type: str = "auto"            # auto | json | form

    # Authentication
    webhook_auth_type: str = "none"               # none | bearer | basic | api_key_header | api_key_query
    webhook_auth_token: str = ""                  # bearer token / api key value
    webhook_auth_header_name: str = "Authorization"  # header name for bearer/api_key_header
    webhook_auth_query_name: str = "api_key"      # query param name for api_key_query
    webhook_basic_username: str = ""
    webhook_basic_password: str = ""

    # Extra headers / query params (JSON object strings, {to}/{message}/{from} substituted)
    webhook_headers: Dict[str, str] = field(default_factory=dict)
    webhook_query_params: Dict[str, str] = field(default_factory=dict)

    # Body template - {to}, {message}, {from} placeholders substituted.
    # Sent as JSON if it parses as JSON (or content-type forces json),
    # otherwise sent as an application/x-www-form-urlencoded body.
    webhook_body_template: str = '{"to": "{to}", "message": "{message}", "from": "{from}"}'

    # Success detection
    webhook_success_check: str = "status_code"    # status_code | json_field
    webhook_success_json_path: str = ""           # dotted path, e.g. "data.status"
    webhook_success_json_value: str = ""          # expected value (string compare)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SmsProviderConfig":
        valid_keys = set(SmsProviderConfig.__dataclass_fields__.keys())
        filtered = {k: v for k, v in (d or {}).items() if k in valid_keys}
        return SmsProviderConfig(**filtered)


@dataclass
class AppSettings:
    theme: str = "dark"           # dark | light | system
    accent_color: str = "blue"    # blue | green | dark-blue
    start_minimized: bool = False
    minimize_to_tray: bool = True
    launch_monitoring_on_start: bool = True
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "07:00"
    sound_alerts: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "AppSettings":
        valid_keys = set(AppSettings.__dataclass_fields__.keys())
        filtered = {k: v for k, v in (d or {}).items() if k in valid_keys}
        return AppSettings(**filtered)


@dataclass
class LogEntry:
    timestamp: str
    server_id: str
    server_name: str
    level: str          # info | warning | error | success
    message: str

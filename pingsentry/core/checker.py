"""
Low level "is it alive" checks.

Four strategies are supported, so PingSentry can monitor almost anything:

  * PING      - real ICMP echo request, using the system `ping` binary
                (works cross-platform without needing raw-socket / admin
                privileges, unlike Python's raw socket ICMP).
  * TCP_PORT  - open a TCP connection to a specific port (e.g. 80, 443,
                22, 3306...). This is what you want when ICMP is filtered
                but the service itself is reachable.
  * HTTP      - issue an HTTP/HTTPS request and validate the status code
                (and optionally response body content). Best for websites
                and APIs, where "the port is open" isn't the same as "the
                application is actually healthy".
  * DNS       - resolve a DNS record (A/AAAA/CNAME/MX/TXT/NS) for a
                hostname, optionally against a specific resolver and/or
                validating the resolved value contains an expected string.
                Useful for monitoring domain/DNS health independently of
                the service itself.
"""
from __future__ import annotations

import platform
import re
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

import requests

from .models import CheckMethod


@dataclass
class CheckResult:
    success: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


_IS_WINDOWS = platform.system().lower() == "windows"


def _silent_subprocess_kwargs() -> dict:
    """Return kwargs that stop a console window from flashing on screen.

    On Windows, shelling out to ``ping`` normally spawns a visible console
    window (a black box that flickers open/closed on every single check).
    Passing ``CREATE_NO_WINDOW`` (and a hidden STARTUPINFO) suppresses it so
    monitoring stays completely silent on the user's PC. No-op elsewhere.
    """
    kwargs: dict = {}
    if not _IS_WINDOWS:
        return kwargs
    # CREATE_NO_WINDOW = 0x08000000 — prevents any console window.
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    kwargs["creationflags"] = creationflags
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = si
    except (AttributeError, Exception):  # STARTUPINFO only exists on Windows
        pass
    return kwargs


def _run_ping(address: str, timeout_seconds: int) -> CheckResult:
    """Shell out to the system ping utility (1 echo, bounded timeout)."""
    timeout_seconds = max(1, int(timeout_seconds))
    if _IS_WINDOWS:
        # -n count, -w timeout(ms)
        cmd = ["ping", "-n", "1", "-w", str(timeout_seconds * 1000), address]
    else:
        # -c count, -W timeout(seconds) (Linux). macOS uses -t for ttl and
        # -W in ms; we still keep it simple, GNU ping is the common case.
        cmd = ["ping", "-c", "1", "-W", str(timeout_seconds), address]

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds + 2,
            **_silent_subprocess_kwargs(),
        )
    except subprocess.TimeoutExpired:
        return CheckResult(success=False, error="ping timed out")
    except FileNotFoundError:
        return CheckResult(success=False, error="ping utility not found on this system")
    except OSError as e:
        return CheckResult(success=False, error=str(e))

    elapsed_ms = (time.monotonic() - start) * 1000
    output = (proc.stdout or b"").decode(errors="ignore") + (proc.stderr or b"").decode(errors="ignore")

    if proc.returncode == 0:
        latency = _extract_latency_ms(output)
        return CheckResult(success=True, latency_ms=latency if latency is not None else round(elapsed_ms, 1))

    # Non-zero return code -> unreachable / host down / packet loss etc.
    reason = "host unreachable"
    if "100% packet loss" in output or "0 received" in output:
        reason = "100% packet loss"
    elif "Unknown host" in output or "could not find host" in output or "Name or service not known" in output:
        reason = "DNS resolution failed"
    return CheckResult(success=False, error=reason)


_LATENCY_RE = re.compile(r"time[=<]([\d.]+)\s*ms", re.IGNORECASE)


def _extract_latency_ms(ping_output: str) -> Optional[float]:
    m = _LATENCY_RE.search(ping_output)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _run_tcp_check(address: str, port: int, timeout_seconds: int) -> CheckResult:
    """Attempt a raw TCP connect() to address:port."""
    start = time.monotonic()
    try:
        with socket.create_connection((address, int(port)), timeout=max(1, timeout_seconds)):
            elapsed_ms = (time.monotonic() - start) * 1000
            return CheckResult(success=True, latency_ms=round(elapsed_ms, 1))
    except socket.gaierror:
        return CheckResult(success=False, error="DNS resolution failed")
    except (socket.timeout, TimeoutError):
        return CheckResult(success=False, error=f"connection to port {port} timed out")
    except ConnectionRefusedError:
        return CheckResult(success=False, error=f"connection refused on port {port}")
    except OSError as e:
        return CheckResult(success=False, error=str(e))


def _run_http_check(
    url: str,
    method: str = "GET",
    timeout_seconds: int = 5,
    expected_status_min: int = 200,
    expected_status_max: int = 399,
    body_contains: str = "",
    verify_tls: bool = True,
) -> CheckResult:
    """Issue an HTTP/HTTPS request and validate status code + optional body content."""
    url = (url or "").strip()
    if not url:
        return CheckResult(success=False, error="no URL configured")
    if "://" not in url:
        url = "https://" + url

    method = (method or "GET").upper()
    start = time.monotonic()
    try:
        resp = requests.request(
            method, url,
            timeout=max(1, timeout_seconds),
            allow_redirects=True,
            verify=verify_tls,
            headers={"User-Agent": "PingSentry-Monitor/1.0"},
        )
        elapsed_ms = (time.monotonic() - start) * 1000
    except requests.exceptions.SSLError as e:
        return CheckResult(success=False, error=f"SSL error: {_short(str(e))}")
    except requests.exceptions.ConnectionError as e:
        return CheckResult(success=False, error=f"connection failed: {_short(str(e))}")
    except requests.exceptions.Timeout:
        return CheckResult(success=False, error="request timed out")
    except requests.exceptions.RequestException as e:
        return CheckResult(success=False, error=_short(str(e)))

    if not (expected_status_min <= resp.status_code <= expected_status_max):
        return CheckResult(
            success=False,
            latency_ms=round(elapsed_ms, 1),
            error=f"unexpected HTTP status {resp.status_code} (expected {expected_status_min}-{expected_status_max})",
        )

    if body_contains:
        try:
            text = resp.text
        except Exception:
            text = ""
        if body_contains not in text:
            return CheckResult(
                success=False,
                latency_ms=round(elapsed_ms, 1),
                error=f"response body did not contain expected text ({body_contains!r})",
            )

    return CheckResult(success=True, latency_ms=round(elapsed_ms, 1))


def _short(text: str, limit: int = 160) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text[:limit] + ("..." if len(text) > limit else "")


def _run_dns_check(
    hostname: str,
    record_type: str = "A",
    timeout_seconds: int = 5,
    resolver_address: str = "",
    expected_value: str = "",
) -> CheckResult:
    """Resolve a DNS record for `hostname` and optionally validate its value."""
    hostname = (hostname or "").strip()
    if not hostname:
        return CheckResult(success=False, error="no hostname configured")

    record_type = (record_type or "A").upper()
    start = time.monotonic()
    try:
        import dns.resolver  # lazy import - optional dependency

        resolver = dns.resolver.Resolver()
        resolver.lifetime = max(1, timeout_seconds)
        resolver.timeout = max(1, timeout_seconds)
        if resolver_address:
            resolver.nameservers = [resolver_address]

        answer = resolver.resolve(hostname, record_type)
        values = [str(r).rstrip(".") for r in answer]
        elapsed_ms = (time.monotonic() - start) * 1000

        if not values:
            return CheckResult(success=False, latency_ms=round(elapsed_ms, 1), error="no records returned")

        if expected_value and not any(expected_value in v for v in values):
            return CheckResult(
                success=False,
                latency_ms=round(elapsed_ms, 1),
                error=f"resolved value(s) {values} did not contain expected {expected_value!r}",
            )

        return CheckResult(success=True, latency_ms=round(elapsed_ms, 1))

    except ImportError:
        # Fallback to socket-based resolution (A/AAAA only) if dnspython
        # isn't installed, so DNS checks still work in a limited fashion.
        return _run_dns_check_fallback(hostname, record_type, timeout_seconds, expected_value, start)
    except Exception as e:  # dns.resolver raises its own exception hierarchy
        etype = type(e).__name__
        if "NXDOMAIN" in etype:
            return CheckResult(success=False, error="domain does not exist (NXDOMAIN)")
        if "NoAnswer" in etype:
            return CheckResult(success=False, error=f"no {record_type} record found")
        if "Timeout" in etype:
            return CheckResult(success=False, error="DNS query timed out")
        return CheckResult(success=False, error=_short(str(e)))


def _run_dns_check_fallback(
    hostname: str, record_type: str, timeout_seconds: int, expected_value: str, start: float
) -> CheckResult:
    if record_type not in ("A", "AAAA"):
        return CheckResult(
            success=False,
            error=f"DNS record type '{record_type}' requires the 'dnspython' package "
                  f"(only A/AAAA supported without it)",
        )
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(max(1, timeout_seconds))
        family = socket.AF_INET6 if record_type == "AAAA" else socket.AF_INET
        infos = socket.getaddrinfo(hostname, None, family)
        values = sorted({info[4][0] for info in infos})
        elapsed_ms = (time.monotonic() - start) * 1000
        if not values:
            return CheckResult(success=False, latency_ms=round(elapsed_ms, 1), error="no records returned")
        if expected_value and not any(expected_value in v for v in values):
            return CheckResult(
                success=False,
                latency_ms=round(elapsed_ms, 1),
                error=f"resolved value(s) {values} did not contain expected {expected_value!r}",
            )
        return CheckResult(success=True, latency_ms=round(elapsed_ms, 1))
    except socket.gaierror:
        return CheckResult(success=False, error="domain does not exist / DNS resolution failed")
    except socket.timeout:
        return CheckResult(success=False, error="DNS query timed out")
    finally:
        socket.setdefaulttimeout(old_timeout)


def check_target(
    address: str,
    method: CheckMethod,
    port: int = 443,
    timeout_seconds: int = 5,
    http_url: str = "",
    http_method: str = "GET",
    http_expected_status_min: int = 200,
    http_expected_status_max: int = 399,
    http_body_contains: str = "",
    http_verify_tls: bool = True,
    dns_record_type: str = "A",
    dns_resolver: str = "",
    dns_expected_value: str = "",
) -> CheckResult:
    """Unified entry point used by the monitor engine."""
    address = (address or "").strip()

    if method == CheckMethod.HTTP:
        url = http_url.strip() if http_url else address
        return _run_http_check(
            url,
            method=http_method,
            timeout_seconds=timeout_seconds,
            expected_status_min=http_expected_status_min,
            expected_status_max=http_expected_status_max,
            body_contains=http_body_contains,
            verify_tls=http_verify_tls,
        )

    if method == CheckMethod.DNS:
        return _run_dns_check(
            address,
            record_type=dns_record_type,
            timeout_seconds=timeout_seconds,
            resolver_address=dns_resolver,
            expected_value=dns_expected_value,
        )

    if not address:
        return CheckResult(success=False, error="no address configured")

    if method == CheckMethod.TCP_PORT:
        return _run_tcp_check(address, port, timeout_seconds)

    return _run_ping(address, timeout_seconds)

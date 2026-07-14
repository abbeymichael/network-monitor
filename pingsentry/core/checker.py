"""
Low level "is it alive" checks.

Two strategies are supported because many hosting providers / firewalls
block ICMP (ping) even for perfectly healthy hosts:

  * PING      - real ICMP echo request, using the system `ping` binary
                (works cross-platform without needing raw-socket / admin
                privileges, unlike Python's raw socket ICMP).
  * TCP_PORT  - open a TCP connection to a specific port (e.g. 80, 443,
                22, 3306...). This is what you want when ICMP is filtered
                but the service itself is reachable.
"""
from __future__ import annotations

import platform
import re
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

from .models import CheckMethod


@dataclass
class CheckResult:
    success: bool
    latency_ms: Optional[float] = None
    error: Optional[str] = None


_IS_WINDOWS = platform.system().lower() == "windows"


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


def check_target(address: str, method: CheckMethod, port: int = 443, timeout_seconds: int = 5) -> CheckResult:
    """Unified entry point used by the monitor engine."""
    address = (address or "").strip()
    if not address:
        return CheckResult(success=False, error="no address configured")

    if method == CheckMethod.TCP_PORT:
        return _run_tcp_check(address, port, timeout_seconds)
    return _run_ping(address, timeout_seconds)

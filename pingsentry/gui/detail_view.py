"""Per-target detail page.

Deep-dive into a single domain / IP: current status with a live heartbeat,
uptime %, lifetime up/down totals, a latency sparkline, the full up/down
event timeline (with per-incident durations), and how many SMS were sent.
"""
from __future__ import annotations

from typing import Callable, List, Optional

import customtkinter as ctk

from ..core.models import Server, StatusEvent, CheckMethod
from ..core import storage
from ..core.engine import human_duration, MonitorEngine
from . import theme
from .widgets import Badge, GhostButton, PrimaryButton, StatCard, Heartbeat, Sparkline


def _method_label(server: Server) -> str:
    method = server.check_method.value if isinstance(server.check_method, CheckMethod) else server.check_method
    if method == CheckMethod.PING.value:
        return "ICMP Ping"
    if method == CheckMethod.TCP_PORT.value:
        return f"TCP Port :{server.port}"
    if method == CheckMethod.HTTP.value:
        return f"HTTP {server.http_method or 'GET'}"
    if method == CheckMethod.DNS.value:
        return f"DNS {(server.dns_record_type or 'A').upper()}"
    return (method or "?").upper()


class DetailView(ctk.CTkFrame):
    def __init__(self, master, on_back: Callable[[], None],
                 on_check_now: Callable[[Server], None],
                 on_edit: Callable[[Server], None], **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_back = on_back
        self.on_check_now = on_check_now
        self.on_edit = on_edit
        self.server: Optional[Server] = None
        self._latency_history: List[Optional[float]] = []
        self._status_history: List[str] = []

        # Header ------------------------------------------------------------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 14))
        GhostButton(header, text="←  Back", width=90, command=self.on_back).pack(side="left")
        self.heartbeat = Heartbeat(header, status="unknown")
        self.heartbeat.set_bg(theme.BG_DARK)
        self.heartbeat.pack(side="left", padx=(14, 8))
        self.title_label = ctk.CTkLabel(header, text="—", font=theme.title_font(22, "bold"))
        self.title_label.pack(side="left")
        self.badge = Badge(header, status="unknown")
        self.badge.pack(side="left", padx=12)
        PrimaryButton(header, text="Check Now", width=110,
                      command=self._check_now).pack(side="right")
        GhostButton(header, text="Edit", width=80,
                    command=self._edit).pack(side="right", padx=(0, 8))

        self.subtitle_label = ctk.CTkLabel(self, text="", font=theme.font(12),
                                            text_color=theme.TEXT_DIM, anchor="w")
        self.subtitle_label.pack(fill="x", pady=(0, 12))

        # Stat cards --------------------------------------------------------
        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.pack(fill="x", pady=(0, 14))
        stats.grid_columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="dstats")
        self.stat_uptime = StatCard(stats, label="Uptime", value="—", value_color=theme.SUCCESS)
        self.stat_state = StatCard(stats, label="Current State", value="—")
        self.stat_incidents = StatCard(stats, label="Outages", value="0", value_color=theme.DANGER)
        self.stat_sms = StatCard(stats, label="SMS Sent", value="0", value_color=theme.ACCENT)
        self.stat_latency = StatCard(stats, label="Last Latency", value="—")
        for i, c in enumerate([self.stat_uptime, self.stat_state, self.stat_incidents,
                               self.stat_sms, self.stat_latency]):
            pad = (0, 8) if i == 0 else ((8, 0) if i == 4 else 8)
            c.grid(row=0, column=i, sticky="ew", padx=pad)

        # Two-column body: sparkline + totals | event timeline --------------
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color=theme.BG_CARD, corner_radius=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ctk.CTkLabel(left, text="Latency (recent checks)", font=theme.font(13, "bold"),
                     text_color=theme.TEXT).pack(anchor="w", padx=16, pady=(16, 8))
        self.sparkline = Sparkline(left, width=360, height=70)
        self.sparkline.pack(fill="x", padx=16, pady=(0, 12))

        div = ctk.CTkFrame(left, height=1, fg_color=theme.BORDER)
        div.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(left, text="Lifetime Totals", font=theme.font(13, "bold"),
                     text_color=theme.TEXT).pack(anchor="w", padx=16, pady=(8, 6))
        self.totals_box = ctk.CTkFrame(left, fg_color="transparent")
        self.totals_box.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        right = ctk.CTkFrame(body, fg_color=theme.BG_CARD, corner_radius=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ctk.CTkLabel(right, text="Up / Down Timeline", font=theme.font(13, "bold"),
                     text_color=theme.TEXT).pack(anchor="w", padx=16, pady=(16, 8))
        self.timeline_scroll = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self.timeline_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 12))
        self._timeline_rows = []

    # ------------------------------------------------------------------
    def _check_now(self):
        if self.server:
            self.on_check_now(self.server)

    def _edit(self):
        if self.server:
            self.on_edit(self.server)

    def load(self, server: Server):
        """Populate the page for a given server and reset history buffers."""
        self.server = server
        self._latency_history = []
        self._status_history = []
        self.refresh(server)
        self._load_timeline(server)

    def note_check(self, server: Server, latency_ms, success: bool):
        """Record a single completed check into the sparkline buffer."""
        if self.server is None or server.id != self.server.id:
            return
        self._latency_history.append(latency_ms if success else None)
        self._status_history.append("up" if success else "down")
        if len(self._latency_history) > 60:
            self._latency_history = self._latency_history[-60:]
            self._status_history = self._status_history[-60:]
        self.sparkline.render(self._latency_history, self._status_history)
        try:
            self.heartbeat.beat()
        except Exception:
            pass

    def refresh(self, server: Server):
        if self.server is None or server.id != self.server.id:
            return
        self.server = server
        status = server.status if server.enabled else "paused"
        self.title_label.configure(text=server.name)
        self.badge.set_status(status)
        self.heartbeat.set_status(status)

        addr = server.address or server.http_url or "—"
        self.subtitle_label.configure(
            text=f"{addr}   ·   {_method_label(server)}   ·   every {server.interval_seconds}s"
                 f"   ·   timeout {server.timeout_seconds}s"
        )

        pct = MonitorEngine.uptime_percent(server)
        self.stat_uptime.set_value(f"{pct:.1f}%" if pct is not None else "—")
        dur = MonitorEngine.current_state_duration_seconds(server)
        state_txt = {"up": "UP", "down": "DOWN", "paused": "PAUSED"}.get(status, "PENDING")
        self.stat_state.set_value(state_txt)
        self.stat_state.value_label.configure(
            text_color=theme.STATUS_COLORS.get(status, theme.MUTED))
        self.stat_incidents.set_value(server.total_down_incidents)
        self.stat_sms.set_value(server.total_sms_sent)
        self.stat_latency.set_value(
            f"{server.last_latency_ms:.0f} ms" if server.last_latency_ms is not None else "—")

        self._render_totals(server, dur)

    def _render_totals(self, server: Server, cur_dur):
        for w in self.totals_box.winfo_children():
            w.destroy()

        def row(label, value):
            r = ctk.CTkFrame(self.totals_box, fg_color="transparent")
            r.pack(fill="x", pady=3)
            ctk.CTkLabel(r, text=label, font=theme.font(12), text_color=theme.MUTED,
                         anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=value, font=theme.font(12, "bold"), text_color=theme.TEXT,
                         anchor="e").pack(side="right")

        cur_state = server.status if server.enabled else "paused"
        row("Current state for", human_duration(cur_dur) if cur_dur else "—")
        row("Total checks", str(server.total_checks))
        row("Successful checks", str(server.total_up_checks))
        row("Total uptime", human_duration(server.total_uptime_seconds))
        row("Total downtime", human_duration(server.total_downtime_seconds))
        row("Outages recorded", str(server.total_down_incidents))
        row("SMS alerts sent", str(server.total_sms_sent))
        row("Last outage", server.last_incident_at or "never")
        row("Last checked", server.last_checked_at or "not yet")

    def _load_timeline(self, server: Server):
        events = storage.load_status_events(server_id=server.id, limit=300)
        self._render_timeline(events)

    def _render_timeline(self, events: List[StatusEvent]):
        for r in self._timeline_rows:
            r.destroy()
        self._timeline_rows = []

        if not events:
            lbl = ctk.CTkLabel(self.timeline_scroll,
                               text="No up/down transitions recorded yet.",
                               text_color=theme.MUTED, font=theme.font(12))
            lbl.pack(pady=30)
            self._timeline_rows.append(lbl)
            return

        for ev in reversed(events):  # newest first
            is_down = ev.status == "down"
            color = theme.DANGER if is_down else theme.SUCCESS
            soft = theme.DANGER_SOFT if is_down else theme.SUCCESS_SOFT
            icon = "▼" if is_down else "▲"

            row = ctk.CTkFrame(self.timeline_scroll, fg_color=theme.BG_PANEL, corner_radius=8)
            row.pack(fill="x", padx=6, pady=3)

            ctk.CTkLabel(row, text=icon, text_color=color, fg_color=soft, corner_radius=6,
                         font=theme.font(11, "bold"), width=26, padx=4, pady=3).pack(
                side="left", padx=(10, 10), pady=8)

            txt = ctk.CTkFrame(row, fg_color="transparent")
            txt.pack(side="left", fill="x", expand=True, pady=6)
            head = "Went DOWN" if is_down else "Recovered (UP)"
            ctk.CTkLabel(txt, text=head, font=theme.font(12, "bold"), text_color=color,
                         anchor="w").pack(anchor="w")
            sub_bits = [ev.at]
            if ev.duration_seconds:
                prefix = "was up for" if is_down else "was down for"
                sub_bits.append(f"{prefix} {human_duration(ev.duration_seconds)}")
            if is_down and ev.reason:
                sub_bits.append(ev.reason)
            if not is_down and ev.alerts_sent:
                sub_bits.append(f"{ev.alerts_sent} SMS sent")
            ctk.CTkLabel(txt, text="  ·  ".join(sub_bits), font=theme.font(11),
                         text_color=theme.TEXT_DIM, anchor="w", justify="left",
                         wraplength=360).pack(anchor="w")
            self._timeline_rows.append(row)

    def add_timeline_event(self, ev: StatusEvent):
        """Live-append a new event without a full reload."""
        if self.server and ev.server_id == self.server.id:
            self._load_timeline(self.server)

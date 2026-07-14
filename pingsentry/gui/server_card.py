"""A single server row/card shown on the dashboard."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..core.models import Server, CheckMethod
from . import theme
from .widgets import Badge, GhostButton


def _method_label(server: Server) -> str:
    """Human-readable summary of a server's check method for card display."""
    method = server.check_method.value if isinstance(server.check_method, CheckMethod) else server.check_method
    if method == CheckMethod.PING.value:
        return "PING"
    if method == CheckMethod.TCP_PORT.value:
        return f"TCP :{server.port}"
    if method == CheckMethod.HTTP.value:
        return f"HTTP ({server.http_method or 'GET'})"
    if method == CheckMethod.DNS.value:
        return f"DNS ({(server.dns_record_type or 'A').upper()})"
    return method.upper() if method else "?"


def _display_address(server: Server) -> str:
    """Address text to show on the card (falls back to the HTTP URL if the
    plain address field was left blank for an HTTP check)."""
    method = server.check_method.value if isinstance(server.check_method, CheckMethod) else server.check_method
    if not server.address and method == CheckMethod.HTTP.value and server.http_url:
        return server.http_url
    return server.address


class ServerCard(ctk.CTkFrame):
    def __init__(
        self,
        master,
        server: Server,
        on_edit: Callable[[Server], None],
        on_delete: Callable[[Server], None],
        on_check_now: Callable[[Server], None],
        on_toggle_enabled: Callable[[Server, bool], None],
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.BG_CARD, corner_radius=12, **kwargs)
        self.server = server
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.on_check_now = on_check_now
        self.on_toggle_enabled = on_toggle_enabled

        self.grid_columnconfigure(1, weight=1)

        # Status dot + badge -------------------------------------------------
        self.badge = Badge(self, status=server.status)
        self.badge.grid(row=0, column=0, rowspan=2, padx=(16, 14), pady=16, sticky="w")

        # Name + address ------------------------------------------------------
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="ew", pady=(14, 0))
        self.name_label = ctk.CTkLabel(
            info_frame, text=server.name, font=theme.font(15, "bold"),
            text_color=theme.TEXT, anchor="w",
        )
        self.name_label.pack(anchor="w")

        method_txt = _method_label(server)
        self.detail_label = ctk.CTkLabel(
            self, text=f"{_display_address(server)}  ·  {method_txt}  ·  every {server.interval_seconds}s",
            font=theme.font(12), text_color=theme.TEXT_DIM, anchor="w",
        )
        self.detail_label.grid(row=1, column=1, sticky="ew", pady=(2, 14))

        # Right side: last check + latency -----------------------------------
        meta_frame = ctk.CTkFrame(self, fg_color="transparent")
        meta_frame.grid(row=0, column=2, rowspan=2, padx=10, sticky="e")
        self.latency_label = ctk.CTkLabel(
            meta_frame, text=self._latency_text(), font=theme.font(12),
            text_color=theme.TEXT_DIM,
        )
        self.latency_label.pack(anchor="e")
        self.checked_label = ctk.CTkLabel(
            meta_frame, text=self._checked_text(), font=theme.font(11),
            text_color=theme.MUTED,
        )
        self.checked_label.pack(anchor="e")

        # Actions --------------------------------------------------------------
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=0, column=3, rowspan=2, padx=(4, 16), sticky="e")

        self.enabled_switch = ctk.CTkSwitch(
            actions, text="", width=40, progress_color=theme.ACCENT,
            command=self._toggle,
        )
        if server.enabled:
            self.enabled_switch.select()
        else:
            self.enabled_switch.deselect()
        self.enabled_switch.pack(side="left", padx=(0, 10))

        GhostButton(actions, text="Check", width=64, command=lambda: self.on_check_now(self.server)).pack(side="left", padx=4)
        GhostButton(actions, text="Edit", width=56, command=lambda: self.on_edit(self.server)).pack(side="left", padx=4)
        GhostButton(
            actions, text="✕", width=32, text_color=theme.DANGER,
            command=lambda: self.on_delete(self.server),
        ).pack(side="left", padx=(4, 0))

    def _latency_text(self) -> str:
        if self.server.last_latency_ms is not None:
            return f"{self.server.last_latency_ms:.0f} ms"
        return "—"

    def _checked_text(self) -> str:
        if self.server.last_checked_at:
            return f"checked {self.server.last_checked_at.split(' ')[1]}"
        return "not checked yet"

    def _toggle(self):
        enabled = bool(self.enabled_switch.get())
        self.on_toggle_enabled(self.server, enabled)

    def refresh(self, server: Server):
        """Update displayed values in-place (avoids destroy/recreate flicker)."""
        self.server = server
        self.badge.set_status(server.status if server.enabled else "paused")
        self.name_label.configure(text=server.name)
        method_txt = _method_label(server)
        self.detail_label.configure(text=f"{_display_address(server)}  ·  {method_txt}  ·  every {server.interval_seconds}s")
        self.latency_label.configure(text=self._latency_text())
        self.checked_label.configure(text=self._checked_text())
        if server.enabled and not self.enabled_switch.get():
            self.enabled_switch.select()
        elif not server.enabled and self.enabled_switch.get():
            self.enabled_switch.deselect()

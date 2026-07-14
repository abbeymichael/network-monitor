"""Dashboard tab: server list + summary stat cards."""
from __future__ import annotations

from typing import Callable, Dict, List

import customtkinter as ctk

from ..core.models import Server
from . import theme
from .widgets import PrimaryButton, StatCard
from .server_card import ServerCard


class DashboardView(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_add_server: Callable[[], None],
        on_edit_server: Callable[[Server], None],
        on_delete_server: Callable[[Server], None],
        on_check_now: Callable[[Server], None],
        on_toggle_enabled: Callable[[Server, bool], None],
        on_open_detail: Callable[[Server], None] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_add_server = on_add_server
        self.on_edit_server = on_edit_server
        self.on_delete_server = on_delete_server
        self.on_check_now = on_check_now
        self.on_toggle_enabled = on_toggle_enabled
        self.on_open_detail = on_open_detail

        self.cards: Dict[str, ServerCard] = {}

        # Header ------------------------------------------------------------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(header, text="Dashboard", font=theme.title_font(22, "bold")).pack(side="left")
        PrimaryButton(header, text="+  Add Server", command=self.on_add_server, width=140).pack(side="right")

        # Stat cards ----------------------------------------------------------
        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.pack(fill="x", pady=(0, 18))
        stats.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="stats")

        self.stat_total = StatCard(stats, label="Total Servers", value="0")
        self.stat_up = StatCard(stats, label="Online", value="0", value_color=theme.SUCCESS)
        self.stat_down = StatCard(stats, label="Down", value="0", value_color=theme.DANGER)
        self.stat_paused = StatCard(stats, label="Paused", value="0", value_color=theme.WARNING)

        self.stat_total.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.stat_up.grid(row=0, column=1, sticky="ew", padx=8)
        self.stat_down.grid(row=0, column=2, sticky="ew", padx=8)
        self.stat_paused.grid(row=0, column=3, sticky="ew", padx=(8, 0))

        # Server list ------------------------------------------------------------
        list_header = ctk.CTkFrame(self, fg_color="transparent")
        list_header.pack(fill="x", pady=(4, 8))
        ctk.CTkLabel(list_header, text="Monitored Targets", font=theme.font(13, "bold"), text_color=theme.TEXT_DIM).pack(anchor="w")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True)

        self.empty_label = ctk.CTkLabel(
            self.scroll,
            text="No servers yet. Click \"+ Add Server\" to start monitoring.",
            text_color=theme.MUTED, font=theme.font(13),
        )
        self.empty_label.pack(pady=60)

    # ------------------------------------------------------------------
    def render_servers(self, servers: List[Server]):
        seen_ids = set()
        if servers:
            self.empty_label.pack_forget()
        else:
            self.empty_label.pack(pady=60)

        for server in servers:
            seen_ids.add(server.id)
            if server.id in self.cards:
                self.cards[server.id].refresh(server)
            else:
                card = ServerCard(
                    self.scroll, server,
                    on_edit=self.on_edit_server,
                    on_delete=self.on_delete_server,
                    on_check_now=self.on_check_now,
                    on_toggle_enabled=self.on_toggle_enabled,
                    on_open_detail=self.on_open_detail,
                )
                card.pack(fill="x", pady=6)
                self.cards[server.id] = card

        # remove cards for deleted servers
        for sid in list(self.cards.keys()):
            if sid not in seen_ids:
                self.cards[sid].destroy()
                del self.cards[sid]

        self._update_stats(servers)

    def beat_server(self, server_id: str):
        """Flash a server's heartbeat when a check completes."""
        card = self.cards.get(server_id)
        if card:
            card.beat()

    def _update_stats(self, servers: List[Server]):
        total = len(servers)
        up = sum(1 for s in servers if s.enabled and s.status == "up")
        down = sum(1 for s in servers if s.enabled and s.status == "down")
        paused = sum(1 for s in servers if not s.enabled)
        self.stat_total.set_value(total)
        self.stat_up.set_value(up)
        self.stat_down.set_value(down)
        self.stat_paused.set_value(paused)

"""Dedicated Notifications page.

Shows every notification the app has produced — SMS sent, SMS failed
(with the error), suppressed alerts, recovery messages and test sends —
with filtering by status and a live counter of successes / failures.
"""
from __future__ import annotations

from typing import Callable, Dict, List

import customtkinter as ctk

from ..core.models import NotificationRecord
from . import theme
from .widgets import GhostButton, PrimaryButton, StatCard


KIND_LABEL = {
    "down": "DOWN ALERT",
    "recovery": "RECOVERY",
    "test": "TEST",
    "info": "INFO",
}

STATUS_STYLE = {
    "sent": (theme.SUCCESS, theme.SUCCESS_SOFT, "✓ SENT"),
    "failed": (theme.DANGER, theme.DANGER_SOFT, "✕ FAILED"),
    "suppressed": (theme.WARNING, theme.WARNING_SOFT, "⦸ SUPPRESSED"),
    "info": (theme.MUTED, theme.BG_CARD, "• INFO"),
}


class NotificationsView(ctk.CTkFrame):
    def __init__(self, master, on_clear: Callable[[], None], **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_clear = on_clear
        self._all: List[NotificationRecord] = []
        self._filter = "all"   # all | sent | failed | suppressed
        self._rows = []

        # Header ------------------------------------------------------------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(header, text="Notifications", font=theme.title_font(22, "bold")).pack(side="left")
        GhostButton(header, text="Clear All", command=self._clear).pack(side="right")

        # Summary stats -----------------------------------------------------
        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.pack(fill="x", pady=(0, 14))
        stats.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="nstats")
        self.stat_total = StatCard(stats, label="Total", value="0")
        self.stat_sent = StatCard(stats, label="Delivered", value="0", value_color=theme.SUCCESS)
        self.stat_failed = StatCard(stats, label="Failed", value="0", value_color=theme.DANGER)
        self.stat_suppressed = StatCard(stats, label="Suppressed", value="0", value_color=theme.WARNING)
        self.stat_total.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.stat_sent.grid(row=0, column=1, sticky="ew", padx=8)
        self.stat_failed.grid(row=0, column=2, sticky="ew", padx=8)
        self.stat_suppressed.grid(row=0, column=3, sticky="ew", padx=(8, 0))

        # Filter chips ------------------------------------------------------
        chips = ctk.CTkFrame(self, fg_color="transparent")
        chips.pack(fill="x", pady=(0, 10))
        self._chip_btns: Dict[str, ctk.CTkButton] = {}
        for key, label in [("all", "All"), ("sent", "Delivered"),
                           ("failed", "Failed"), ("suppressed", "Suppressed")]:
            b = ctk.CTkButton(
                chips, text=label, width=96, height=30, corner_radius=15,
                fg_color=theme.BG_CARD, hover_color=theme.BG_CARD_HOVER,
                text_color=theme.TEXT_DIM, font=theme.font(12, "bold"),
                command=lambda k=key: self._set_filter(k),
            )
            b.pack(side="left", padx=(0, 8))
            self._chip_btns[key] = b

        # List --------------------------------------------------------------
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=theme.BG_CARD, corner_radius=14)
        self.scroll.pack(fill="both", expand=True)
        self.empty_label = ctk.CTkLabel(
            self.scroll,
            text="No notifications yet.\nWhen a target goes down or recovers, the SMS attempts and results appear here.",
            text_color=theme.MUTED, font=theme.font(13), justify="center",
        )
        self.empty_label.pack(pady=50)

        self._set_filter("all")

    # ------------------------------------------------------------------
    def _clear(self):
        self.on_clear()
        self.set_records([])

    def _set_filter(self, key: str):
        self._filter = key
        for k, b in self._chip_btns.items():
            if k == key:
                b.configure(fg_color=theme.ACCENT, text_color="#ffffff")
            else:
                b.configure(fg_color=theme.BG_CARD, text_color=theme.TEXT_DIM)
        self._render_rows()

    def set_records(self, records: List[NotificationRecord]):
        self._all = list(records)
        self._update_stats()
        self._render_rows()

    def prepend_record(self, rec: NotificationRecord):
        self._all.append(rec)
        self._update_stats()
        self._render_rows()

    def _update_stats(self):
        total = len(self._all)
        sent = sum(1 for r in self._all if r.status == "sent")
        failed = sum(1 for r in self._all if r.status == "failed")
        suppressed = sum(1 for r in self._all if r.status == "suppressed")
        self.stat_total.set_value(total)
        self.stat_sent.set_value(sent)
        self.stat_failed.set_value(failed)
        self.stat_suppressed.set_value(suppressed)

    def _filtered(self) -> List[NotificationRecord]:
        if self._filter == "all":
            return self._all
        return [r for r in self._all if r.status == self._filter]

    def _render_rows(self):
        for r in self._rows:
            r.destroy()
        self._rows = []

        records = self._filtered()
        if not records:
            self.empty_label.pack(pady=50)
            return
        self.empty_label.pack_forget()

        for rec in reversed(records):  # newest first
            row = self._make_row(rec)
            row.pack(fill="x", padx=10, pady=5)
            self._rows.append(row)

    def _make_row(self, rec: NotificationRecord) -> ctk.CTkFrame:
        color, soft, status_txt = STATUS_STYLE.get(rec.status, STATUS_STYLE["info"])

        card = ctk.CTkFrame(self.scroll, fg_color=theme.BG_PANEL, corner_radius=10)
        card.grid_columnconfigure(1, weight=1)

        # status pill
        pill = ctk.CTkLabel(card, text=status_txt, text_color=color, fg_color=soft,
                            corner_radius=8, font=theme.font(10, "bold"), padx=8, pady=3)
        pill.grid(row=0, column=0, rowspan=2, padx=(12, 12), pady=12, sticky="w")

        # main text
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(10, 0))
        kind_txt = KIND_LABEL.get(rec.kind, rec.kind.upper())
        title = f"{kind_txt} · {rec.server_name}"
        if rec.address:
            title += f" ({rec.address})"
        ctk.CTkLabel(top, text=title, font=theme.font(13, "bold"),
                     text_color=theme.TEXT, anchor="w").pack(side="left")
        ctk.CTkLabel(card, text=rec.timestamp, font=theme.font(10),
                     text_color=theme.MUTED).grid(row=0, column=2, padx=(0, 14), pady=(10, 0), sticky="e")

        detail_bits = []
        if rec.recipients:
            detail_bits.append("to " + ", ".join(rec.recipients))
        if rec.status == "failed" and rec.error:
            detail_bits.append(f"error: {rec.error}")
        elif rec.detail:
            detail_bits.append(rec.detail)
        elif rec.message:
            detail_bits.append(rec.message)
        detail_text = "  ·  ".join(detail_bits) if detail_bits else "—"
        detail_color = theme.DANGER if rec.status == "failed" else theme.TEXT_DIM
        ctk.CTkLabel(card, text=detail_text, font=theme.font(11), text_color=detail_color,
                     anchor="w", justify="left", wraplength=680).grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=(0, 14), pady=(2, 10))

        return card

"""Activity log / history tab."""
from __future__ import annotations

from typing import List, Dict, Any

import customtkinter as ctk

from . import theme
from .widgets import GhostButton, SectionLabel

LEVEL_COLORS = {
    "info": theme.TEXT_DIM,
    "success": theme.SUCCESS,
    "warning": theme.WARNING,
    "error": theme.DANGER,
}

LEVEL_ICON = {
    "info": "•",
    "success": "✓",
    "warning": "!",
    "error": "✕",
}


class LogsView(ctk.CTkFrame):
    def __init__(self, master, on_clear, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_clear = on_clear

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text="Activity Log", font=theme.title_font(18, "bold")).pack(side="left")
        GhostButton(header, text="Clear Log", command=self._clear).pack(side="right")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color=theme.BG_CARD, corner_radius=14)
        self.scroll.pack(fill="both", expand=True)

        self.empty_label = ctk.CTkLabel(
            self.scroll, text="No activity yet. Log entries will appear here once monitoring starts.",
            text_color=theme.MUTED, font=theme.font(13),
        )
        self.empty_label.pack(pady=40)

        self._rows = []

    def _clear(self):
        self.on_clear()
        self.set_entries([])

    def set_entries(self, entries: List[Dict[str, Any]]):
        for r in self._rows:
            r.destroy()
        self._rows = []

        if not entries:
            self.empty_label.pack(pady=40)
            return
        self.empty_label.pack_forget()

        # newest first
        for entry in reversed(entries):
            row = self._make_row(entry)
            row.pack(fill="x", padx=10, pady=3)
            self._rows.append(row)

    def prepend_entry(self, entry: Dict[str, Any]):
        self.empty_label.pack_forget()
        row = self._make_row(entry)
        row.pack(fill="x", padx=10, pady=3, before=self._rows[0] if self._rows else None)
        self._rows.insert(0, row)
        # cap displayed rows for perf
        if len(self._rows) > 400:
            old = self._rows.pop()
            old.destroy()

    def _make_row(self, entry: Dict[str, Any]) -> ctk.CTkFrame:
        level = entry.get("level", "info")
        color = LEVEL_COLORS.get(level, theme.TEXT_DIM)
        icon = LEVEL_ICON.get(level, "•")

        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        icon_lbl = ctk.CTkLabel(row, text=icon, text_color=color, font=theme.font(13, "bold"), width=18)
        icon_lbl.pack(side="left", padx=(4, 8))
        ts_lbl = ctk.CTkLabel(row, text=entry.get("timestamp", ""), text_color=theme.MUTED, font=theme.font(11), width=140, anchor="w")
        ts_lbl.pack(side="left", padx=(0, 10))
        msg_lbl = ctk.CTkLabel(row, text=entry.get("message", ""), text_color=theme.TEXT, font=theme.font(12), anchor="w", justify="left")
        msg_lbl.pack(side="left", fill="x", expand=True)
        return row

"""Activity log / history tab — with level filters, live search and a
running tally of events by severity."""
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

LEVEL_SOFT = {
    "info": theme.BG_CARD,
    "success": theme.SUCCESS_SOFT,
    "warning": theme.WARNING_SOFT,
    "error": theme.DANGER_SOFT,
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
        self._entries: List[Dict[str, Any]] = []
        self._filter = "all"      # all | info | success | warning | error
        self._search = ""
        self._rows = []
        self._MAX = 800

        # Header ------------------------------------------------------------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(header, text="Activity Log", font=theme.title_font(22, "bold")).pack(side="left")
        GhostButton(header, text="Clear Log", command=self._clear).pack(side="right")

        # Tally counters ----------------------------------------------------
        self.count_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.count_bar.pack(fill="x", pady=(0, 8))
        self._count_labels = {}
        for level, label in [("error", "Errors"), ("warning", "Warnings"),
                             ("success", "Recoveries"), ("info", "Info")]:
            chip = ctk.CTkFrame(self.count_bar, fg_color=LEVEL_SOFT[level], corner_radius=10)
            chip.pack(side="left", padx=(0, 8))
            lbl = ctk.CTkLabel(chip, text=f"0 {label}", font=theme.font(11, "bold"),
                               text_color=LEVEL_COLORS[level], padx=12, pady=5)
            lbl.pack()
            self._count_labels[level] = (lbl, label)

        # Filter + search row ----------------------------------------------
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", pady=(0, 8))
        self._chip_btns = {}
        for key, label in [("all", "All"), ("error", "Errors"), ("warning", "Warnings"),
                           ("success", "Success"), ("info", "Info")]:
            b = ctk.CTkButton(
                controls, text=label, width=78, height=28, corner_radius=14,
                fg_color=theme.BG_CARD, hover_color=theme.BG_CARD_HOVER,
                text_color=theme.TEXT_DIM, font=theme.font(11, "bold"),
                command=lambda k=key: self._set_filter(k),
            )
            b.pack(side="left", padx=(0, 6))
            self._chip_btns[key] = b

        self.search_entry = ctk.CTkEntry(controls, placeholder_text="Search log…", width=220)
        self.search_entry.pack(side="right")
        self.search_entry.bind("<KeyRelease>", self._on_search)

        # List --------------------------------------------------------------
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=theme.BG_CARD, corner_radius=14)
        self.scroll.pack(fill="both", expand=True)

        self.empty_label = ctk.CTkLabel(
            self.scroll, text="No activity yet. Log entries will appear here once monitoring starts.",
            text_color=theme.MUTED, font=theme.font(13),
        )
        self.empty_label.pack(pady=40)

        self._set_filter("all")

    # ------------------------------------------------------------------
    def _clear(self):
        self.on_clear()
        self.set_entries([])

    def _on_search(self, _event=None):
        self._search = self.search_entry.get().strip().lower()
        self._render()

    def _set_filter(self, key: str):
        self._filter = key
        for k, b in self._chip_btns.items():
            if k == key:
                b.configure(fg_color=theme.ACCENT, text_color="#ffffff")
            else:
                b.configure(fg_color=theme.BG_CARD, text_color=theme.TEXT_DIM)
        self._render()

    def set_entries(self, entries: List[Dict[str, Any]]):
        self._entries = list(entries)[-self._MAX:]
        self._update_counts()
        self._render()

    def prepend_entry(self, entry: Dict[str, Any]):
        self._entries.append(entry)
        if len(self._entries) > self._MAX:
            self._entries = self._entries[-self._MAX:]
        self._update_counts()
        self._render()

    def _update_counts(self):
        counts = {"error": 0, "warning": 0, "success": 0, "info": 0}
        for e in self._entries:
            lvl = e.get("level", "info")
            if lvl in counts:
                counts[lvl] += 1
        for level, (lbl, label) in self._count_labels.items():
            lbl.configure(text=f"{counts[level]} {label}")

    def _matches(self, entry: Dict[str, Any]) -> bool:
        if self._filter != "all" and entry.get("level", "info") != self._filter:
            return False
        if self._search:
            hay = (entry.get("message", "") + " " + entry.get("server_name", "") +
                   " " + entry.get("timestamp", "")).lower()
            if self._search not in hay:
                return False
        return True

    def _render(self):
        for r in self._rows:
            r.destroy()
        self._rows = []

        filtered = [e for e in self._entries if self._matches(e)]
        if not filtered:
            msg = "No matching log entries." if (self._search or self._filter != "all") \
                else "No activity yet. Log entries will appear here once monitoring starts."
            self.empty_label.configure(text=msg)
            self.empty_label.pack(pady=40)
            return
        self.empty_label.pack_forget()

        for entry in reversed(filtered):  # newest first
            row = self._make_row(entry)
            row.pack(fill="x", padx=10, pady=3)
            self._rows.append(row)

    def _make_row(self, entry: Dict[str, Any]) -> ctk.CTkFrame:
        level = entry.get("level", "info")
        color = LEVEL_COLORS.get(level, theme.TEXT_DIM)
        soft = LEVEL_SOFT.get(level, theme.BG_CARD)
        icon = LEVEL_ICON.get(level, "•")

        row = ctk.CTkFrame(self.scroll, fg_color=theme.BG_PANEL, corner_radius=8)
        icon_lbl = ctk.CTkLabel(row, text=icon, text_color=color, fg_color=soft,
                                corner_radius=6, font=theme.font(12, "bold"),
                                width=24, padx=2, pady=2)
        icon_lbl.pack(side="left", padx=(8, 8), pady=6)
        ts_lbl = ctk.CTkLabel(row, text=entry.get("timestamp", ""), text_color=theme.MUTED,
                              font=theme.font(11), width=140, anchor="w")
        ts_lbl.pack(side="left", padx=(0, 10))
        msg_lbl = ctk.CTkLabel(row, text=entry.get("message", ""), text_color=theme.TEXT,
                               font=theme.font(12), anchor="w", justify="left")
        msg_lbl.pack(side="left", fill="x", expand=True, pady=6)
        return row

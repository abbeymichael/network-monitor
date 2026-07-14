"""
Central place for colors, fonts and small style constants so the whole
app has one consistent "slick" look.
"""
import customtkinter as ctk

# Brand / status palette -----------------------------------------------
BG_DARK = "#0f1420"
BG_PANEL = "#161c2c"
BG_CARD = "#1c2437"
BG_CARD_HOVER = "#232c44"
BORDER = "#2a3348"

ACCENT = "#4f7cff"
ACCENT_HOVER = "#3d67e6"
ACCENT_SOFT = "#26314f"

SUCCESS = "#33d17a"
SUCCESS_SOFT = "#173325"
WARNING = "#f5b544"
WARNING_SOFT = "#3a2f14"
DANGER = "#f4553f"
DANGER_SOFT = "#3a1a17"
MUTED = "#8892a6"
TEXT = "#eef1f8"
TEXT_DIM = "#a7b0c4"

STATUS_COLORS = {
    "up": SUCCESS,
    "down": DANGER,
    "unknown": MUTED,
    "paused": WARNING,
}

STATUS_SOFT = {
    "up": SUCCESS_SOFT,
    "down": DANGER_SOFT,
    "unknown": "#232a3c",
    "paused": WARNING_SOFT,
}

STATUS_LABELS = {
    "up": "ONLINE",
    "down": "DOWN",
    "unknown": "PENDING",
    "paused": "PAUSED",
}

FONT_FAMILY = "Roboto"


def font(size=13, weight="normal"):
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


def title_font(size=20, weight="bold"):
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


def apply_theme():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

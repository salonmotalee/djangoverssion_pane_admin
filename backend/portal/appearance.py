"""Shared portal defaults; palettes contain colors only, never arbitrary CSS."""

from copy import deepcopy

DEFAULT_APPEARANCE = {
    "version": 1,
    "mode": "light",
    "palettes": {
        "light": {
            "primary": "#7860cc",
            "background": "#f6f7fb",
            "surface": "#ffffff",
            "sidebar": "#22233c",
            "success": "#258673",
            "warning": "#94621b",
            "danger": "#c44761",
        },
        "dark": {
            "primary": "#a78bfa",
            "background": "#101321",
            "surface": "#1c2033",
            "sidebar": "#151829",
            "success": "#5ad1a4",
            "warning": "#f3bf70",
            "danger": "#fb889a",
        },
    },
}


def default_appearance():
    return deepcopy(DEFAULT_APPEARANCE)

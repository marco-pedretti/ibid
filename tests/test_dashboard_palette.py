"""Tests for dashboard/palette.py.

These guard properties that are easy to break by "just tweaking a colour":
the slot order is the colour-blindness safety mechanism, hues are never
cycled, and the same index maps to the same colour in the table and the chart.

The perceptual thresholds themselves (OKLab ΔE under simulated protanopia and
deuteranopia) are re-derived here rather than trusted, so a future edit to the
hex values fails the suite instead of silently shipping an unreadable chart.
"""

from __future__ import annotations

import math

import pytest

from dashboard.palette import (
    DARK,
    LIGHT,
    MAX_SERIES,
    color_map,
    series_colors,
    theme_mode,
)

# Machado, Oliveira & Fernandes (2009), severity 1.0 — the model the dataviz
# skill's validator calibrates its thresholds against.
_MACHADO = {
    "protan": [[0.152286, 1.052583, -0.204868],
               [0.114503, 0.786281, 0.099216],
               [-0.003882, -0.048116, 1.051998]],
    "deutan": [[0.367322, 0.860646, -0.227968],
               [0.280085, 0.672501, 0.047413],
               [-0.011820, 0.042940, 0.968881]],
}
CVD_TARGET = 8.0     # OKLab ΔE×100, adjacent pairs
NORMAL_FLOOR = 15.0  # OKLab ΔE×100, unsimulated vision


def _lin(hex_color: str) -> list[float]:
    h = hex_color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out


def _oklab(rgb: list[float]) -> list[float]:
    # l/m/s sono i nomi delle risposte dei coni nella formula OKLab
    # pubblicata: rinominarli allontanerebbe il codice dal riferimento.
    r, g, b = rgb
    l = (  # noqa: E741
        0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    ) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return [0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s]


def _simulate(hex_color: str, kind: str) -> list[float]:
    r, g, b = _lin(hex_color)
    m = _MACHADO[kind]
    return [max(0.0, min(1.0, m[i][0] * r + m[i][1] * g + m[i][2] * b)) for i in range(3)]


def _delta_e(a: str, b: str, kind: str | None = None) -> float:
    pa = _oklab(_simulate(a, kind) if kind else _lin(a))
    pb = _oklab(_simulate(b, kind) if kind else _lin(b))
    return 100 * math.dist(pa, pb)


@pytest.mark.parametrize("slots,name", [(LIGHT, "light"), (DARK, "dark")])
class TestPerceptualGates:
    """Re-derived, not trusted: editing a hex must fail here, not in production."""

    def test_adjacent_pairs_clear_cvd_target(self, slots, name):
        worst = min(
            _delta_e(slots[i], slots[i + 1], kind)
            for i in range(len(slots) - 1)
            for kind in ("protan", "deutan")
        )
        assert worst >= CVD_TARGET, (
            f"{name}: peggiore coppia adiacente ΔE {worst:.1f} < {CVD_TARGET} — "
            "indistinguibile per un lettore daltonico"
        )

    def test_adjacent_pairs_clear_normal_vision_floor(self, slots, name):
        worst = min(_delta_e(slots[i], slots[i + 1]) for i in range(len(slots) - 1))
        assert worst >= NORMAL_FLOOR, (
            f"{name}: peggiore coppia adiacente ΔE {worst:.1f} < {NORMAL_FLOOR} "
            "anche a vista normale"
        )

    def test_all_slots_are_six_digit_hex(self, slots, name):
        assert all(len(c) == 7 and c.startswith("#") for c in slots)

    def test_no_duplicate_hues(self, slots, name):
        assert len(set(slots)) == len(slots)


class TestSeriesColors:
    def test_returns_requested_count(self):
        assert len(series_colors(3, "dark")) == 3

    def test_assigned_in_fixed_order(self):
        """Slot order is the safety mechanism — never sorted, never shuffled."""
        assert series_colors(4, "light") == list(LIGHT[:4])

    def test_light_and_dark_differ(self):
        assert series_colors(3, "light") != series_colors(3, "dark")

    def test_never_cycles_past_the_slots(self):
        """A 9th series must not reuse slot 1: two runs would share an identity."""
        colors = series_colors(20, "dark")
        assert len(colors) == MAX_SERIES
        assert len(set(colors)) == MAX_SERIES

    def test_zero_series(self):
        assert series_colors(0, "dark") == []

    def test_prefix_is_stable_when_a_series_is_added(self):
        """Colour follows the run, not its rank: adding #4 must not repaint #1-3."""
        before = series_colors(3, "dark")
        after = series_colors(4, "dark")
        assert after[:3] == before


class TestColorMap:
    def test_maps_labels_by_position(self):
        m = color_map(["#1 a", "#2 b"], "dark")
        assert m["#1 a"] == DARK[0]
        assert m["#2 b"] == DARK[1]

    def test_empty(self):
        assert color_map([], "dark") == {}

    def test_index_one_matches_first_table_row(self):
        """The link the run table relies on: #1 in the table == slot 1 in the chart."""
        labels = ["#1 routed·dense", "#2 generic·dense"]
        assert color_map(labels, "dark")["#1 routed·dense"] == series_colors(2, "dark")[0]


class TestThemeMode:
    def test_returns_a_valid_mode_outside_streamlit(self):
        assert theme_mode() in ("light", "dark")

    def test_falls_back_to_dark_when_context_unavailable(self, monkeypatch):
        import streamlit as st

        monkeypatch.setattr(st, "context", object(), raising=False)
        assert theme_mode() == "dark"

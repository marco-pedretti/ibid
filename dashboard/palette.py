"""Categorical colours for the dashboard charts.

Why a module and not a literal in the chart call: the same colour must identify
the same run in the chart legend *and* in the run table above it.  A reader
should be able to see a bar and know which row of the table it came from without
counting positions — that link is the whole reason these values are shared.

Provenance: these are the eight categorical slots of the `dataviz` skill's
reference palette, in its documented order.  The order is the colour-blindness
safety mechanism, not decoration — re-ordering the slots invalidates it.

Validated (OKLab ΔE ×100, Machado-Oliveira-Fernandes 2009 severity 1.0) against
the surfaces Streamlit actually renders on, not the skill's defaults:

    light on #FFFFFF   CVD 9.1 (target ≥8) · normal-vision 19.6 (floor ≥15)
    dark  on #0E1117   CVD 8.4             · normal-vision 19.3

Both pass.  In light mode three slots (aqua, yellow, magenta) fall below the
3:1 contrast floor against white; the documented relief for that is a visible
table view, which the comparator has — the metrics table sits directly above
the chart.  Do not use this palette in a chart that has no table beside it
without re-checking that.

Grouped bars put series next to each other within a group, so the *adjacent*
pairlist is the applicable gate (per the skill: stacks, bars, lines).  A chart
where every series can touch every other — scatter, bubble — must re-validate
with all pairs, where only the first three slots clear the floors.
"""

from __future__ import annotations

#: Categorical slots, in the order they must be assigned.
LIGHT: tuple[str, ...] = (
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
)

DARK: tuple[str, ...] = (
    "#3987e5",
    "#d95926",
    "#199e70",
    "#c98500",
    "#d55181",
    "#008300",
    "#9085e9",
    "#e66767",
)

#: Past this many series, hues would have to be cycled — and a cycled hue means
#: two runs share a colour, which is worse than no colour at all.
MAX_SERIES = len(LIGHT)

#: Chart chrome, from the same reference palette.
GRID = {"light": "#e1e0d9", "dark": "#2c2c2a"}
AXIS = {"light": "#c3c2b7", "dark": "#383835"}
WHISKER = {"light": "#52514e", "dark": "#c3c2b7"}


def theme_mode() -> str:
    """"light" or "dark", from the viewer's Streamlit theme.

    Falls back to dark: it is Streamlit's default and the mode this dashboard is
    normally read in, and the dark slots are the ones that clear contrast on
    both surfaces.
    """
    try:
        import streamlit as st

        mode = getattr(getattr(st.context, "theme", None), "type", None)
        return mode if mode in ("light", "dark") else "dark"
    except Exception:
        return "dark"


def series_colors(n: int, mode: str | None = None) -> list[str]:
    """First `n` categorical slots for the given mode, never cycled.

    Asking for more than MAX_SERIES returns MAX_SERIES colours; the caller is
    expected to have capped the series count before that point.
    """
    slots = LIGHT if (mode or theme_mode()) == "light" else DARK
    return list(slots[: min(n, len(slots))])


def color_map(labels: list[str], mode: str | None = None) -> dict[str, str]:
    """{series label: hex}, assigned by position.

    Position, not rank: the caller passes labels already ordered as the runs
    were selected, so a run keeps its colour when another is added after it.
    """
    return dict(zip(labels, series_colors(len(labels), mode)))

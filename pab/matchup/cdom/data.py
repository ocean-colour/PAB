"""Shared analysis dataframe + caveats for the CDOM comparison (C1-C4).

Per C1, CDOM ingestion was folded into the same Stage 10 re-ingestion pass
that added the Chl-a fields, so the CDOM matchup population is a subset of
the exact same joined table :func:`pab.matchup.chl.data.load_chl_matchups`
already builds (it already carries ``cdom``/``cdom_std``/``cdom_data_mode``
and the fitted ``adg_bing`` amplitude alongside the Chl fields) — this module
re-exports that loader rather than re-deriving the same joins, and adds only
what is CDOM-specific: the validity filter and the caveat text every CDOM
figure must carry per C3.

**No ``cdom_adjusted`` field exists.** Per ``chl_cdom_prompt_1.md``'s Task 1
spot-check, GDAC's ``CDOM_ADJUSTED`` is empty fleet-wide (no BGC-Argo float has
ever had CDOM delayed-mode processed), and per that doc's Q1, JXP chose to
ingest raw ``cdom`` only pending a BGC-Argo consult on how to apply the
Sea-Bird 5.62x Reference Adjustment Factor — so there is nothing for a
"raw vs. adjusted" CDOM comparison to compare yet. Every figure here is raw
CDOM only; the Sea-Bird caveat is carried as text, not as a second series.

**Refinement pass (chl_cdom_matchups.md R1-R8).** Per R1/R3, the analysis
population is now restricted to ``cdom < 6`` ppb QSDE and AOML-processed
floats only (``valid_cdom()`` + :func:`restrict_to_aoml`), replacing the
prior unrestricted 7,083-matchup figures. Two further restrictions were
requested (R2: drop QC=4 points; R6: split by CDOM sensor model) but both
require a real re-ingestion pass — no per-level QC flag or sensor-model
field is stored anywhere in ``pab.db`` today, only the already-averaged
``mld_summary.cdom`` mean — so per R2(b)/R6(b) both are deferred to a
separate future pass, not applied here.
"""

from __future__ import annotations

import numpy as np

from pab.matchup.chl.data import DEFAULT_DB, load_chl_matchups  # noqa: F401 (re-export)

#: Per R1: strict "< 6", not "<= 6". Removes only 18 of 7,083 matchups.
CDOM_MAX = 6.0

#: Per C3: the two quantities are not the same thing, and PAB draws no
#: ppb -> absorption conversion. Every CDOM figure carries this verbatim.
QUANTITY_CAVEAT = (
    "Argo CDOM: fluorescence proxy (ppb QSDE). BING $A_{dg}$: combined\n"
    "CDOM + detrital absorption coefficient (m$^{-1}$). Different quantities —\n"
    "qualitative/correlative comparison only, no 1:1 or bias claim."
)

#: Per the chl_cdom_prompt_1.md Task 1 spot-check + chl_cdom_matchups.md's
#: CDOM exploration: raw CDOM from sensors calibrated/serviced before
#: 2023-01-13 (most of the historical fleet) reads ~5.62x too low per Sea-Bird
#: Scientific's Dec 2024 notice; a second, separate sensor-reference bias is
#: still unpublished. GDAC's CDOM_ADJUSTED is empty fleet-wide (confirmed
#: again below), so this correction is not baked into any value plotted here.
SEABIRD_CAVEAT = (
    "Raw CDOM only — no CDOM_ADJUSTED exists in GDAC (spot-checked fleet-wide,\n"
    "see chl_cdom_prompt_1.md Task 1). Sea-Bird's Dec-2024 notice implies most\n"
    "pre-2023-01-13 sensors read ~5.6x too low (uncorrected here, pending a\n"
    "BGC-Argo consult)."
)


def valid_cdom(df):
    """Rows with finite, positive raw ``cdom`` (< :data:`CDOM_MAX`, per R1) and fitted ``adg_bing``.

    Args:
        df: Frame from :func:`load_chl_matchups`.

    Returns:
        A filtered copy — the CDOM comparison population (~48% of the full
        Chl-a matchup set, consistent with the ~46% fleet-coverage figure in
        ``pab/argo/BGC_Argo_Coverage_Report.md``). Combine with
        :func:`restrict_to_aoml` for the R1-R8 refined analysis population.
    """
    ok = (
        df["cdom"].notna()
        & np.isfinite(df["cdom"])
        & (df["cdom"] > 0)
        & (df["cdom"] < CDOM_MAX)
        & df["adg_bing"].notna()
        & np.isfinite(df["adg_bing"])
        & (df["adg_bing"] > 0)
    )
    return df[ok].copy()


def restrict_to_aoml(df):
    """AOML-processed floats only (per R3 — combined with :func:`valid_cdom`'s cdom < 6 cut).

    Args:
        df: Frame already filtered by :func:`valid_cdom`.

    Returns:
        A filtered copy — 3,676 of the 3,690 AOML-in-``valid_cdom`` matchups
        survive the combined ``cdom < 6`` + AOML cut (verified: the two
        restrictions barely interact).
    """
    return df[df["is_aoml"]].copy()


def add_caveat_box(
    ax, *, text: str = QUANTITY_CAVEAT, loc: str = "lower right"
) -> None:
    """Stamp a small caveat text box on an axes (per C3, every CDOM figure needs one)."""
    xy = {
        "lower right": (0.98, 0.02, "right", "bottom"),
        "lower left": (0.02, 0.02, "left", "bottom"),
        "upper right": (0.98, 0.98, "right", "top"),
        "upper left": (0.02, 0.98, "left", "top"),
    }[loc]
    ax.text(
        xy[0],
        xy[1],
        text,
        transform=ax.transAxes,
        ha=xy[2],
        va=xy[3],
        fontsize=6.5,
        color="#555555",
        bbox={
            "boxstyle": "round",
            "facecolor": "white",
            "alpha": 0.75,
            "edgecolor": "#cccccc",
        },
    )

"""Shared analysis dataframe for the Chl-a deep-dive figure set.

Builds one enriched per-matchup table on top of
:func:`pab.metrics.compare.gather_matchups`, adding the geometry/strata joins
(``distance_km``, ``dtime_hours``, ``mld``, season/region/basin), the
DAC/provenance fields added by the Stage 10 re-ingestion pass
(``floats.data_center``, ``mld_summary.chla_adjusted``/``chla_data_mode``),
granule ``cloud_cover``, and the fitted CDOM/detrital amplitude
(``BING_ExpBPow_Adg``) used as a probe for the CDOM-confound hypothesis. Every
script in this subfolder starts from :func:`load_chl_matchups` rather than
re-deriving these joins, since they are needed by nearly every figure.

Relative difference follows the bbp700 convention throughout this project:
``(PACE - Argo) / PACE``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pab.config import DATA_DIR
from pab.metrics.compare import add_strata, gather_matchups

#: Default local DB path (``$PAB_DATA_DIR/pab.db``), replacing the
#: hardcoded ``/Users/alliejames/...`` paths in the original scripts.
DEFAULT_DB = DATA_DIR / "pab.db"

MODEL_PAIR = "ExpBPow"
ADG_QUANTITY = f"BING_{MODEL_PAIR}_Adg"


def basin_of(lat: float, lon: float) -> str:
    """Coarse ocean basin from a lon/lat pair (the bbp700 precedent's rule).

    Four basins: Southern (lat <= -35), Atlantic, Indian, Pacific — split on
    longitude bands. Not exact (no strait-level detail), but sufficient for a
    global stratification panel.
    """
    if lat <= -35:
        return "Southern"
    if -70 <= lon < 20:
        return "Atlantic"
    if 20 <= lon < 100:
        return "Indian"
    return "Pacific"


def rel_diff(sat, insitu):
    """``(sat - insitu) / sat`` as a numpy array (the project's bias convention)."""
    sat = np.asarray(sat, dtype=float)
    insitu = np.asarray(insitu, dtype=float)
    return (sat - insitu) / sat


def load_chl_matchups(
    db_path: str | Path | None = None, *, model_pair: str = MODEL_PAIR
):
    """Build the full enriched Chl-a matchup analysis dataframe.

    Args:
        db_path: Path to ``pab.db`` (default: :data:`DEFAULT_DB`).
        model_pair: Which BING fit family to pull (default ``"ExpBPow"``).

    Returns:
        A :class:`pandas.DataFrame`, one row per matchup with a BING fit,
        columns: everything from :func:`gather_matchups` plus
        ``distance_km``, ``dtime_hours``, ``mld``, ``season``, ``region``,
        ``basin``, ``chla_adjusted``, ``cdom``, ``cdom_std``,
        ``chla_data_mode``, ``cdom_data_mode``, ``bbp700_data_mode``,
        ``profile_data_mode``, ``project_name``, ``data_center``, ``is_aoml``,
        ``cloud_cover``, ``adg_bing``, ``rel_diff`` (chl, PACE-vs-raw-Argo),
        ``rel_diff_adjusted`` (chl, PACE-vs-adjusted-Argo), ``bbp_rel_diff``.
    """
    from pab.db.store import Store

    db_path = Path(db_path) if db_path is not None else DEFAULT_DB
    with Store.open(db_path, create=False) as store:
        df = gather_matchups(store, model_pair=model_pair)
        if df.empty:
            return df

        mtch = store.query_df(
            "SELECT matchup_id, profile_id, granule_id, distance_km, dtime_hours "
            "FROM matchups"
        )
        mld = store.query_df(
            "SELECT profile_id, mld, chla_adjusted, cdom, cdom_std, "
            "chla_data_mode, cdom_data_mode, bbp700_data_mode FROM mld_summary"
        )
        prof = store.query_df(
            "SELECT profile_id, wmo, data_mode AS profile_data_mode FROM profiles"
        )
        floats = store.query_df("SELECT wmo, project_name, data_center FROM floats")
        granules = store.query_df("SELECT granule_id, cloud_cover FROM granules")
        adg = store.query_df(
            "SELECT fit_id, value AS adg_bing FROM fit_results WHERE quantity = ?",
            (ADG_QUANTITY,),
        )

    df = df.merge(mtch, on="matchup_id", how="left")
    df = df.merge(mld, on="profile_id", how="left")
    df = df.merge(
        prof[["profile_id", "profile_data_mode"]], on="profile_id", how="left"
    )
    df = df.merge(floats, on="wmo", how="left")
    df = df.merge(granules, on="granule_id", how="left")
    df = df.merge(adg, on="fit_id", how="left")

    df = add_strata(df)
    df["basin"] = [
        basin_of(la, lo) for la, lo in zip(df["latitude"], df["longitude"], strict=True)
    ]

    df["is_aoml"] = df["data_center"] == "AO"
    df["rel_diff"] = rel_diff(df["chl_bing"], df["chla_argo"])
    df["rel_diff_adjusted"] = rel_diff(df["chl_bing"], df["chla_adjusted"])
    df["bbp_rel_diff"] = rel_diff(df["bbp_bing"], df["bbp_argo"])
    return df


def valid_chl(df, *, clip: float | None = None):
    """Rows with finite, positive ``chl_bing``/``chla_argo`` (and finite ``rel_diff``).

    Args:
        df: Frame from :func:`load_chl_matchups`.
        clip: If given, also require ``|rel_diff| <= clip`` (matching the
            bbp700 precedent's ``|rel_diff| <= 1.5`` outlier screen).

    Returns:
        A filtered copy.
    """
    ok = (
        np.isfinite(df["chl_bing"])
        & np.isfinite(df["chla_argo"])
        & (df["chl_bing"] > 0)
        & (df["chla_argo"] > 0)
        & np.isfinite(df["rel_diff"])
    )
    if clip is not None:
        ok &= df["rel_diff"].abs() <= clip
    return df[ok].copy()

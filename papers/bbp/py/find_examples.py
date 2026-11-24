"""
Find matchups that resemble the first scrutinized one, but under clearer skies
(``papers/bbp/prompts/scrutinize.md``, Prompts/Find examples 1-2).

The reference matchup (wmo 5906209, cycle 224) has Argo bbp(700) ~ 1.0e-3 m^-1
and PACE/Argo ~ 2 in a granule that is 81 % cloud. This script looks for
matchups with the same two bbp properties in granules that are < 50 % cloud,
observed close in time:

    Argo bbp(700)        ~ 1.0e-3 m^-1      (``mld_summary.bbp700``, MLD mean)
    PACE / Argo bbp(700) ~ 2                (PACE = v2.1 BING posterior median)
    granule cloud cover  < 50 %             (``granules.cloud_cover``)
    |PACE - Argo time|   <= 3 h             (``matchups.dtime_hours``)

"Approximately" is made concrete as a distance in log space,

    score = sqrt( ln(argo / 1e-3)^2 + ln(ratio / 2)^2 ),

so a factor-of-x miss in either quantity costs the same, and the matchups are
ranked by it (0 = exact). The cloud cover and the time difference are hard
cuts, not part of the score. The cloud cover is the cloud fraction of the whole
5-minute granule from NASA's metadata, *not* a measure of cloud near the pixel.

The list holds **one matchup per float**: each float's best-scoring matchup
(Q&A/Find examples 1, Q2), so the examples are spread over floats.

Only successful v2.1 BING fits are used (one per matchup: the rank-1 pixel).

Usage:
    python papers/bbp/py/find_examples.py            # top 20
    python papers/bbp/py/find_examples.py 40         # top 40
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from pab.config import DATA_DIR
from pab.viz import data as vdata

# ── defaults ──────────────────────────────────────────────────────────────────

DEFAULT_DB = Path(DATA_DIR) / "v2" / "pab.db"
PAB_VERSION = "2.1"
BBP_QUANTITY = "BING_ExpBPow_bbp700"

#: The targets (prompt 1).
ARGO_BBP_TARGET = 1.0e-3     # m^-1
RATIO_TARGET = 2.0           # PACE / Argo
CLOUD_MAX = 50.0             # percent, exclusive
DTIME_MAX = 3.0              # hours, inclusive (absolute PACE - Argo)

N_TOP = 20

SQL = """
SELECT p.wmo, p.cycle, p.time,
       x.latitude AS lat, x.longitude AS lon,
       g.cloud_cover,
       s.bbp700 AS bbp_argo,
       r.value AS bbp_pace, r.value_lo AS bbp_pace_lo, r.value_hi AS bbp_pace_hi,
       m.distance_km, m.dtime_hours, f.chisq, x.flagged,
       m.matchup_id
FROM fits f
JOIN fit_results r    ON r.fit_id = f.fit_id AND r.quantity = ?
JOIN matchups m       ON m.matchup_id = f.matchup_id
JOIN matchup_pixels x ON x.pixel_id = f.pixel_id
JOIN profiles p       ON p.profile_id = m.profile_id
JOIN mld_summary s    ON s.profile_id = m.profile_id
JOIN granules g       ON g.granule_id = m.granule_id
WHERE f.algorithm = 'BING' AND f.pab_version = ? AND f.success = 1
"""


# ── selection ─────────────────────────────────────────────────────────────────

def load_matchups(db=None) -> pd.DataFrame:
    """Every successful v2.1 BING matchup with a positive Argo and PACE bbp(700).

    Columns: ``wmo, cycle, time, lat, lon`` (the fitted PACE pixel),
    ``cloud_cover`` (granule, %), ``bbp_argo``, ``bbp_pace`` (+ 5-95 %),
    ``distance_km``, ``dtime_hours``, ``chisq``, ``flagged``, ``matchup_id``
    and ``ratio`` = PACE / Argo.
    """
    store = vdata.open_store(Path(db or DEFAULT_DB))
    try:
        df = store.query_df(SQL, (BBP_QUANTITY, PAB_VERSION))
    finally:
        store.close()
    ok = (np.isfinite(df["bbp_argo"]) & np.isfinite(df["bbp_pace"])
          & (df["bbp_argo"] > 0) & (df["bbp_pace"] > 0)
          & np.isfinite(df["cloud_cover"]))
    df = df[ok].copy()
    df["ratio"] = df["bbp_pace"] / df["bbp_argo"]
    return df


def find_examples(db=None, n: int = N_TOP, argo_target: float = ARGO_BBP_TARGET,
                  ratio_target: float = RATIO_TARGET,
                  cloud_max: float | None = CLOUD_MAX, dtime_max: float = DTIME_MAX,
                  one_per_float: bool = True) -> pd.DataFrame:
    """The ``n`` matchups closest to the targets that pass the hard cuts.

    Args:
        db: Path to ``pab.db``; default :data:`DEFAULT_DB`.
        n: Number of rows to return.
        argo_target, ratio_target: The targets of the score.
        cloud_max: Keep granules with cloud cover below this (percent);
            ``None`` applies no cloud cut.
        dtime_max: Keep matchups with ``|dtime_hours|`` at or below this.
        one_per_float: Keep only each float's best-scoring matchup.

    Returns:
        The :func:`load_matchups` frame after the cuts, with a ``score``
        column (log-space distance to the targets; see the module docstring),
        sorted by it and truncated to ``n`` rows. ``attrs`` records the
        counts at each step (``n_all``, ``n_cloud``, ``n_dtime``, ``n_floats``).
    """
    df = load_matchups(db)
    n_all = len(df)
    if cloud_max is not None:
        df = df[df["cloud_cover"] < cloud_max]
    n_cloud = len(df)
    df = df[df["dtime_hours"].abs() <= dtime_max].copy()
    n_dtime = len(df)
    df["score"] = np.hypot(np.log(df["bbp_argo"] / argo_target),
                           np.log(df["ratio"] / ratio_target))
    df = df.sort_values("score")
    if one_per_float:
        df = df.drop_duplicates("wmo", keep="first")
    out = df.head(n).reset_index(drop=True)
    out.attrs.update(n_all=n_all, n_cloud=n_cloud, n_dtime=n_dtime,
                     n_floats=df["wmo"].nunique())
    return out


def print_examples(df: pd.DataFrame) -> None:
    """Print the ranked table."""
    a = df.attrs
    print(f"{a['n_all']} v{PAB_VERSION} matchups -> {a['n_cloud']} with granule cloud "
          f"cover < {CLOUD_MAX:.0f} % -> {a['n_dtime']} with |dt| <= {DTIME_MAX:g} h "
          f"({a['n_floats']} floats)")
    print(f"top {len(df)} by score, one per float "
          f"(targets: Argo bbp700 = {ARGO_BBP_TARGET:.1e} m^-1, PACE/Argo = {RATIO_TARGET:g})\n")
    print(f"{'#':>2} {'wmo':>8} {'cyc':>4} {'date':>10} {'lat':>7} {'lon':>8} "
          f"{'cloud%':>6} {'Argo bbp':>9} {'PACE bbp':>9} {'ratio':>5} "
          f"{'dx km':>5} {'dt h':>5} {'chi2':>5} {'score':>5}")
    for i, r in df.iterrows():
        print(f"{i + 1:2d} {int(r.wmo):8d} {int(r.cycle):4d} {str(r.time)[:10]:>10} "
              f"{r.lat:7.2f} {r.lon:8.2f} {r.cloud_cover:6.1f} "
              f"{r.bbp_argo:9.2e} {r.bbp_pace:9.2e} {r.ratio:5.2f} "
              f"{r.distance_km:5.1f} {r.dtime_hours:5.1f} {r.chisq:5.2f} {r.score:5.3f}"
              f"{'  flagged' if r.flagged else ''}")


# ── main ──────────────────────────────────────────────────────────────────────

def main(n: int = N_TOP):
    """Print the top ``n`` examples."""
    print_examples(find_examples(n=n))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else N_TOP)

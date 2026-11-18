"""v2.1 Task 4: full-population 2.1 vs 2.0 numbers for ``geometry_rerun.md``.

Read-only on the live v2 DB. Every 2.1 fit is paired with its reference on
matchup **and pixel**: the 2.0 fit, or the 2.0.1 re-fit for the 51 runaways
(the overlay the site applies).

    python versions/v2.1/analyze_full.py --db $PAB_DATA_DIR/v2/pab.db

Writes ``full_summary.json``, ``full_table.csv`` (one row per pair) and
``fig_full_ratios.png`` next to this file.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
QTY = ("bbp700", "bbp440", "Aph", "chl", "Adg", "Sdg", "beta", "Bp")
BP_PRIOR = (0.004, 0.05)
EMU_BP = (0.01026, 0.018)
TS_BINS = [0, 20, 30, 40, 50, 90]
TV_BINS = [0, 25, 35, 45, 90]
STOP_BAND = (1.05, 1.25)  # R2-Q1: a full-run median outside this stops the close-out


def _ro(db):
    return sqlite3.connect(f"file:{Path(db).resolve()}?mode=ro", uri=True)


def _fits(c, version):
    df = pd.read_sql(
        "SELECT f.fit_id, f.matchup_id, f.pixel_id, f.chisq, f.accept_frac AS accept, "
        "f.success, r.quantity, r.value FROM fits f "
        "JOIN fit_results r USING (fit_id) "
        "WHERE f.algorithm = 'BING' AND f.pab_version = ?", c, params=(version,))
    df["quantity"] = df["quantity"].str.replace("BING_ExpBPow_", "", regex=False)
    w = df.pivot_table(index=["matchup_id", "pixel_id", "fit_id", "chisq", "accept", "success"],
                       columns="quantity", values="value").reset_index()
    return w.set_index(["matchup_id", "pixel_id"])


def _q(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if not x.size:
        return {"n": 0}
    p16, p50, p84 = np.percentile(x, [16, 50, 84])
    return {"n": int(x.size), "median": float(p50), "p16": float(p16), "p84": float(p84)}


def _bp_bounds(bp):
    span = BP_PRIOR[1] - BP_PRIOR[0]
    bp = np.asarray(bp, float)
    return {
        "median": float(np.nanmedian(bp)),
        "p16": float(np.nanpercentile(bp, 16)), "p84": float(np.nanpercentile(bp, 84)),
        "at_floor_2pct": int((bp < BP_PRIOR[0] + 0.02 * span).sum()),
        "at_ceiling_2pct": int((bp > BP_PRIOR[1] - 0.02 * span).sum()),
        "in_emulator_range": int(((bp >= EMU_BP[0]) & (bp <= EMU_BP[1])).sum()),
    }


def build(db) -> tuple[pd.DataFrame, dict]:
    c = _ro(db)
    new = _fits(c, "2.1")
    ref = _fits(c, "2.0")
    r201 = _fits(c, "2.0.1")
    ref["ref_version"] = "2.0"
    r201["ref_version"] = "2.0.1"
    ref = pd.concat([ref.drop(index=r201.index, errors="ignore"), r201])
    m = new.join(ref, lsuffix="_21", rsuffix="_ref", how="left")
    pix = pd.read_sql(
        "SELECT p.pixel_id, p.theta_s, p.theta_v, p.dphi, p.latitude, p.longitude, "
        "s.bbp700 AS bbp_float, s.chla AS chl_float, g.time_start AS time "
        "FROM matchup_pixels p JOIN matchups m USING (matchup_id) "
        "LEFT JOIN mld_summary s ON s.profile_id = m.profile_id "
        "LEFT JOIN granules g ON g.granule_id = m.granule_id", c)
    m = m.reset_index().merge(pix, on="pixel_id", how="left")
    spec = importlib.util.spec_from_file_location("make_slice", HERE / "make_slice.py")
    ms = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ms)
    m["basin"] = [ms.basin(a, b) if np.isfinite(a) and np.isfinite(b) else "?"
                  for a, b in zip(m["latitude"], m["longitude"], strict=True)]
    for q in QTY:
        m[f"{q}_ratio"] = m[f"{q}_21"] / m[f"{q}_ref"]
    for v in ("ref", "21"):
        m[f"delta_{v}"] = (m[f"bbp700_{v}"] - m["bbp_float"]) / m[f"bbp700_{v}"]

    S: dict = {"db": str(Path(db).resolve()), "n_2_1": int(len(new)),
               "n_paired": int(m["bbp700_ref"].notna().sum()),
               "ref_versions": m["ref_version"].value_counts().to_dict()}
    S["ratios"] = {q: _q(m[f"{q}_ratio"]) for q in QTY}
    r = m["bbp700_ratio"]
    med = S["ratios"]["bbp700"]["median"]
    S["stop_band"] = {"band": STOP_BAND, "median": med,
                      "inside": bool(STOP_BAND[0] <= med <= STOP_BAND[1])}
    ts = pd.cut(m["theta_s"], TS_BINS)
    tv = pd.cut(m["theta_v"], TV_BINS)
    S["bbp700_by_theta_s"] = {str(k): _q(g) for k, g in r.groupby(ts, observed=True)}
    S["bbp700_by_theta_v"] = {str(k): _q(g) for k, g in r.groupby(tv, observed=True)}
    S["bbp700_by_basin"] = {k: _q(g) for k, g in r.groupby(m["basin"])}
    S["grid_theta_s_x_theta_v"] = {
        f"{a}|{b}": _q(g) for (a, b), g in r.groupby([ts, tv], observed=True)}
    S["theta_s"] = _q(m["theta_s"])
    S["extremes"] = {
        "outside_1/3_3": int(((r < 1 / 3) | (r > 3)).sum()),
        "below_1/3": int((r < 1 / 3).sum()), "above_3": int((r > 3).sum()),
        "within_x1.5": float(((r > 1 / 1.5) & (r < 1.5)).mean()),
        "ref_bbp700_of_extremes": _q(m.loc[(r < 1 / 3) | (r > 3), "bbp700_ref"]),
    }
    S["bp"] = {"ref": _bp_bounds(m["Bp_ref"]), "2.1": _bp_bounds(m["Bp_21"])}
    S["chisq"] = {"ratio": _q(m["chisq_21"] / m["chisq_ref"]),
                  "ref": _q(m["chisq_ref"]), "2.1": _q(m["chisq_21"])}
    S["accept"] = {"ref": _q(m["accept_ref"]), "2.1": _q(m["accept_21"]),
                   "delta": _q(m["accept_21"] - m["accept_ref"])}
    S["lm_success"] = {
        "2.1": int(m["success_21"].sum()), "ref": int(m["success_ref"].sum()),
        "lost": int(((m["success_21"] == 0) & (m["success_ref"] == 1)).sum()),
        "gained": int(((m["success_21"] == 1) & (m["success_ref"] == 0)).sum()),
    }
    S["delta_float"] = {"ref": _q(m["delta_ref"]), "2.1": _q(m["delta_21"])}
    S["sat_over_float"] = {"ref": _q(m["bbp700_ref"] / m["bbp_float"]),
                           "2.1": _q(m["bbp700_21"] / m["bbp_float"])}
    S["failures_2_1"] = int(len(new) - m["bbp700_21"].notna().sum())
    S["implausible_2_1"] = int((m["bbp700_21"] > 1.0).sum())
    return m, S


def figure(m, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    ink, muted, grid = "#1f2328", "#59636e", "#d0d7de"
    line = "#2a6fdb"
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": muted, "axes.labelcolor": ink,
                         "xtick.color": muted, "ytick.color": muted})
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.9), constrained_layout=True)
    r = m["bbp700_ratio"].to_numpy(float)
    ts = m["theta_s"].to_numpy(float)
    edges = np.arange(0, 76, 5)
    mid, p50, p16, p84, n = [], [], [], [], []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        x = r[(ts >= lo) & (ts < hi) & np.isfinite(r)]
        if x.size >= 30:
            mid.append((lo + hi) / 2)
            p16.append(np.percentile(x, 16))
            p50.append(np.median(x))
            p84.append(np.percentile(x, 84))
            n.append(x.size)
    a1.fill_between(mid, p16, p84, color=line, alpha=0.18, linewidth=0)
    a1.plot(mid, p50, color=line, lw=2, marker="o", ms=4)
    a1.axhline(1, color=muted, lw=1, ls="--")
    a1.set_yscale("log")
    a1.set_yticks([0.6, 0.8, 1, 1.25, 1.6, 2])
    a1.set_yticklabels(["0.6", "0.8", "1", "1.25", "1.6", "2"])
    a1.minorticks_off()
    a1.set_ylim(0.55, 2.2)
    a1.set_xlabel("solar zenith θ_s of the pixel (°)")
    a1.set_ylabel("b_bp(700) ratio 2.1 / 2.0")
    a1.set_title("Median and 16–84 % band, 5° bins (n ≥ 30)", color=ink, fontsize=9)
    a1.grid(True, color=grid, lw=0.6)
    a1.set_axisbelow(True)
    for s in ("top", "right"):
        a1.spines[s].set_visible(False)

    tsb = np.arange(0, 80, 10)
    tvb = np.arange(10, 65, 5)
    grid_med = np.full((len(tvb) - 1, len(tsb) - 1), np.nan)
    tv = m["theta_v"].to_numpy(float)
    for i in range(len(tvb) - 1):
        for j in range(len(tsb) - 1):
            k = (tv >= tvb[i]) & (tv < tvb[i + 1]) & (ts >= tsb[j]) & (ts < tsb[j + 1])
            x = r[k & np.isfinite(r)]
            if x.size >= 20:
                grid_med[i, j] = np.median(x)
    im = a2.pcolormesh(tsb, tvb, grid_med, cmap="RdBu_r",
                       norm=LogNorm(vmin=1 / 1.6, vmax=1.6), edgecolors="white", linewidth=1.5)
    cb = fig.colorbar(im, ax=a2, shrink=0.9)
    cb.set_ticks([0.7, 0.85, 1, 1.2, 1.4])
    cb.set_ticklabels(["0.7", "0.85", "1", "1.2", "1.4"])
    cb.minorticks_off()
    cb.set_label("median b_bp(700) ratio 2.1 / 2.0")
    a2.set_xlabel("solar zenith θ_s (°)")
    a2.set_ylabel("view zenith θ_v (°)")
    a2.set_title("Median ratio per cell (≥ 20 fits; blank otherwise)", color=ink, fontsize=9)
    for s in ("top", "right"):
        a2.spines[s].set_visible(False)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", required=True)
    a = ap.parse_args(argv)
    m, S = build(a.db)
    (HERE / "full_summary.json").write_text(json.dumps(S, indent=1, default=str) + "\n")
    cols = ["matchup_id", "pixel_id", "fit_id_21", "fit_id_ref", "ref_version", "theta_s",
            "theta_v", "dphi", "basin", "bbp_float", "chl_float",
            *[f"{q}_{v}" for q in QTY for v in ("ref", "21")], "bbp700_ratio",
            "chisq_ref", "chisq_21", "accept_ref", "accept_21", "success_ref", "success_21"]
    m[cols].to_csv(HERE / "full_table.csv", index=False, float_format="%.6g")
    figure(m, HERE / "fig_full_ratios.png")
    print(json.dumps({k: S[k] for k in ("n_2_1", "n_paired", "ref_versions", "stop_band",
                                         "extremes", "lm_success", "failures_2_1")},
                     indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

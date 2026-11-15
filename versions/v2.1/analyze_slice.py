"""Analyse the v2.1 gate slice + fixed-B_p arm (build_v2_1_rerun.md Plan §3).

Reads (all read-only):
* the live v2 DB (the stored 2.0 / 2.0.1 reference fits, floats, pixels);
* ``<slice-root>/{main,arm_norm,arm_obs}/pab.db`` and their ``fit_chains/``
  (the slice pod's outputs, pulled back);
* ``slice_200.csv`` / ``bp_arm_50.csv`` beside this script.

Writes ``<out>/slice_summary.json``, ``<out>/slice_table.csv`` and figures
``<out>/fig_*.png``. The write-up (``geometry_rerun.md``) quotes these.

    PYTHONWARNINGS=ignore python versions/v2.1/analyze_slice.py \\
        --live-db $PAB_DATA_DIR/v2/pab.db --slice-root <dir> --out versions/v2.1
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sqlite3
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
QTY = ("bbp700", "Aph", "chl", "Adg", "Bp")
BP_PRIOR = (0.004, 0.05)
BP_FIXED = 0.014
VIEW_FEATURES = ("cos_theta_v", "cos_dphi")
PRED_BAND = (0.98, 1.20)  # the bbp700 pause trigger


def _ro(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def _sel(name):
    with open(HERE / name, newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in ("ix", "iy", "band", "success", "refit"):
            r[k] = int(r[k])
        for k in ("theta_s", "theta_v", "dphi", "latitude", "longitude"):
            r[k] = float(r[k])
    return rows


def _fits(conn, version=None, where=""):
    """{(matchup_id, ix, iy): {fit_id, chisq, accept, success, geom_mode, q...}}"""
    sql = (
        "SELECT f.fit_id, f.matchup_id, p.ix, p.iy, f.chisq, f.accept_frac, f.success, "
        "f.pab_version, " + ("f.geom_mode" if _has_col(conn, "fits", "geom_mode") else "NULL")
        + " AS geom_mode, r.quantity, r.value FROM fits f "
        "JOIN matchup_pixels p ON p.pixel_id = f.pixel_id "
        "LEFT JOIN fit_results r ON r.fit_id = f.fit_id "
        "WHERE f.algorithm = 'BING'" + (" AND f.pab_version = ?" if version else "") + where
    )
    out = {}
    for r in conn.execute(sql, (version,) if version else ()):
        key = (r["matchup_id"], r["ix"], r["iy"])
        d = out.setdefault(key, {"fit_id": r["fit_id"], "chisq": r["chisq"],
                                 "accept": r["accept_frac"], "success": r["success"],
                                 "geom_mode": r["geom_mode"], "version": r["pab_version"]})
        if r["quantity"]:
            d[r["quantity"].replace("BING_ExpBPow_", "")] = r["value"]
    return out


def _has_col(conn, table, col):
    return any(r[1] == col for r in conn.execute(f"PRAGMA table_info({table})"))


def _q(xs):
    xs = np.asarray([x for x in xs if x is not None and np.isfinite(x)], float)
    if not xs.size:
        return {"n": 0}
    p16, p50, p84 = np.percentile(xs, [16, 50, 84])
    return {"n": int(xs.size), "median": float(p50), "p16": float(p16), "p84": float(p84)}


def _wmedian(x, w):
    x, w = np.asarray(x, float), np.asarray(w, float)
    ok = np.isfinite(x) & np.isfinite(w)
    x, w = x[ok], w[ok]
    if not x.size:
        return float("nan")
    o = np.argsort(x)
    cw = np.cumsum(w[o])
    return float(x[o][np.searchsorted(cw, 0.5 * cw[-1])])


# ------------------------------------------------------------ forward model
def _state(npz, config, geom, chl):
    """Models + windowed spectrum + posterior median for one fit's NPZ."""
    from bing.models import utils as model_utils

    from pab.fit import run as frun
    from pab.fit.models import build_models

    with np.load(npz, allow_pickle=False) as z:
        wave = np.asarray(z["wave"], float)
        chains = np.asarray(z["chains"], float)
    _p, rt_dict, models = build_models(config, wave, geom=geom)
    model_utils.init_other_bits(models, Chl=np.array([chl if chl else 0.1]), Y=None, Rrs=None)
    frun.set_inelastic_Ed(models, geom, rt_dict)
    burn = config.analysis_burn if chains.shape[0] > config.analysis_burn else chains.shape[0] // 2
    med = np.median(chains[burn:].reshape(-1, chains.shape[-1]), axis=0)
    return dict(wave=wave, models=models, rt_dict=rt_dict, geom=geom, med=med)


def _rrs(st, params, bp=None):
    from pab.fit import run as frun

    a, b, bpp = frun._split_flat(np.asarray(params, float)[None, :], st["models"][0].nparam,
                                 st["rt_dict"])
    bp = float(bpp[0]) if bpp is not None else bp
    return np.squeeze(frun.reconstruct_rrs(st["models"], a[0], b[0], st["rt_dict"],
                                           geom=st["geom"], Bp=bp))


def _breaches(st):
    """Which emulator features are out of domain at the posterior median."""
    import bing.evaluate as ev
    from robust.rt import emulator as E

    from pab.fit import run as frun

    a, b, bpp = frun._split_flat(st["med"][None, :], st["models"][0].nparam, st["rt_dict"])
    bp = float(bpp[0]) if bpp is not None else float(st["rt_dict"].get("Bp_value", BP_FIXED))
    inp = ev._build_robust_inputs(st["models"][0], a[0], st["models"][1], b[0], st["rt_dict"],
                                  st["geom"], bp)
    rep = E.load_default().out_of_domain(inp.iops, inp.phase_params, inp.geometry,
                                         np.asarray(st["wave"], float))
    return sorted(rep)


def _pred_ratio(npz, theta, chl):
    """Rrs700(observed)/Rrs700(0,0,0) at the arm-O posterior median, B_p fixed."""
    from pab.fit import run as frun
    from pab.fit.models import FitConfig

    cfg_o = FitConfig.v2_0_1(fit_Bp=False, Bp_value=BP_FIXED)
    cfg_n = FitConfig(fit_Bp=False, Bp_value=BP_FIXED)
    so = _state(npz, cfg_o, frun.fit_geometry(cfg_o, *theta), chl)
    sn = _state(npz, cfg_n, frun.fit_geometry(cfg_n, *theta), chl)
    k = int(np.argmin(np.abs(so["wave"] - 700.0)))
    return float(_rrs(so, so["med"], BP_FIXED)[k] / _rrs(sn, so["med"], BP_FIXED)[k])


# --------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--live-db", required=True)
    ap.add_argument("--slice-root", required=True)
    ap.add_argument("--chains20", required=True, help="production fit_chains (2.0 NPZs)")
    ap.add_argument("--out", default=str(HERE))
    ap.add_argument("--no-forward", action="store_true", help="skip breach/prediction")
    a = ap.parse_args(argv)
    warnings.filterwarnings("ignore")
    root, out = Path(a.slice_root), Path(a.out)
    from pab.fit import run as frun
    from pab.fit.models import FitConfig

    sl, arm = _sel("slice_200.csv"), _sel("bp_arm_50.csv")
    live = _ro(a.live_db)
    ref20, ref201 = _fits(live, "2.0"), _fits(live, "2.0.1")
    floats = {r["matchup_id"]: (r["bbp700"], r["chla"]) for r in live.execute(
        "SELECT m.matchup_id, s.bbp700, s.chla FROM matchups m "
        "JOIN mld_summary s ON s.profile_id = m.profile_id")}
    # population weights (band x basin), for a population-weighted median
    spec = importlib.util.spec_from_file_location("make_slice", HERE / "make_slice.py")
    ms = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ms)
    pop = defaultdict(int)
    for r in live.execute(
        "SELECT p.theta_v, COALESCE(p.latitude, pr.latitude) la, "
        "COALESCE(p.longitude, pr.longitude) lo FROM fits f "
        "JOIN matchup_pixels p ON p.pixel_id = f.pixel_id JOIN matchups m ON m.matchup_id = f.matchup_id "
        "JOIN profiles pr ON pr.profile_id = m.profile_id "
        "WHERE f.algorithm = 'BING' AND f.pab_version = '2.0' AND p.theta_v IS NOT NULL"):
        pop[(ms.band_of(r["theta_v"]), ms.basin(r["la"], r["lo"]))] += 1
    live.close()
    samp = defaultdict(int)
    for r in sl:
        samp[(r["band"], r["basin"])] += 1

    passes = {}
    for p in ("main", "arm_norm", "arm_obs"):
        db = root / p / "pab.db"
        passes[p] = _fits(_ro(db), "2.1") if db.is_file() else {}

    rows = []
    for r in sl:
        key = (r["matchup_id"], r["ix"], r["iy"])
        ref = ref201.get(key) if r["refit"] else ref20.get(key)
        new = passes["main"].get(key)
        d = dict(r, ref_version="2.0.1" if r["refit"] else "2.0", fitted=new is not None,
                 w=pop[(r["band"], r["basin"])] / samp[(r["band"], r["basin"])])
        for q in QTY:
            d[f"{q}_ref"] = ref.get(q) if ref else None
            d[f"{q}_21"] = new.get(q) if new else None
            d[f"{q}_ratio"] = (d[f"{q}_21"] / d[f"{q}_ref"]
                               if new and ref and d[f"{q}_ref"] and d[f"{q}_21"] is not None else None)
        for k in ("chisq", "accept", "success"):
            d[f"{k}_ref"] = ref[k] if ref else None
            d[f"{k}_21"] = new[k] if new else None
        d["geom_mode_21"] = new["geom_mode"] if new else None
        fb, fc = floats.get(r["matchup_id"], (None, None))
        d["bbp_float"] = fb
        for v in ("ref", "21"):
            x = d[f"bbp700_{v}"]
            d[f"delta_{v}"] = (x - fb) / x if x and fb else None
        rows.append(d)

    S = {"n_slice": len(sl), "n_fitted": sum(d["fitted"] for d in rows)}
    S["failed"] = [d["matchup_id"] for d in rows if not d["fitted"]]
    S["geom_mode_21"] = sorted({str(d["geom_mode_21"]) for d in rows if d["fitted"]})
    S["lm_success_21"] = sum(1 for d in rows if d["success_21"] == 1)
    S["lm_success_ref"] = sum(1 for d in rows if d["success_ref"] == 1)
    for q in QTY:
        S[f"{q}_ratio"] = _q(d[f"{q}_ratio"] for d in rows)
        S[f"{q}_ratio_by_band"] = {b: _q(d[f"{q}_ratio"] for d in rows if d["band"] == b)
                                   for b in range(1, 5)}
    good = [d for d in rows if d["bbp700_ratio"] is not None]
    S["bbp700_ratio_popweighted"] = _wmedian([d["bbp700_ratio"] for d in good],
                                             [d["w"] for d in good])
    S["bbp700_ratio_no_refits"] = _q(d["bbp700_ratio"] for d in rows if not d["refit"])
    S["bbp700_ratio_by_theta_s"] = {
        f"{lo}-{hi}": _q(d["bbp700_ratio"] for d in rows if lo <= d["theta_s"] < hi)
        for lo, hi in ((0, 20), (20, 30), (30, 40), (40, 50), (50, 90))}
    S["trigger_bbp700"] = PRED_BAND
    for v in ("ref", "21"):
        bp = [d[f"Bp_{v}"] for d in rows if d[f"Bp_{v}"] is not None and d["fitted"]]
        bp = np.asarray(bp, float)
        span = BP_PRIOR[1] - BP_PRIOR[0]
        S[f"Bp_{v}"] = {**_q(bp), "at_floor_2pct": int(np.sum(bp <= BP_PRIOR[0] + 0.02 * span)),
                        "at_ceil_2pct": int(np.sum(bp >= BP_PRIOR[1] - 0.02 * span)),
                        "in_emulator_domain": int(np.sum((bp >= 0.010264) & (bp <= 0.018003)))}
        S[f"Bp_{v}_by_band"] = {b: _q(d[f"Bp_{v}"] for d in rows if d["band"] == b and d["fitted"])
                                for b in range(1, 5)}
        S[f"chisq_{v}"] = _q(d[f"chisq_{v}"] for d in rows if d["fitted"])
        S[f"accept_{v}"] = _q(d[f"accept_{v}"] for d in rows if d["fitted"])
        S[f"delta_{v}"] = _q(d[f"delta_{v}"] for d in rows if d["fitted"])
    S["chisq_ratio"] = _q(d["chisq_21"] / d["chisq_ref"] for d in rows
                          if d["fitted"] and d["chisq_ref"])
    S["accept_diff"] = _q(d["accept_21"] - d["accept_ref"] for d in rows
                          if d["fitted"] and d["accept_ref"] is not None)

    # ---------------------------------------------------------------- arm
    arows = []
    for r in arm:
        key = (r["matchup_id"], r["ix"], r["iy"])
        n, o = passes["arm_norm"].get(key), passes["arm_obs"].get(key)
        m = next(d for d in rows if (d["matchup_id"], d["ix"], d["iy"]) == key)
        e = dict(matchup_id=r["matchup_id"], band=r["band"], theta_s=r["theta_s"],
                 theta_v=r["theta_v"], dphi=r["dphi"],
                 bbp_N=n and n.get("bbp700"), bbp_O=o and o.get("bbp700"),
                 chisq_N=n and n["chisq"], chisq_O=o and o["chisq"],
                 geom_N=n and n["geom_mode"], geom_O=o and o["geom_mode"],
                 R_free=m["bbp700_ratio"], Bp_ref=m["Bp_ref"], Bp_21=m["Bp_21"],
                 chisq_free21=m["chisq_21"])
        e["R_fix"] = e["bbp_N"] / e["bbp_O"] if e["bbp_N"] and e["bbp_O"] else None
        e["pred"] = None
        npz_o = root / "arm_obs" / "fit_chains" / f"{o['fit_id']}.npz" if o else None
        if not a.no_forward and npz_o is not None and npz_o.is_file():
            try:
                e["pred"] = _pred_ratio(npz_o, (r["theta_s"], r["theta_v"], r["dphi"]),
                                        floats.get(r["matchup_id"], (None, None))[1])
            except Exception as exc:  # noqa: BLE001
                e["pred_error"] = repr(exc)
        arows.append(e)
    S["arm"] = {
        "n": len(arm), "n_both": sum(1 for e in arows if e["R_fix"] is not None),
        "geom_modes": sorted({(str(e["geom_N"]), str(e["geom_O"])) for e in arows
                              if e["R_fix"] is not None}),
        "R_fix": _q(e["R_fix"] for e in arows),
        "R_fix_by_band": {b: _q(e["R_fix"] for e in arows if e["band"] == b) for b in range(1, 5)},
        "pred": _q(e["pred"] for e in arows),
        "pred_by_band": {b: _q(e["pred"] for e in arows if e["band"] == b) for b in range(1, 5)},
        "R_fix_over_pred": _q(e["R_fix"] / e["pred"] for e in arows if e["R_fix"] and e["pred"]),
        "R_free": _q(e["R_free"] for e in arows),
        "R_free_by_band": {b: _q(e["R_free"] for e in arows if e["band"] == b) for b in range(1, 5)},
        "Bp_shift": _q(e["Bp_21"] - e["Bp_ref"] for e in arows if e["Bp_21"] and e["Bp_ref"]),
        "chisq_fixN_over_free21": _q(e["chisq_N"] / e["chisq_free21"] for e in arows
                                     if e["chisq_N"] and e["chisq_free21"]),
        "chisq_N_over_O": _q(e["chisq_N"] / e["chisq_O"] for e in arows
                             if e["chisq_N"] and e["chisq_O"]),
    }
    ok = [(e["pred"], e["R_fix"]) for e in arows if e["pred"] and e["R_fix"]]
    if len(ok) > 3:
        x, y = np.array(ok).T
        S["arm"]["pred_vs_Rfix_spearman"] = float(
            np.corrcoef(np.argsort(np.argsort(x)), np.argsort(np.argsort(y)))[0, 1])

    # ------------------------------------------------- domain breach mix
    if not a.no_forward:
        mix = {"2.0_observed": defaultdict(int), "2.1_normalized": defaultdict(int)}
        for d in rows:
            if not d["fitted"] or d["refit"]:
                continue
            theta = (d["theta_s"], d["theta_v"], d["dphi"])
            chl = floats.get(d["matchup_id"], (None, None))[1]
            for lab, cfg, npz in (
                ("2.0_observed", FitConfig.v2_0(),
                 Path(a.chains20) / f"{ref20[(d['matchup_id'], d['ix'], d['iy'])]['fit_id']}.npz"),
                ("2.1_normalized", FitConfig(),
                 root / "main" / "fit_chains"
                 / f"{passes['main'][(d['matchup_id'], d['ix'], d['iy'])]['fit_id']}.npz"),
            ):
                try:
                    feats = _breaches(_state(npz, cfg, frun.fit_geometry(cfg, *theta), chl))
                except Exception as exc:  # noqa: BLE001
                    feats = [f"error:{type(exc).__name__}"]
                mix[lab]["n"] += 1
                mix[lab]["any"] += bool(feats)
                mix[lab]["view"] += any(f in VIEW_FEATURES for f in feats)
                mix[lab]["iop_only"] += any(f not in VIEW_FEATURES for f in feats)
                for f in feats:
                    mix[lab][f] += 1
        S["breach_mix"] = {k: dict(v) for k, v in mix.items()}

    out.mkdir(parents=True, exist_ok=True)
    (out / "slice_summary.json").write_text(json.dumps(S, indent=1, default=str))
    cols = list(rows[0])
    with open(out / "slice_table.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    with open(out / "arm_table.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted({k for e in arows for k in e}))
        w.writeheader()
        w.writerows(arows)
    _figures(rows, arows, out)
    print(json.dumps({k: S[k] for k in ("n_slice", "n_fitted", "bbp700_ratio")}, default=str))
    print("arm R_fix", S["arm"]["R_fix"], "pred", S["arm"]["pred"], "R_free", S["arm"]["R_free"])


def _figures(rows, arows, out):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    good = [d for d in rows if d["bbp700_ratio"]]
    if len(good) < 3:
        return
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    for b, c in zip(range(1, 5), ("C0", "C1", "C2", "C3"), strict=True):
        x = [d["bbp700_ratio"] for d in good if d["band"] == b]
        ax[0].hist(np.log10(x), bins=20, histtype="step", color=c,
                   label=("θv<25", "25–35", "35–45", "≥45")[b - 1])
    ax[0].axvspan(np.log10(1.05), np.log10(1.10), color="0.85", label="analysis.md")
    ax[0].axvline(0, color="k", lw=0.8)
    ax[0].set_xlabel("log10 bbp700(2.1)/bbp700(ref)")
    ax[0].legend(fontsize=8)
    sc = ax[1].scatter([d["theta_v"] for d in good], [d["bbp700_ratio"] for d in good],
                       c=[d["theta_s"] for d in good], s=14, cmap="viridis")
    plt.colorbar(sc, ax=ax[1], label="θs (deg)")
    ax[1].axhline(1, color="k", lw=0.8)
    ax[1].set_yscale("log")
    ax[1].set_xlabel("θv (deg)")
    ax[1].set_ylabel("bbp700 ratio")
    bp = [(d["Bp_ref"], d["Bp_21"], d["band"]) for d in good if d["Bp_ref"] and d["Bp_21"]]
    if bp:
        x, y, b = np.array(bp).T
        ax[2].scatter(x, y, c=b, s=14, cmap="plasma")
        ax[2].plot([0.004, 0.05], [0.004, 0.05], "k-", lw=0.8)
        ax[2].axhspan(0.010264, 0.018003, color="0.9")
        ax[2].set_xlabel("B_p (ref)")
        ax[2].set_ylabel("B_p (2.1)")
    fig.tight_layout()
    fig.savefig(out / "fig_slice_ratios.png", dpi=110)
    plt.close(fig)

    ok = [e for e in arows if e["R_fix"]]
    if len(ok) >= 3:
        fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
        p = [e for e in ok if e["pred"]]
        if p:
            ax[0].scatter([e["pred"] for e in p], [e["R_fix"] for e in p],
                          c=[e["theta_v"] for e in p], s=18)
            lim = [0.8, 1.4]
            ax[0].plot(lim, lim, "k-", lw=0.8)
            ax[0].set_xlabel("predicted Rrs700(obs)/Rrs700(0,0,0)")
            ax[0].set_ylabel("R_fix = bbp700(arm-N)/bbp700(arm-O)")
        ax[1].scatter([e["theta_v"] for e in ok], [e["R_fix"] for e in ok], s=18, label="R_fix (B_p fixed)")
        ax[1].scatter([e["theta_v"] for e in ok if e["R_free"]],
                      [e["R_free"] for e in ok if e["R_free"]], s=18, marker="x",
                      label="R_free (2.1 / 2.0)")
        ax[1].axhline(1, color="k", lw=0.8)
        ax[1].set_xlabel("θv (deg)")
        ax[1].legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(out / "fig_bp_arm.png", dpi=110)
        plt.close(fig)


if __name__ == "__main__":
    main()

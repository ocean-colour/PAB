"""Task 1 end-of-task check (build_v2_1_rerun.md Plan §2): re-fit 5 cached
matchups under FitConfig() (2.1) and FitConfig.v2_0_1() on a scratch DB copy,
replaying the 2.0 spectrum; record the geometry every robust forward call saw.
No DB writes (persist=False path: gather -> replay -> fit_spectrum)."""
import json
import sys
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from pathlib import Path

SCR = Path(sys.argv[1])
CHAINS = Path(sys.argv[2])
MATCHUPS = [
    "1902458_65_PACE_OCI.20250317T082026.L2.OC_AOP.V3_2.nc",
    "3901578_115_PACE_OCI.20250122T142004.L2.OC_AOP.V3_2.nc",
    "1902453_70_PACE_OCI.20250424T074423.L2.OC_AOP.V3_2.nc",
    "3902581_83_PACE_OCI.20260130T063249.L2.OC_AOP.V3_2.nc",
    "1902499_86_PACE_OCI.20260619T122154.L2.OC_AOP.V3_2.nc",  # a 2.0.1 re-fit
]
KEEP = ("bbp700", "bbp440", "aph440", "adg440", "chl", "Bp")


def work(inp, mode):
    import time
    import warnings

    warnings.filterwarnings("ignore")
    from pab.parallel import init_worker

    init_worker()
    from bing.rt import geometry as G

    from pab.fit import FitConfig, run
    from pab.fit.replay import spectrum_from_chains

    seen = set()
    orig = G.ObsGeometry.to_robust

    def rec(self, Ed=None):
        seen.add((float(self.theta_s), float(self.theta_v), float(self.dphi)))
        return orig(self, Ed=Ed)

    G.ObsGeometry.to_robust = rec
    cfg = FitConfig() if mode == "2.1" else FitConfig.v2_0_1()
    geom = run._geometry_or_none(inp, cfg)
    wave, rrs, unc, src = spectrum_from_chains(CHAINS)(inp)
    t0 = time.process_time()
    res = run.fit_spectrum(wave, rrs, unc, Chl=inp["chl"], geom=geom, config=cfg)
    q = {d["quantity"]: (d["value"], d["value_lo"], d["value_hi"])
         for d in res.quantities if d["quantity"] in KEEP}
    return {
        "matchup_id": inp["matchup_id"], "mode": mode, "src": src,
        "geom_seen": sorted(seen), "q": q, "chisq": res.chisq,
        "accept": res.accept_frac, "success": res.success,
        "cpu_s": time.process_time() - t0,
    }


def main():
    from pab.db import Store
    from pab.fit import FitConfig, run

    store = Store.open(str(SCR / "pab.db"), create=False)
    jobs = []
    for m in MATCHUPS:
        inp = run._gather_fit_input(store, m, FitConfig())
        jobs += [(inp, "2.1"), (inp, "2.0.1")]
    stored = {}
    for m in MATCHUPS:
        rows = store.query(
            "SELECT f.fit_id, f.pab_version, f.chisq, f.accept_frac, r.quantity, "
            "r.value, r.value_lo, r.value_hi, p.theta_s, p.theta_v, p.dphi "
            "FROM fits f JOIN fit_results r ON r.fit_id = f.fit_id "
            "JOIN matchup_pixels p ON p.pixel_id = f.pixel_id "
            "WHERE f.matchup_id = ? AND f.algorithm = 'BING'", (m,))
        for r in rows:
            key = r["quantity"].replace("BING_ExpBPow_", "")
            if key in KEEP:
                d = stored.setdefault(m, {}).setdefault(r["pab_version"], {
                    "chisq": r["chisq"], "accept": r["accept_frac"],
                    "angles": (r["theta_s"], r["theta_v"], r["dphi"])})
                d[key] = (r["value"], r["value_lo"], r["value_hi"])
    store.close()
    with ProcessPoolExecutor(max_workers=len(jobs),
                             mp_context=mp.get_context("spawn")) as ex:
        out = list(ex.map(work, *zip(*jobs, strict=True)))
    (SCR / "check_out.json").write_text(json.dumps(
        {"fits": out, "stored": stored}, indent=1, default=str))
    print("done", len(out))


if __name__ == "__main__":
    main()

"""Example Argo profile for the CDOM report's methodology section.

Live-fetches one real BGC-Argo profile (default: WMO 5907147, cycle 258 — the
same matchup as `cdom_example_bing_fit.png`, so the report can walk through one
concrete float+PACE pair end to end) via the same `argopy` BGC `DataFetcher`
path the pipeline uses (`ds='bgc', src='gdac', mode='expert'`), and plots
CDOM + CHLA vs. pressure with the mixed-layer depth marked.

Deliberately does **not** call `pab.argo.fetch.filter_quality()` — verified
against the pipeline (`pab/pipeline.py::_fetch_profile_payload`) that no QC
screening is actually applied before `summarize_profile()` in production;
`filter_quality` exists but has no call site anywhere in the pipeline. This
script reproduces that as-ingested reality (all QC flags shown, colored by
QC value) rather than a cleaned-up illustration.

Usage
-----
    python pab/matchup/cdom/plot_cdom_example_profile.py
    python pab/matchup/cdom/plot_cdom_example_profile.py --wmo 5907147 --cycle 258
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

DEFAULT_WMO = 5907147
DEFAULT_CYCLE = 258
DEFAULT_MLD = 16.9  # m; from this profile's stored mld_summary row


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--wmo", type=int, default=DEFAULT_WMO)
    p.add_argument("--cycle", type=int, default=DEFAULT_CYCLE)
    p.add_argument("--mld", type=float, default=DEFAULT_MLD)
    p.add_argument("--out", type=Path, default=Path("cdom_example_argo_profile.png"))
    p.add_argument("--ymax", type=float, default=100.0, help="Pressure axis max (dbar)")
    p.add_argument("--dpi", type=int, default=200)
    return p.parse_args(argv)


def fetch_profile_arrays(wmo: int, cycle: int):
    """Live-fetch one BGC profile via the same path `pab.argo.fetch` uses."""
    from pab.argo.fetch import build_fetcher

    fetcher = build_fetcher(
        params=["CDOM", "CHLA", "PRES"], measured=None, mode="expert"
    )
    ds = fetcher.profile(wmo, cycle).load().data
    return {
        "pres": np.asarray(ds["PRES"].values, dtype=float),
        "cdom": np.asarray(ds["CDOM"].values, dtype=float),
        "cdom_qc": np.asarray(ds["CDOM_QC"].values, dtype=float),
        "chla": np.asarray(ds["CHLA"].values, dtype=float),
        "chla_qc": np.asarray(ds["CHLA_QC"].values, dtype=float),
    }


_QC_COLORS = {1: "#2ca25f", 2: "#99d8c9", 3: "#fdae6b", 4: "#e34a33"}
_QC_LABELS = {
    1: "QC=1 good",
    2: "QC=2 probably good",
    3: "QC=3 probably bad",
    4: "QC=4 bad",
}


def plot_example_profile(
    arrays, *, wmo, cycle, mld=None, ymax=100.0, outfile=None, dpi=200
):
    """CDOM + CHLA vs. pressure, points colored by their Argo QC flag.

    No QC screen is applied before plotting — matching the fact that
    `pab.pipeline` does not call `filter_quality()` before averaging into
    `mld_summary` (verified against the live pipeline code, not assumed).
    """
    pres = arrays["pres"]
    fig, axes = plt.subplots(1, 2, figsize=(7, 4.5), sharey=True)

    for ax, (name, values, qc) in zip(
        axes,
        [
            ("CDOM [ppb QSDE]", arrays["cdom"], arrays["cdom_qc"]),
            (r"CHLA [mg m$^{-3}$]", arrays["chla"], arrays["chla_qc"]),
        ],
        strict=True,
    ):
        ok = np.isfinite(values) & (pres <= ymax)
        for q in sorted(set(qc[ok].astype(int))):
            m = ok & (qc.astype(int) == q)
            ax.plot(
                values[m],
                pres[m],
                ".",
                ms=4,
                color=_QC_COLORS.get(q, "0.4"),
                label=_QC_LABELS.get(q, f"QC={q}"),
            )
        if mld is not None:
            ax.axhline(mld, color="k", ls="--", lw=1, label=f"MLD = {mld:.1f} m")
        ax.set_xlabel(name)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=6.5, loc="lower right")

    axes[0].set_ylabel("Pressure (dbar)")
    axes[0].set_ylim(ymax, 0)
    fig.suptitle(
        f"WMO {wmo} / cycle {cycle} — as fetched (no QC screen applied by PAB)",
        fontsize=10,
    )
    fig.tight_layout()

    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved -> {outfile}")
        return outfile
    return fig


def main(argv=None):
    args = _parse_args(argv)
    arrays = fetch_profile_arrays(args.wmo, args.cycle)
    plot_example_profile(
        arrays,
        wmo=args.wmo,
        cycle=args.cycle,
        mld=args.mld,
        ymax=args.ymax,
        outfile=args.out,
        dpi=args.dpi,
    )


if __name__ == "__main__":
    main()

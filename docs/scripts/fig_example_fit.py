"""Figure 2 for the PAB design document: an example BING fit.

Generates a real, data-backed two-panel figure from one of the BING fits
produced by the bing/papers/biomass/Analysis work:

  (a) the extracted PACE Rrs(λ) spectrum (with per-band uncertainty) and the
      BING reconstructed fit with its uncertainty envelope;
  (b) the retrieved non-water IOPs a_nw(λ) and b_b,nw(λ) with their 5–95%
      posterior envelopes.

This illustrates the core science of a single matchup: a PACE spectrum in,
IOPs + uncertainties out. (The companion float bbp(z)/MLD profile and the PACE
pixel-neighborhood panels require the raw Argo NetCDF and the PACE granule
respectively; see the design-doc Q&A.)

Usage:
    python docs/scripts/fig_example_fit.py [path_to_fits.npz] [out.png]

Defaults point at a biomass fit on this workstation and write
docs/figures/fig_example_fit.png.
"""
import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DEFAULT_NPZ = ("/home/xavier/Oceanography/python/bing/papers/biomass/"
               "Analysis/Argo_Constrained/Argo_6903823_387_fits.npz")
DEFAULT_OUT = os.path.join(os.path.dirname(__file__), "..", "figures",
                           "fig_example_fit.png")


def main(npz_path=DEFAULT_NPZ, out_path=DEFAULT_OUT):
    d = np.load(npz_path, allow_pickle=True)
    wave = d["wave"].astype(float)
    Rrs = d["Rrs"].astype(float)
    sigRrs = np.sqrt(d["varRrs"].astype(float))
    Rrs_recon = d["Rrs_recon"].astype(float)
    sig_recon = d["sigRrs_recon"].astype(float)
    a, a_lo, a_hi = d["a"], d["a_lo"], d["a_hi"]
    bb, bb_lo, bb_hi = d["bb"], d["bb_lo"], d["bb_hi"]

    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(9.0, 3.6))

    # Panel (a): Rrs observed + BING fit
    ax0.errorbar(wave, Rrs, yerr=sigRrs, fmt="o", ms=2.5, lw=0.6,
                 color="0.35", alpha=0.7, label="PACE Rrs (±σ)")
    ax0.plot(wave, Rrs_recon, "-", color="C3", lw=1.8, label="BING fit")
    ax0.fill_between(wave, Rrs_recon - sig_recon, Rrs_recon + sig_recon,
                     color="C3", alpha=0.25, lw=0)
    ax0.set_xlabel("wavelength [nm]")
    ax0.set_ylabel(r"$R_{rs}$ [sr$^{-1}$]")
    ax0.set_title("(a) Extracted PACE spectrum + BING fit", fontsize=10)
    ax0.legend(frameon=False, fontsize=8)

    # Panel (b): retrieved IOPs with envelopes
    ax1.plot(wave, a, "-", color="C0", lw=1.8, label=r"$a_{nw}(\lambda)$")
    ax1.fill_between(wave, a_lo, a_hi, color="C0", alpha=0.25, lw=0)
    ax1.plot(wave, bb, "-", color="C2", lw=1.8, label=r"$b_{b,nw}(\lambda)$")
    ax1.fill_between(wave, bb_lo, bb_hi, color="C2", alpha=0.25, lw=0)
    ax1.set_yscale("log")
    ax1.set_xlabel("wavelength [nm]")
    ax1.set_ylabel(r"IOP [m$^{-1}$]")
    ax1.set_title("(b) Retrieved IOPs (5–95% envelope)", fontsize=10)
    ax1.legend(frameon=False, fontsize=8)

    fig.tight_layout()
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Keep the file small (design-doc target ~100 KB)
    fig.savefig(out_path, dpi=110)
    print(f"Wrote {out_path} ({os.path.getsize(out_path)/1024:.0f} KB)")


if __name__ == "__main__":
    npz = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_NPZ
    out = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    main(npz, out)

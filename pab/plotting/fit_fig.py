"""Per-matchup BING fit figure (Stage 6).

Reconstructs a stored fit from its chains NPZ (:func:`pab.fit.artifacts.load_chains`)
and renders a compact, ~100 KB figure: the observed vs. model ``Rrs`` with the
posterior band, the residuals, and the retrieved ``b_bp(λ)`` credible band. The
**concept** follows BING's ``bing.plotting`` / the ``plot-bing-fit`` skill, but
this is PAB's own code, sized down (low DPI, two panels) from the ~1 MB biomass
figures.

``bing`` is imported lazily (the reconstruction needs the model objects); the
figure is therefore exercised only where ``bing`` + its model data are present.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

SIZE_BUDGET = 100 * 1024


def reconstruct_fit(store, fit_id: str):
    """Rebuild ``(wave, obs_Rrs, Rrs_med, Rrs_lo, Rrs_hi, bbp_med, bbp_lo, bbp_hi)``.

    Loads the fit's chains NPZ and ``fits`` row, rebuilds the BING models on the
    saved wavelength grid, and evaluates the posterior (``b_bp(λ)`` via the
    non-water backscatter model; model ``Rrs`` via the Gordon forward model).
    """
    import bing.evaluate as ev
    from bing.models import utils as model_utils

    from pab.fit import artifacts
    from pab.fit.models import FitConfig, build_models

    row = store.query("SELECT * FROM fits WHERE fit_id = ?", (fit_id,))
    if not row:
        raise ValueError(f"no fit {fit_id!r}")
    row = row[0]
    npz = artifacts.load_chains(fit_id)
    wave = np.asarray(npz["wave"], dtype=float)
    obs = np.asarray(npz["Rrs"], dtype=float)
    chains = np.asarray(npz["chains"], dtype=float)
    chl = float(npz["Chl"]) if np.isfinite(npz["Chl"]) else None

    config = FitConfig(
        model_pair=row["model_pair"],
        wave_min=float(row["wave_min"]),
        wave_max=float(row["wave_max"]),
        nsteps=int(row["nsteps"]),
    )
    _, rt_dict, models = build_models(config, wave)
    model_utils.init_other_bits(
        models, Chl=None if chl is None else np.array([chl]), Y=None, Rrs=obs
    )

    burn = config.analysis_burn
    if chains.shape[0] <= burn:
        burn = chains.shape[0] // 2
    flat = ev.thin_burn_chains(chains, burn=burn)
    na = models[0].nparam

    rrs_samples = ev.calc_Rrs_from_models(
        models[0], flat[:, :na], models[1], flat[:, na:], rt_dict
    )
    rrs_med = np.median(rrs_samples, axis=0)
    rrs_lo, rrs_hi = np.percentile(rrs_samples, [5, 95], axis=0)
    bbnw = models[1].eval_bbnw(flat[:, na:], wave=wave)
    bbp_med = np.median(bbnw, axis=0)
    bbp_lo, bbp_hi = np.percentile(bbnw, [5, 95], axis=0)
    return wave, obs, rrs_med, rrs_lo, rrs_hi, bbp_med, bbp_lo, bbp_hi


def fit_figure(store, fit_id: str, *, outfile=None, dpi: int = 100):
    """Render the two-panel fit figure for ``fit_id``.

    Top: observed vs. model ``Rrs`` (median + 5–95% band) and the residual.
    Bottom: the retrieved ``b_bp(λ)`` with its credible band (700 nm marked).

    Returns:
        The Matplotlib ``Figure`` (or the written ``Path`` when ``outfile``).
    """
    import matplotlib.pyplot as plt

    wave, obs, rrs_med, rrs_lo, rrs_hi, bbp_med, bbp_lo, bbp_hi = reconstruct_fit(
        store, fit_id
    )
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(6, 6), sharex=True)
    a1.fill_between(wave, rrs_lo, rrs_hi, color="C0", alpha=0.3, label="5–95%")
    a1.plot(wave, rrs_med, "C0-", lw=1.3, label="BING median")
    a1.plot(wave, obs, "k.", ms=4, label="observed")
    a1.set_ylabel("Rrs (sr$^{-1}$)")
    a1.legend(fontsize=8)
    a1.grid(alpha=0.3)
    a1.set_title(fit_id, fontsize=9)

    a2.fill_between(wave, bbp_lo, bbp_hi, color="C1", alpha=0.3, label="5–95%")
    a2.plot(wave, bbp_med, "C1-", lw=1.3, label="median")
    a2.axvline(700.0, color="0.6", ls=":")
    a2.set_xlabel("wavelength (nm)")
    a2.set_ylabel("$b_{bp}(\\lambda)$ (m$^{-1}$)")
    a2.legend(fontsize=8)
    a2.grid(alpha=0.3)
    fig.tight_layout()

    if outfile is not None:
        outfile = Path(outfile)
        fig.savefig(outfile, dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        return outfile
    return fig

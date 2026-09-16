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


def _config_from_row(config_row):
    """Rebuild the :class:`~pab.fit.models.FitConfig` a stored fit ran under.

    Reads the schema-v5 RT columns. A legacy 1.0 row has them NULL, which maps
    to the Gordon/elastic configuration it was actually fitted with — hence
    :meth:`~pab.fit.models.FitConfig.v1` as the base rather than the 2.0
    defaults, which would claim physics that row never saw.
    """
    from pab.fit.models import FitConfig

    def _flag(name, default=False):
        v = config_row[name] if name in config_row.keys() else None
        return default if v is None else bool(v)

    backend = config_row["rt_backend"] if "rt_backend" in config_row.keys() else None
    phi_c = config_row["phi_c"] if "phi_c" in config_row.keys() else None
    return FitConfig.v1(
        model_pair=config_row["model_pair"],
        wave_min=float(config_row["wave_min"]),
        wave_max=float(config_row["wave_max"]),
        nsteps=int(config_row["nsteps"]),
        rt_backend=backend or "gordon",
        include_Raman=_flag("include_raman"),
        include_Chl_fl=_flag("include_chl_fl"),
        include_CDOM_fl=_flag("include_cdom_fl"),
        fit_Bp=_flag("fit_bp"),
        phi_C=0.02 if phi_c is None else float(phi_c),
    )


def _geometry_from_row(store, config_row):
    """The fit's pixel geometry, read back from ``matchup_pixels``.

    Returns ``None`` when the pixel has none — ``build_models`` will then raise
    for a robust backend, which is correct: a robust fit cannot be reconstructed
    without the geometry it was fitted at.
    """
    from pab.fit import run

    px = store.query(
        "SELECT theta_s, theta_v, dphi FROM matchup_pixels WHERE pixel_id = ?",
        (config_row["pixel_id"],),
    )
    if not px:
        return None
    return run.obs_geometry(px[0]["theta_s"], px[0]["theta_v"], px[0]["dphi"])


def reconstruct_fit(store, fit_id: str):
    """Rebuild ``(wave, obs_Rrs, Rrs_med, Rrs_lo, Rrs_hi, bbp_med, bbp_lo, bbp_hi)``.

    Loads the fit's chains NPZ and ``fits`` row, rebuilds the BING models on the
    saved wavelength grid, and evaluates the posterior (``b_bp(λ)`` via the
    non-water backscatter model; model ``Rrs`` via **the forward model the fit
    actually used**).

    The RT configuration is read back out of the ``fits`` row (schema v5) and
    the viewing geometry out of the fit's ``matchup_pixels`` row, so a
    ``robust_*`` fit is reconstructed with ``calc_Rrs_from_models_robust`` and
    its free ``B_p``, not with the elastic Gordon relation. A legacy 1.0 row has
    ``rt_backend`` NULL and falls back to Gordon, which is what it was fitted
    with.
    """
    import bing.evaluate as ev
    from bing.models import utils as model_utils

    from pab.fit import artifacts, run
    from pab.fit.models import build_models

    row = store.query("SELECT * FROM fits WHERE fit_id = ?", (fit_id,))
    if not row:
        raise ValueError(f"no fit {fit_id!r}")
    row = row[0]
    npz = artifacts.load_chains(fit_id)
    wave = np.asarray(npz["wave"], dtype=float)
    obs = np.asarray(npz["Rrs"], dtype=float)
    chains = np.asarray(npz["chains"], dtype=float)
    chl = float(npz["Chl"]) if np.isfinite(npz["Chl"]) else None

    config = _config_from_row(row)
    geom = _geometry_from_row(store, row) if run.requires_geometry(config) else None
    _, rt_dict, models = build_models(config, wave, geom=geom)
    model_utils.init_other_bits(
        models, Chl=None if chl is None else np.array([chl]), Y=None, Rrs=obs
    )
    run.set_inelastic_Ed(models, geom, rt_dict)

    burn = config.analysis_burn
    if chains.shape[0] <= burn:
        burn = chains.shape[0] // 2
    flat = ev.thin_burn_chains(chains, burn=burn)
    na = models[0].nparam
    # Peel any trailing free B_p before the a/bb split, exactly as the fit did.
    a_flat, bb_flat, bp_flat = run._split_flat(flat, na, rt_dict)

    rrs_samples = run.reconstruct_rrs(
        models, a_flat, bb_flat, rt_dict, geom=geom, Bp=bp_flat
    )
    rrs_med = np.median(rrs_samples, axis=0)
    rrs_lo, rrs_hi = np.percentile(rrs_samples, [5, 95], axis=0)
    bbnw = models[1].eval_bbnw(bb_flat, wave=wave)
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

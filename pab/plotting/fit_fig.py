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
    :meth:`~pab.fit.models.FitConfig.v1` as the base rather than the 2.0.1
    defaults, which would claim physics (and prior ceilings) that row never
    saw. The prior ceilings come back out of ``prior_set``
    (:func:`~pab.fit.models.ceilings_from_prior_set`): ``'bing_standard'`` —
    every 1.0 and 2.0 row — means none, a 2.0.1 ceiling string restores the
    ceilings it names, so ``prior_set_label(_config_from_row(row)) ==
    row["prior_set"]``. Reconstruction itself needs no priors (it evaluates
    the stored posterior), but the rebuilt config must not misdescribe the
    fit.

    ``geometry_mode`` comes from the schema-v6 ``geom_mode`` column; NULL
    (every row written before 2.1, and a row read from a v5 file) means
    ``'observed'``, which is what those fits used.
    """
    from pab.fit.models import GEOM_OBSERVED, FitConfig, ceilings_from_prior_set

    def _flag(name, default=False):
        v = config_row[name] if name in config_row.keys() else None
        return default if v is None else bool(v)

    backend = config_row["rt_backend"] if "rt_backend" in config_row.keys() else None
    phi_c = config_row["phi_c"] if "phi_c" in config_row.keys() else None
    prior_set = config_row["prior_set"] if "prior_set" in config_row.keys() else None
    geom_mode = config_row["geom_mode"] if "geom_mode" in config_row.keys() else None
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
        geometry_mode=geom_mode or GEOM_OBSERVED,
        **ceilings_from_prior_set(prior_set),
    )


def _geometry_from_row(store, config_row, config=None):
    """The geometry the fit's forward model ran at.

    Dispatches on the row's ``geom_mode`` through
    :func:`pab.fit.run.fit_geometry` — the resolver the fit itself used — so a
    2.1 (``'normalized'``) fit is redrawn at (0, 0, 0) and a 2.0 / 2.0.1
    (``'observed'``, or NULL) fit at its pixel's angles, read back from
    ``matchup_pixels``.

    Returns ``None`` for an observed-mode fit whose pixel has no angles (and
    for Gordon) — ``build_models`` will then raise for a robust backend, which
    is correct: a robust fit cannot be reconstructed without the geometry it
    was fitted at.
    """
    from pab.fit import run

    config = config if config is not None else _config_from_row(config_row)
    if not run.requires_pixel_angles(config):
        return run.fit_geometry(config, None, None, None)
    px = store.query(
        "SELECT theta_s, theta_v, dphi FROM matchup_pixels WHERE pixel_id = ?",
        (config_row["pixel_id"],),
    )
    if not px:
        return None
    return run.fit_geometry(config, px[0]["theta_s"], px[0]["theta_v"], px[0]["dphi"])


def _band(samples):
    """``(median, 5 %, 95 %)`` over the posterior samples (axis 0)."""
    med = np.median(samples, axis=0)
    lo, hi = np.percentile(samples, [5, 95], axis=0)
    return med, lo, hi


def reconstruct_posterior(store, fit_id: str, *, iops: bool = False) -> dict:
    """Rebuild a stored fit's posterior on its own wavelength grid.

    Loads the fit's chains NPZ and ``fits`` row, rebuilds the BING models on the
    saved wavelength grid, and evaluates the posterior (``b_bp(λ)`` via the
    non-water backscatter model; model ``Rrs`` via **the forward model the fit
    actually used**).

    The RT configuration is read back out of the ``fits`` row (schema v5) and
    the viewing geometry is resolved from its ``geom_mode`` (schema v6):
    (0, 0, 0) for a 2.1 fit, the fit's ``matchup_pixels`` angles otherwise,
    so a
    ``robust_*`` fit is reconstructed with ``calc_Rrs_from_models_robust`` and
    its free ``B_p``, not with the elastic Gordon relation. A legacy 1.0 row has
    ``rt_backend`` NULL and falls back to Gordon, which is what it was fitted
    with.

    Returns a dict of arrays: ``wave``, ``obs``, and ``(median, 5 %, 95 %)``
    triples ``rrs`` and ``bbp``. With ``iops`` it adds the non-water
    absorption triples ``anw`` and, for a model with a separable CDOM +
    detritus term, ``adg`` and ``aph`` (else ``None``).
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
    geom = _geometry_from_row(store, row, config)
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
    out = {
        "wave": wave,
        "obs": obs,
        "rrs": _band(rrs_samples),
        "bbp": _band(models[1].eval_bbnw(bb_flat, wave=wave)),
    }
    if iops:
        anw_model = models[0]
        if getattr(anw_model, "has_a_dg", False):
            a_dg, a_ph = anw_model.eval_anw(a_flat, retsub_comps=True, wave=wave)
            out["adg"], out["aph"] = _band(a_dg), _band(a_ph)
            out["anw"] = _band(a_dg + a_ph)
        else:
            out["adg"] = out["aph"] = None
            out["anw"] = _band(anw_model.eval_anw(a_flat, wave=wave))
    return out


def reconstruct_fit(store, fit_id: str):
    """Rebuild ``(wave, obs_Rrs, Rrs_med, Rrs_lo, Rrs_hi, bbp_med, bbp_lo, bbp_hi)``.

    The tuple form of :func:`reconstruct_posterior` (which see).
    """
    post = reconstruct_posterior(store, fit_id)
    return (post["wave"], post["obs"], *post["rrs"], *post["bbp"])


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

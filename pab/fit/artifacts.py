"""Fit artifacts & persistence (Stage 5).

Writes the bulky MCMC chains to an NPZ on disk (keyed by ``fit_id``, under
``PAB_DATA_DIR``) and the scalar fit + namespaced IOP quantities to the DB
(``fits`` + ``fit_results``), stamped with provenance. Chains stay out of the
database — ``fits.chains_path`` records where they live.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from pab.config import DATA_DIR, pab_version, package_versions

if TYPE_CHECKING:
    from pab.fit.run import FitSpectrumResult

#: Subdirectory of ``PAB_DATA_DIR`` holding the per-fit chain NPZ files.
CHAINS_SUBDIR = "fit_chains"


def chains_path(fit_id: str) -> Path:
    """Path to the NPZ chain file for ``fit_id`` (not created)."""
    return Path(DATA_DIR) / CHAINS_SUBDIR / f"{fit_id}.npz"


def save_chains(fit_id: str, result: FitSpectrumResult) -> Path:
    """Write the MCMC chains + inputs to ``chains_path(fit_id)``; return it.

    Stores ``chains`` (nsteps, nwalkers, nparam), the windowed ``wave``/``Rrs``/
    ``varRrs``, the parameter names, and ``Chl``.
    """
    path = chains_path(fit_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        chains=result.chains.astype(np.float32),
        wave=result.wave,
        Rrs=result.Rrs,
        varRrs=result.varRrs,
        param_names=np.array(result.param_names),
        Chl=result.Chl,
    )
    return path


def load_chains(fit_id: str) -> dict[str, Any]:
    """Load a fit's NPZ chain file into a dict."""
    with np.load(chains_path(fit_id), allow_pickle=False) as npz:
        return {k: npz[k] for k in npz.files}


def persist_fit(
    store,
    *,
    fit_id: str,
    matchup_id: str,
    pixel_id: int | None,
    result: FitSpectrumResult,
    config,
    rrs_source: str = "L2_AOP",
    chains_path: str | None = None,
    figure_path: str | None = None,
    created: str | None = None,
) -> str:
    """Upsert the ``fits`` row and its namespaced ``fit_results`` (idempotent).

    Quantities are namespaced ``BING_<model_pair>_<quantity>``. Provenance
    (``pab_version``, ``created``, ``pkg_versions``) is stamped on the ``fits``
    row.

    Returns:
        The ``fit_id``.
    """
    created = created or datetime.now(UTC).isoformat()
    store.upsert(
        "fits",
        {
            "fit_id": fit_id,
            "matchup_id": matchup_id,
            "pixel_id": pixel_id,
            "algorithm": "BING",
            "model_pair": config.model_pair,
            "anw_model": result.anw_model,
            "bbnw_model": result.bbnw_model,
            "rrs_source": rrs_source,
            "prior_set": "bing_standard",
            "nsteps": config.nsteps,
            "nburn": config.nburn,
            "nwalkers": result.nwalkers,
            "wave_min": config.wave_min,
            "wave_max": config.wave_max,
            "chisq": result.chisq,
            "aic": result.aic,
            "bic": result.bic,
            "accept_frac": result.accept_frac,
            "success": int(result.success),
            "chains_path": chains_path,
            "figure_path": figure_path,
            "pkg_versions": json.dumps(package_versions()),
            "pab_version": pab_version,
            "created": created,
        },
    )
    prefix = f"BING_{config.model_pair}_"
    rows = [
        {
            "fit_id": fit_id,
            "quantity": f"{prefix}{q['quantity']}",
            "value": q["value"],
            "value_lo": q["value_lo"],
            "value_hi": q["value_hi"],
            "unit": q["unit"],
        }
        for q in result.quantities
    ]
    # replace prior rows for this fit so a re-run leaves no stale quantities
    store.execute("DELETE FROM fit_results WHERE fit_id = ?", (fit_id,))
    store.upsert_many("fit_results", rows)
    return fit_id

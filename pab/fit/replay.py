"""Replay a stored fit's input spectrum (the 2.0.1 re-fit seam; Q&A/Outliers 8 = C).

The 2.0.1 re-fit of the 51 runaways must differ from the 2.0 fit by the prior
ceilings and **nothing else**. Re-reading the pixel from the granule would not
guarantee that: it costs ~25 GB of off-cloud downloads (or a pod image rebuild),
and NASA may have reprocessed the L2 files since the 2.0 run, so a different
``Rrs`` would confound a test whose only intended change is the prior. The
chain NPZ of every 2.0 fit holds ``wave``, ``Rrs`` and ``varRrs`` **exactly as
``prepare_spectrum`` produced them** (``pab.fit.artifacts.save_chains``), so
replaying from there gives the 2.0.1 fit a bit-identical input.

:func:`spectrum_from_chains` returns the provider ``build_fits(…, spectra=)``
and ``fit_matchup(…, spectrum=)`` accept: ``inp -> (wave, Rrs, Rrs_unc,
rrs_source)``. The fourth element stamps ``fits.rrs_source`` as
``"L2_AOP:replay:<2.0 fit_id>"`` so the provenance says where the spectrum
came from. With a provider, **no granule is opened**.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pab.fit.run import RRS_SOURCE_L2, make_fit_id

#: The version whose fits are replayed by default — the 2.0 release.
REPLAY_VERSION = "2.0"

#: ``fits.rrs_source`` prefix of a replayed spectrum; the replayed ``fit_id``
#: follows.
REPLAY_SOURCE_PREFIX = RRS_SOURCE_L2 + ":replay:"


def replay_source(fit_id: str) -> str:
    """The ``rrs_source`` stamp for a spectrum replayed from ``fit_id``'s NPZ."""
    return REPLAY_SOURCE_PREFIX + fit_id


def replayed_fit_id(rrs_source: str | None) -> str | None:
    """Invert :func:`replay_source`: the replayed ``fit_id``, or ``None`` for a
    spectrum that was read from the granule (or an unknown stamp)."""
    if rrs_source and rrs_source.startswith(REPLAY_SOURCE_PREFIX):
        return rrs_source[len(REPLAY_SOURCE_PREFIX):]
    return None


def chain_file(root, matchup_id: str, ix: int, iy: int, model_pair: str,
               *, version: str = REPLAY_VERSION) -> Path:
    """The NPZ under ``root`` holding the ``version`` fit of this pixel.

    Resolved by **basename** (``<fit_id>.npz``), never by ``fits.chains_path``:
    the stored paths are PVC paths (``/data/v2/fit_chains/…``) and the chains
    now live at ``$PAB_DATA_DIR/v2/fit_chains/`` on the workstation (O4).
    """
    fit_id = make_fit_id(matchup_id, ix, iy, model_pair, version=version)
    return Path(root) / f"{fit_id}.npz"


def load_spectrum(path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(wave, Rrs, Rrs_unc)`` from a chain NPZ — the windowed spectrum the
    fit saw, with ``Rrs_unc = sqrt(varRrs)``.

    Only the three small arrays are read (``np.load`` is lazy per key; the
    chains themselves stay compressed on disk). ``prepare_spectrum`` turns
    ``Rrs_unc`` back into ``Rrs_unc**2``, so the fit's ``varRrs`` is the stored
    one to rounding; the 400–700 window is a pass-through because the stored
    grid is already inside it.

    Raises:
        FileNotFoundError: if ``path`` does not exist (``build_fits`` records
            that matchup under ``"failed"`` and goes on).
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"no chain NPZ to replay at {path}")
    with np.load(path, allow_pickle=False) as npz:
        wave = np.asarray(npz["wave"], dtype=float)
        rrs = np.asarray(npz["Rrs"], dtype=float)
        var = np.asarray(npz["varRrs"], dtype=float)
    return wave, rrs, np.sqrt(var)


def spectrum_from_chains(root, *, version: str = REPLAY_VERSION):
    """Build the replay provider for ``build_fits(…, spectra=)``.

    The returned callable takes the fit-input dict ``build_fits`` gathers
    (``matchup_id``, ``ix``, ``iy``, ``model_pair``), names the **``version``**
    (default 2.0) fit of the same matchup *and pixel* with
    :func:`pab.fit.run.make_fit_id`, loads its NPZ under ``root`` by basename
    and returns ``(wave, Rrs, sqrt(varRrs), "L2_AOP:replay:<that fit_id>")``.

    Args:
        root: Directory holding the chain NPZs (``$PAB_DATA_DIR/v2/fit_chains``).
        version: ``pab_version`` of the fits to replay.

    Returns:
        The provider. Its ``root`` and ``version`` are exposed as attributes
        and it has a readable ``__name__`` for the ``build_fits`` log line.
    """
    root = Path(root)

    def replay(inp):
        path = chain_file(
            root, inp["matchup_id"], inp["ix"], inp["iy"], inp["model_pair"],
            version=version,
        )
        wave, rrs, unc = load_spectrum(path)
        return wave, rrs, unc, replay_source(path.stem)

    replay.__name__ = f"spectrum_from_chains({root}, version={version!r})"
    replay.root = root  # type: ignore[attr-defined]
    replay.version = version  # type: ignore[attr-defined]
    return replay

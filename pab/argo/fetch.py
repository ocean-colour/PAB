"""BGC-Argo access via argopy (the ingestion seam).

Thin wrappers over ``argopy.DataFetcher`` configured for biogeochemical data
(``ds='bgc'``). The **default source is ``src='gdac'``** — it reads the GDAC
netCDF directly and is markedly more reliable than the Ifremer BGC ERDDAP, which
has repeatedly returned ``408``/timeout/``404`` errors; ``src='erddap'`` (and
``'argovis'`` for core data) remain selectable. The design selects data by
region / float / profile, narrows with the BGC-only ``params`` and ``measured``
keywords, applies QC and data-mode filtering, and reshapes points → profiles
before the mixed-layer summary (:mod:`pab.argo.summary`).

Note on ``mode``: for a **recent real-time** profile the delayed-mode/adjusted
fields ``standard``/``research`` prefer may not exist yet, so a ``gdac`` fetch in
those modes can return zero points. Use ``mode='expert'`` to read the measured
parameters in that case (PAB then applies its own QC and de-spiking downstream).

argopy is imported lazily inside each function so ``import pab.argo.fetch``
works in a minimal environment; network access happens only at ``.load()``.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

import numpy as np

#: Default BGC variables PAB requests for the matchup/summary.
DEFAULT_PARAMS = ("CHLA", "BBP700", "PSAL", "TEMP", "PRES")

#: Default QC flags retained (1 = good, 2 = probably good).
DEFAULT_QC = (1, 2)


def build_fetcher(
    *,
    params: Sequence[str] = DEFAULT_PARAMS,
    measured: Sequence[str] | None = ("BBP700",),
    mode: str = "standard",
    src: str = "gdac",
):
    """Construct a BGC ``argopy.DataFetcher``.

    Args:
        params: BGC variables to return.
        measured: Variables required non-NaN (e.g. keep only profiles with a
            valid ``BBP700``); ``None`` to disable.
        mode: argopy user mode — ``'standard'`` (routine) or ``'research'``
            (delayed-mode, QC=1; best for MLD), or ``'expert'`` (measured
            parameters as-is; needed for recent real-time profiles that have no
            adjusted fields yet — see the module note).
        src: Data source. Default ``'gdac'`` (reads the GDAC netCDF directly,
            more reliable than the Ifremer BGC ERDDAP); ``'erddap'`` is also
            supported for BGC.

    Returns:
        A configured (unfetched) ``argopy.DataFetcher``.
    """
    import argopy

    kwargs: dict[str, Any] = {"params": list(params)}
    if measured is not None:
        kwargs["measured"] = list(measured)
    with argopy.set_options(ds="bgc", src=src, mode=mode):
        return argopy.DataFetcher(**kwargs)


def fetch_region(box: Sequence[float], **kwargs):
    """Fetch BGC profiles within a region box and return the ``xarray.Dataset``.

    Args:
        box: ``[lon_min, lon_max, lat_min, lat_max, pres_min, pres_max,
            date_min, date_max]`` (the upper time bound is exclusive).
        **kwargs: Passed to :func:`build_fetcher`.

    Returns:
        The loaded ``xarray.Dataset`` (1-D ``N_POINTS`` collection).
    """
    fetcher = build_fetcher(**kwargs)
    return fetcher.region(list(box)).load().data


def fetch_float(wmo: int, **kwargs):
    """Fetch all BGC profiles for one float WMO."""
    fetcher = build_fetcher(**kwargs)
    return fetcher.float(wmo).load().data


def fetch_profile(wmo: int, cycle: int, **kwargs):
    """Fetch a single BGC profile (WMO + cycle number)."""
    fetcher = build_fetcher(**kwargs)
    return fetcher.profile(wmo, cycle).load().data


def filter_quality(ds, *, qc_list: Sequence[int] = DEFAULT_QC, research: bool = False):
    """Apply QC and data-mode filtering via the argopy accessor.

    Args:
        ds: An argopy ``xarray.Dataset``.
        qc_list: QC flags to retain (default ``(1, 2)``).
        research: If True, additionally apply ``filter_researchmode`` (keeps
            delayed-mode, QC=1 data — appropriate when high quality matters).

    Returns:
        The filtered dataset.
    """
    out = ds.argo.filter_qc(QC_list=list(qc_list))
    if research:
        out = out.argo.filter_researchmode()
    return out


def iter_profiles(ds) -> Iterator[tuple[dict[str, Any], dict[str, np.ndarray]]]:
    """Reshape an argopy dataset to profiles and yield per-profile arrays.

    Bridges the fetched ``N_POINTS`` dataset to the array-based summary
    functions: reshapes with ``ds.argo.point2profile()`` and, for each profile,
    yields its metadata (``wmo``, ``cycle``, ``latitude``, ``longitude``,
    ``time``, ``data_mode``) and a dict of its 1-D variable arrays.

    Args:
        ds: An argopy ``xarray.Dataset`` (point collection).

    Yields:
        ``(metadata, variables)`` per profile, ready for
        :func:`pab.argo.summary.summarize_profile`.
    """
    prof = ds.argo.point2profile()
    var_names = [v for v in ("PRES", "BBP700", "CHLA", "PSAL", "TEMP") if v in prof]
    n_prof = prof.sizes.get("N_PROF", 0)
    for i in range(n_prof):
        one = prof.isel(N_PROF=i)
        meta = {
            "wmo": int(one["PLATFORM_NUMBER"].values),
            "cycle": int(one["CYCLE_NUMBER"].values),
            "latitude": float(one["LATITUDE"].values),
            "longitude": float(one["LONGITUDE"].values),
            "time": str(np.datetime_as_string(one["TIME"].values))
            if "TIME" in one
            else None,
        }
        if "DATA_MODE" in one:
            meta["data_mode"] = str(one["DATA_MODE"].values)
        variables = {v: np.asarray(one[v].values, dtype=float) for v in var_names}
        yield meta, variables

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
DEFAULT_PARAMS = ("CHLA", "BBP700", "CDOM", "PSAL", "TEMP", "PRES")

#: BGC parameters whose per-parameter Argo data mode (``<PARAM>_DATA_MODE``,
#: R/A/D) :func:`iter_profiles` records — distinct from ``profiles.data_mode``,
#: which BGC fetches leave unpopulated (see :func:`iter_profiles`).
_PER_PARAM_MODE_VARS = ("CHLA", "CDOM", "BBP700")

#: Default QC flags retained (1 = good, 2 = probably good).
DEFAULT_QC = (1, 2)

#: Argo QC flag PAB drops from the mixed-layer mean when QC-aware CDOM
#: filtering is requested (per chl_cdom_matchups.md R2) — "bad" data.
#: Distinct from DEFAULT_QC/filter_quality, which nothing in the ingestion
#: pipeline actually calls (see pab.argo.summary's module docstring).
BAD_CDOM_QC = (4,)

#: Official Argo DAC 2-letter code -> GDAC directory name, for the floats
#: actually present in this project's matchup set (chl_cdom_matchups.md R6).
#: Not necessarily exhaustive of every Argo DAC.
DAC_FOLDERS: dict[str, str] = {
    "AO": "aoml",
    "BO": "bodc",
    "CS": "csiro",
    "HZ": "csio",
    "IF": "coriolis",
    "IN": "incois",
    "JA": "jma",
    "KM": "kma",
    "KO": "kordi",
    "ME": "meds",
}

#: GDAC meta-file URL template (float-level; a different Argo file type than
#: the per-profile files ``iter_profiles`` reads). ``{dac}`` is a
#: :data:`DAC_FOLDERS` value, not the 2-letter code.
GDAC_META_URL = "https://data-argo.ifremer.fr/dac/{dac}/{wmo}/{wmo}_meta.nc"

#: The ``SENSOR`` row identifying the CDOM fluorometer in a meta.nc file.
CDOM_SENSOR_ROW = "FLUOROMETER_CDOM"


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
    ``time``, ``data_mode``, ``project_name``, ``data_center``,
    ``chla_data_mode``, ``cdom_data_mode``, ``bbp700_data_mode``) and a dict of
    its 1-D variable arrays (including ``CDOM``, ``CDOM_QC`` — the per-level
    QC flag, for R2's QC-filtered mixed-layer mean — and ``CHLA_ADJUSTED`` when
    present, alongside ``PRES``/``BBP700``/``CHLA``/``PSAL``/``TEMP``).

    ``data_mode`` is extracted defensively but is a no-op on a real BGC/GDAC
    fetch as of argopy 1.4.0 — a bare ``DATA_MODE`` variable was not observed
    there (confirmed: ``'DATA_MODE' in ds.variables`` is ``False``). BGC files
    instead carry a **per-parameter** ``<PARAM>_DATA_MODE`` for each BGC
    variable (e.g. ``CHLA`` and ``PSAL`` on the same profile can be in
    different modes) — ``chla_data_mode``/``cdom_data_mode``/
    ``bbp700_data_mode`` capture that. ``project_name``/``data_center`` (from
    Argo's ``PROJECT_NAME``/``DATA_CENTRE``) are per-float and were confirmed
    present on real BGC/GDAC profiles.

    Args:
        ds: An argopy ``xarray.Dataset`` (point collection).

    Yields:
        ``(metadata, variables)`` per profile, ready for
        :func:`pab.argo.summary.summarize_profile`.
    """
    prof = ds.argo.point2profile()
    var_names = [
        v
        for v in (
            "PRES",
            "BBP700",
            "CHLA",
            "CHLA_ADJUSTED",
            "CDOM",
            "CDOM_QC",
            "PSAL",
            "TEMP",
        )
        if v in prof
    ]
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
        if "PROJECT_NAME" in one:
            meta["project_name"] = str(one["PROJECT_NAME"].values).strip()
        if "DATA_CENTRE" in one:
            meta["data_center"] = str(one["DATA_CENTRE"].values).strip()
        for p in _PER_PARAM_MODE_VARS:
            mode_var = f"{p}_DATA_MODE"
            if mode_var in one:
                meta[f"{p.lower()}_data_mode"] = str(one[mode_var].values).strip()
        variables = {v: np.asarray(one[v].values, dtype=float) for v in var_names}
        yield meta, variables


def _default_meta_downloader(url: str) -> bytes:
    """Real HTTP downloader for :func:`fetch_cdom_sensor_model` (network seam)."""
    import urllib.request

    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 - fixed https GDAC host
        return resp.read()


def fetch_cdom_sensor_model(
    wmo: int, data_center: str | None, *, downloader=None
) -> str | None:
    """Fetch a float's CDOM fluorometer ``SENSOR_MODEL`` from its GDAC meta.nc.

    Per chl_cdom_matchups.md R6: sensor identity ("MCOM*" vs. ``ECO_FLBBCD``)
    is not present in anything :func:`iter_profiles` reads — it lives only in
    the float's separate, per-**float** (not per-profile) ``<wmo>_meta.nc``
    file, fetched here via a plain HTTPS download (not through argopy's
    ``DataFetcher``, which has no meta-file support).

    Args:
        wmo: Float WMO id.
        data_center: The float's 2-letter DAC code (``floats.data_center``,
            e.g. ``'AO'``); looked up in :data:`DAC_FOLDERS` for the GDAC URL
            path. ``None`` or an unknown code returns ``None`` rather than
            guessing a folder.
        downloader: ``url -> bytes`` override (the test seam — mocks the
            network); defaults to a real HTTPS GET.

    Returns:
        The stripped ``SENSOR_MODEL`` string for the ``FLUOROMETER_CDOM``
        sensor row (e.g. ``'MCOMS_FLBBCD'``, ``'ECO_FLBBCD'``, or the literal
        string ``'UNKNOWN'`` some floats report), or ``None`` if the float has
        no DAC mapping, no CDOM sensor row, or the fetch/parse fails for any
        reason — a missing sensor model must never abort a re-ingestion pass.
    """
    dac = DAC_FOLDERS.get((data_center or "").strip().upper())
    if dac is None:
        return None
    url = GDAC_META_URL.format(dac=dac, wmo=wmo)
    get = downloader or _default_meta_downloader
    try:
        raw = get(url)
    except Exception:  # noqa: BLE001 - a fetch failure must not abort re-ingestion
        return None

    import tempfile
    from pathlib import Path

    import xarray as xr

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"{wmo}_meta.nc"
        path.write_bytes(raw)
        try:
            with xr.open_dataset(path) as ds:
                if "SENSOR" not in ds or "SENSOR_MODEL" not in ds:
                    return None
                sensors = _decode_char_array(ds["SENSOR"].values)
                models = _decode_char_array(ds["SENSOR_MODEL"].values)
        except Exception:  # noqa: BLE001 - a malformed meta file must not abort
            return None

    for sensor, model in zip(sensors, models, strict=True):
        if sensor == CDOM_SENSOR_ROW:
            return model or None
    return None


def _decode_char_array(values) -> list[str]:
    """Decode a netCDF fixed-width byte/char array to a list of stripped strings.

    A real GDAC meta.nc yields plain ``bytes`` rows via xarray (no
    ``.tobytes()`` — decode directly; ``str(x)`` would silently stringify a
    ``bytes`` object to its ``b'...'`` repr). A synthetic/round-tripped
    dataset (e.g. in tests) can instead yield ``numpy.str_``, which — despite
    already being a real ``str`` — *also* defines ``.tobytes()``, returning
    the raw in-memory encoding (UTF-32 on most builds), not UTF-8 text; that
    check must come after the plain-``str`` check, not before, or "real
    string" rows get mangled through a UTF-8 decode of the wrong bytes.
    """
    out = []
    for x in values:
        if isinstance(x, bytes):
            s = x.decode("utf-8", errors="ignore")
        elif isinstance(x, str):
            s = str(x)
        elif hasattr(x, "tobytes"):
            s = x.tobytes().decode("utf-8", errors="ignore")
        else:
            s = str(x)
        out.append(s.strip())
    return out

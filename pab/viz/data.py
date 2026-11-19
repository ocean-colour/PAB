"""Read-only data layer for the PAB viz tools.

The **only** module in :mod:`pab.viz` that touches the database or the chain
files. Every store is opened read-only (a ``mode=ro`` URI, never migrated),
and nothing here writes anywhere (``claude_prompts/viz_tools.md``, Working
agreements / I-Q6).

Version handling is generic (I-Q1): a *family* is a base version plus its
patches (``"2.0"`` with ``"2.0.1"``), resolved through
:mod:`pab.metrics.compare`, so a future ``3.0`` appears without code changes.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import pab.config
from pab.db.store import Store
from pab.fit import artifacts
from pab.metrics import compare

#: Default BING model pair (the only one in production).
DEFAULT_MODEL_PAIR = "ExpBPow"


# -- opening ---------------------------------------------------------------
def open_store(path: str | Path) -> Store:
    """Open ``path`` **read-only** as a :class:`Store` (no create, no migrate).

    The connection allows use from the thread that did not create it
    (``check_same_thread=False``) because a Bokeh session may be torn down
    from another thread; callers still give each worker thread its own store.
    """
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"no database at {path}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return Store(conn)


def set_data_dir(path: str | Path) -> Path:
    """Point chain lookups at ``path`` (the folder holding ``fit_chains/``).

    :func:`pab.fit.artifacts.chains_path` resolves through the ``DATA_DIR``
    bound when :mod:`pab.config` was imported, which ``python -m pab.viz`` does
    before any viz code runs, so the binding is updated here explicitly. Only
    the read path changes; nothing in :mod:`pab.viz` writes chains.
    """
    path = Path(path).expanduser().resolve()
    pab.config.DATA_DIR = path
    artifacts.DATA_DIR = path
    return path


def chains_file(fit_id: str) -> Path:
    """Where the chain NPZ of ``fit_id`` is looked for (it may not exist)."""
    return artifacts.chains_path(fit_id)


def has_chains(fit_id: str) -> bool:
    """Whether the chain NPZ of ``fit_id`` is present under the data dir."""
    return chains_file(fit_id).is_file()


# -- versions --------------------------------------------------------------
def version_families(store) -> list[str]:
    """The BING base versions in ``store``, **newest first** (``["2.1", "2.0"]``)."""
    bases = {compare.base_version(v) for v in compare._bing_versions(store)}
    return sorted(bases, key=compare._version_key, reverse=True)


def family_members(store, base: str) -> list[str]:
    """``base`` and every patch of it in ``store``, oldest first."""
    return [
        v for v in compare._bing_versions(store) if compare.base_version(v) == base
    ]


def family_label(store, base: str) -> str:
    """Selector text for a family: ``"2.1"`` or ``"2.0 (+2.0.1)"``."""
    patches = [v for v in family_members(store, base) if v != base]
    return f"{base} (+{', '.join(patches)})" if patches else base


# -- selection -------------------------------------------------------------
def wmos_with_matchups(store) -> list[int]:
    """Every float WMO that has at least one matchup, ascending."""
    rows = store.query(
        "SELECT DISTINCT p.wmo FROM matchups m "
        "JOIN profiles p ON p.profile_id = m.profile_id ORDER BY p.wmo"
    )
    return [int(r["wmo"]) for r in rows]


def cycles_for_wmo(store, wmo: int) -> list[int]:
    """The matchup cycles of float ``wmo``, ascending."""
    rows = store.query(
        "SELECT DISTINCT p.cycle FROM matchups m "
        "JOIN profiles p ON p.profile_id = m.profile_id "
        "WHERE p.wmo = ? ORDER BY p.cycle",
        (int(wmo),),
    )
    return [int(r["cycle"]) for r in rows]


def matchup_for(store, wmo: int, cycle: int) -> dict[str, Any] | None:
    """The matchup of profile ``(wmo, cycle)`` with its profile and ML summary.

    Returns ``None`` when the profile has no matchup. Keys include
    ``matchup_id``, ``profile_id``, ``latitude``, ``longitude``, ``time``,
    ``distance_km``, ``dtime_hours`` and the ``mld_summary`` columns
    (``mld``, ``bbp700``, ``bbp700_std``, ``n_points``, ``chla``,
    ``chla_adjusted``, ``cdom``, …).
    """
    rows = store.query(
        """
        SELECT m.matchup_id, m.distance_km, m.dtime_hours, m.granule_id,
               p.profile_id, p.wmo, p.cycle, p.latitude, p.longitude, p.time,
               s.mld, s.mld_method, s.bbp700, s.bbp700_std, s.n_points,
               s.chla, s.chla_std, s.chla_adjusted, s.cdom, s.cdom_std
        FROM matchups m
        JOIN profiles p ON p.profile_id = m.profile_id
        LEFT JOIN mld_summary s ON s.profile_id = p.profile_id
        WHERE p.wmo = ? AND p.cycle = ?
        ORDER BY m.matchup_id
        """,
        (int(wmo), int(cycle)),
    )
    return rows[0] if rows else None


def _results(store, fit_id: str) -> dict[str, tuple[float, float, float]]:
    """``{quantity: (value, lo, hi)}`` for one fit (NULL → NaN)."""
    out = {}
    for r in store.query(
        "SELECT quantity, value, value_lo, value_hi FROM fit_results WHERE fit_id = ?",
        (fit_id,),
    ):
        out[r["quantity"]] = tuple(
            float("nan") if r[k] is None else float(r[k])
            for k in ("value", "value_lo", "value_hi")
        )
    return out


def bing_fit(
    store, matchup_id: str, family: str, *, model_pair: str = DEFAULT_MODEL_PAIR
) -> dict[str, Any] | None:
    """The BING fit of ``matchup_id`` shown for version ``family``.

    The family's rows are overlaid (:func:`compare.overlay_patch`), so a patched
    pixel shows its patch row, and the best-ranked pixel is taken (production
    fits only the rank-1 pixel). Returns the ``fits`` row plus ``results``
    (``{short_name: (value, lo, hi)}``, e.g. ``"bbp700"``), ``rank`` and
    ``patched`` (the row is a patch of ``family``), or ``None``.
    """
    versions = family_members(store, family)
    if not versions:
        return None
    marks = ", ".join("?" for _ in versions)
    df = store.query_df(
        f"""
        SELECT f.*, p.rank
        FROM fits f LEFT JOIN matchup_pixels p ON p.pixel_id = f.pixel_id
        WHERE f.matchup_id = ? AND f.algorithm = 'BING' AND f.model_pair = ?
          AND f.pab_version IN ({marks})
        """,
        (matchup_id, model_pair, *versions),
    )
    if not len(df):
        return None
    df = compare.overlay_patch(df)
    df = df.sort_values("rank", na_position="last", kind="stable")
    row = {k: (None if pd.isna(v) else v) for k, v in df.iloc[0].to_dict().items()}
    prefix = f"BING_{model_pair}_"
    row["results"] = {
        q[len(prefix):]: v
        for q, v in _results(store, row["fit_id"]).items()
        if q.startswith(prefix)
    }
    row["patched"] = row["pab_version"] != family
    return row


def giop_fit(store, matchup_id: str, pixel_id=None) -> dict[str, Any] | None:
    """NASA-GIOP ``b_bp(700)`` for the matchup (same pixel when given).

    ``bbp700`` is ``bbp_442`` moved to 700 nm with GIOP's own per-pixel slope
    (:func:`compare.giop_bbp_to_700`); ``bbp700_unc`` is ``bbp_unc_442``
    scaled by the same factor, which carries **no slope uncertainty**.
    """
    rows = store.query(
        """
        SELECT f.fit_id, f.pixel_id, f.pab_version, p.rank
        FROM fits f LEFT JOIN matchup_pixels p ON p.pixel_id = f.pixel_id
        WHERE f.matchup_id = ? AND f.algorithm = 'NASA_GIOP'
        """,
        (matchup_id,),
    )
    if not rows:
        return None
    same = [r for r in rows if pixel_id is not None and r["pixel_id"] == pixel_id]
    row = same[0] if same else sorted(rows, key=lambda r: (r["rank"] is None, r["rank"]))[0]
    res = {q: v[0] for q, v in _results(store, row["fit_id"]).items()}
    bbp442 = res.get("NASA_GIOP_bbp_442", np.nan)
    slope = res.get("NASA_GIOP_bbp_s", np.nan)
    unc442 = res.get("NASA_GIOP_bbp_unc_442", np.nan)
    bbp700 = float(compare.giop_bbp_to_700(bbp442, slope))
    factor = bbp700 / bbp442 if np.isfinite(bbp442) and bbp442 != 0 else np.nan
    return {
        "fit_id": row["fit_id"],
        "pixel_id": row["pixel_id"],
        "pab_version": row["pab_version"],
        "bbp_442": bbp442,
        "bbp_s": slope,
        "bbp700": bbp700,
        "bbp700_unc": float(unc442 * factor) if np.isfinite(unc442) else np.nan,
    }


# -- all matchups (Global explorer) ------------------------------------------
#: ``fit_results`` quantities added to the explorer frame, by column name.
EXPLORER_QUANTITIES = {"adg": "Adg", "sdg": "Sdg", "beta": "beta"}


def explorer_frame(store, family: str | None = None, *,
                   model_pair: str = DEFAULT_MODEL_PAIR) -> pd.DataFrame:
    """One row per matchup of BING family ``family`` (patches overlaid).

    :func:`compare.gather_matchups` (position, time, Argo and BING ``b_bp`` /
    Chl, ``chisq``, ``bbp_bing_implausible``, …), **ungated**, plus the fit's
    LM ``success``, the matchup's ``distance_km`` / ``dtime_hours`` and the
    stored medians of ``Adg`` (at 400 nm), ``Sdg`` and ``beta``.
    """
    if family is None:
        fams = version_families(store)
        family = fams[0] if fams else None
    if family is None:
        return pd.DataFrame()
    versions = family_members(store, family)
    df = compare.gather_matchups(store, model_pair=model_pair, pab_version=versions)
    if df.empty:
        return df
    clause, params = compare._version_clause("f.pab_version", versions)
    pivots = ", ".join(
        f"MAX(CASE WHEN r.quantity = '{_q(model_pair, q)}' THEN r.value END) AS {col}"
        for col, q in EXPLORER_QUANTITIES.items()
    )
    rows = store.query(
        f"""
        SELECT f.fit_id, f.success, m.distance_km, m.dtime_hours, {pivots}
        FROM fits f
        JOIN matchups m ON m.matchup_id = f.matchup_id
        LEFT JOIN fit_results r ON r.fit_id = f.fit_id
        WHERE f.algorithm = 'BING' AND f.model_pair = ? {clause}
        GROUP BY f.fit_id
        """,
        (model_pair, *params),
    )
    extra = pd.DataFrame([dict(r) for r in rows])
    if extra.empty:
        return df
    return df.merge(extra, on="fit_id", how="left")


def _q(model_pair: str, short: str) -> str:
    """The ``fit_results.quantity`` name of a BING parameter."""
    return f"BING_{model_pair}_{short}"

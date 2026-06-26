"""End-to-end pipeline & CLI (Stage 8).

A single, resumable, config-driven stage runner tying Stages 2–7 together —
**ingest → discover → match → fit → figure → report** — with **no new science**:
each stage is a thin wrapper over the module already built for it, reads/writes
the shared :class:`pab.db.store.Store`, and **skips work already done** (the
existing `persist_*`/`build_*` idempotency), so a re-run resumes. Re-running
under a new ``pab_version`` adds records rather than overwriting.

The network/heavy seams stay **injectable** — ``fetcher`` (argopy), ``searcher``
(earthaccess discovery), and ``opener`` (:func:`pab.pace.cloud.open_granule`) —
so the pipeline runs offline on synthetic inputs in tests while the orchestration
(stage order, skip/resume, the run summary) is plain, testable code.
"""

from __future__ import annotations

import argparse
import inspect
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pab.config import DATA_DIR
from pab.config import pab_version as _pab_version
from pab.fit.models import FitConfig
from pab.matchup.engine import MatchupConfig

#: The pipeline stages, in run order.
STAGES: tuple[str, ...] = ("ingest", "discover", "match", "fit", "figure", "report")


@dataclass
class PipelineConfig:
    """Configuration for an end-to-end pipeline run.

    Attributes:
        profiles: Inline profile dicts (offline) — each ``{wmo, cycle, latitude,
            longitude, time}`` and optionally a precomputed ``summary`` (then
            ``ingest`` persists it directly instead of fetching).
        profiles_csv: Path to a dev-set CSV (default ``data/dev_profiles.csv``)
            used when ``profiles`` is ``None``.
        argo_src, argo_mode: argopy source/mode for the live fetch.
        short_name: PACE collection short name for discovery.
        bbox_pad_deg, dtime_days, cloud_cover: granule-discovery window.
        matchup, fit: the Stage-4 / Stage-5 configs.
        outdir: base output directory (defaults to ``DATA_DIR/pipeline``).
        make_figures: render per-matchup figures in the ``figure`` stage.
        replace: re-do already-completed work (else stages skip it).
    """

    profiles: list[dict[str, Any]] | None = None
    profiles_csv: str | Path | None = None
    argo_src: str = "gdac"
    argo_mode: str = "expert"
    short_name: str = "PACE_OCI_L2_AOP"
    bbox_pad_deg: float = 0.4
    dtime_days: float = 1.0
    cloud_cover: tuple[int, int] = (0, 100)
    matchup: MatchupConfig = field(default_factory=MatchupConfig)
    fit: FitConfig = field(default_factory=FitConfig)
    outdir: str | Path | None = None
    make_figures: bool = True
    replace: bool = False

    def out(self) -> Path:
        """The resolved base output directory."""
        return Path(self.outdir) if self.outdir else Path(DATA_DIR) / "pipeline"

    def profile_rows(self) -> list[dict[str, Any]]:
        """The profile selection — inline ``profiles`` or the dev-set CSV rows."""
        if self.profiles is not None:
            return list(self.profiles)
        import pandas as pd

        csv = Path(self.profiles_csv) if self.profiles_csv else _default_dev_csv()
        return pd.read_csv(csv).to_dict(orient="records")


def _default_dev_csv() -> Path:
    from pab.config import ROOT

    return Path(ROOT) / "data" / "dev_profiles.csv"


# -- stages -----------------------------------------------------------------
def ingest(store, config: PipelineConfig, *, fetcher=None) -> dict[str, Any]:
    """Persist BGC-Argo profiles + mixed-layer summaries (idempotent).

    For each selected profile: if it already has an ``mld_summary`` (and not
    ``replace``), skip. Otherwise persist a precomputed ``summary`` (offline) or
    fetch + summarize via argopy (``fetcher`` overrides the live fetch — it takes
    ``(wmo, cycle, argo_src, argo_mode)`` and returns an argopy dataset).
    """
    from pab.argo import fetch, summary

    written, skipped = [], []
    for row in config.profile_rows():
        wmo, cycle = int(row["wmo"]), int(row["cycle"])
        have = store.query(
            "SELECT 1 FROM mld_summary ms JOIN profiles p "
            "ON p.profile_id = ms.profile_id WHERE p.wmo = ? AND p.cycle = ?",
            (wmo, cycle),
        )
        if have and not config.replace:
            skipped.append(f"{wmo}_{cycle}")
            continue
        if "summary" in row:  # offline: a precomputed summary
            summary.persist_summary(
                store,
                wmo=wmo,
                cycle=cycle,
                summary=row["summary"],
                latitude=row.get("latitude"),
                longitude=row.get("longitude"),
                time=row.get("time"),
            )
        else:
            ds = (
                fetcher(wmo, cycle, config.argo_src, config.argo_mode)
                if fetcher is not None
                else fetch.fetch_profile(
                    wmo, cycle, src=config.argo_src, mode=config.argo_mode
                )
            )
            meta, v = next(fetch.iter_profiles(ds))
            summ = summary.summarize_profile(
                v["PRES"],
                bbp700=v.get("BBP700"),
                chla=v.get("CHLA"),
                psal=v.get("PSAL"),
                temp=v.get("TEMP"),
                lon=meta["longitude"],
                lat=meta["latitude"],
            )
            summary.persist_summary(
                store,
                wmo=wmo,
                cycle=cycle,
                summary=summ,
                latitude=meta["latitude"],
                longitude=meta["longitude"],
                time=meta["time"],
            )
        written.append(f"{wmo}_{cycle}")
    return {"written": written, "skipped": skipped}


def discover(store, config: PipelineConfig, *, searcher=None) -> dict[str, Any]:
    """Discover + persist PACE granules around each profile (idempotent upsert).

    ``searcher(lat, lon, t0, t1, config)`` overrides the live earthaccess search
    (it returns a granule ``DataFrame``); otherwise ``pab.pace.discover`` is used.
    A profile that already has granules in its time window is **skipped** (no
    re-query) unless ``replace`` — so a resume doesn't re-hit the network.
    """
    from pab.matchup.engine import candidate_granules
    from pab.pace import discover as disc

    profiles = store.query(
        "SELECT wmo, cycle, latitude, longitude, time FROM profiles "
        "WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    )
    n, skipped = 0, []
    dtime_hours = config.dtime_days * 24.0
    for p in profiles:
        if not config.replace and candidate_granules(
            store, p["time"], dtime_max_hours=dtime_hours
        ):
            skipped.append(f"{p['wmo']}_{p['cycle']}")
            continue
        t = datetime.fromisoformat(str(p["time"]))
        win = (
            t - timedelta(days=config.dtime_days),
            t + timedelta(days=config.dtime_days),
        )
        lon, lat, pad = p["longitude"], p["latitude"], config.bbox_pad_deg
        if searcher is not None:
            table = searcher(lat, lon, win[0], win[1], config)
        else:
            res = disc.search_granules(
                short_name=config.short_name,
                temporal=(win[0].isoformat(), win[1].isoformat()),
                bounding_box=(lon - pad, lat - pad, lon + pad, lat + pad),
                cloud_cover=config.cloud_cover,
            )
            table = disc.granule_table(res)
        if table is not None and len(table):
            n += disc.persist_granules(store, table, short_name=config.short_name)
    return {"granules_upserted": n, "skipped": skipped}


def match(store, config: PipelineConfig, *, opener=None) -> dict[str, Any]:
    """Stage 4: build matchups (idempotent/resumable)."""
    from pab.matchup.engine import build_matchups

    return build_matchups(
        store, opener=opener, config=config.matchup, replace=config.replace
    )


def fit(store, config: PipelineConfig, *, opener=None) -> dict[str, Any]:
    """Stage 5: fit each matchup with BING (idempotent by ``fit_id``)."""
    from pab.fit.run import build_fits

    return build_fits(store, opener=opener, config=config.fit, replace=config.replace)


def figure(store, config: PipelineConfig, *, opener=None) -> dict[str, Any]:
    """Stage 6: render per-matchup fit + scene figures; record ``figure_path``.

    Best-effort per fit (a failed render is recorded, not fatal). Skips fits that
    already have a ``figure_path`` unless ``replace``.
    """
    if not config.make_figures:
        return {"written": [], "skipped": [], "failed": []}
    from pab.plotting import fit_fig, scene

    figdir = config.out() / "figures"
    figdir.mkdir(parents=True, exist_ok=True)
    written, skipped, failed = [], [], []
    rows = store.query(
        "SELECT fit_id, matchup_id, figure_path FROM fits ORDER BY fit_id"
    )
    for r in rows:
        if r["figure_path"] and not config.replace:
            skipped.append(r["fit_id"])
            continue
        try:
            fpath = figdir / f"{r['fit_id']}_fit.png"
            fit_fig.fit_figure(store, r["fit_id"], outfile=fpath)
            try:  # the scene is a bonus artifact; don't fail the fit figure on it
                scene.scene_from_store(
                    store,
                    r["matchup_id"],
                    opener=opener,
                    outfile=figdir / f"{r['matchup_id']}_scene.png",
                )
            except Exception:  # noqa: BLE001
                pass
            store.execute(
                "UPDATE fits SET figure_path = ? WHERE fit_id = ?",
                (str(fpath), r["fit_id"]),
            )
            written.append(r["fit_id"])
        except Exception:  # noqa: BLE001 — one bad render must not abort the batch
            failed.append(r["fit_id"])
    return {"written": written, "skipped": skipped, "failed": failed}


def report(store, config: PipelineConfig) -> dict[str, Any]:
    """Stage 7: build the aggregate site and the (stub-published) release."""
    from pab.report import publish, rst

    site = rst.build_site(store, config.out() / "site")
    release = publish.publish_release(store, config.out() / "release")
    return {
        "site": {k: str(v) for k, v in site.items()},
        "n_uploaded": release["n_uploaded"],
        "manifest": str(release["manifest_path"]),
    }


_STAGE_FUNCS = {
    "ingest": ingest,
    "discover": discover,
    "match": match,
    "fit": fit,
    "figure": figure,
    "report": report,
}


def run(
    store,
    config: PipelineConfig | None = None,
    *,
    stages=STAGES,
    opener=None,
    fetcher=None,
    searcher=None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the selected pipeline stages in order; return a per-stage summary.

    Args:
        store: An open :class:`pab.db.store.Store` (the shared state).
        config: The :class:`PipelineConfig` (defaults to the dev-set defaults).
        stages: Which stages to run (subset of :data:`STAGES`, run in
            :data:`STAGES` order).
        opener, fetcher, searcher: Injectable seams for the granule open, argopy
            fetch, and earthaccess discovery (mocked offline; live by default).
        dry_run: If True, return the planned stage order and do nothing.

    Returns:
        ``{"dry_run": True, "stages": [...]}`` on a dry run, else
        ``{stage: <summary>}`` for each executed stage.
    """
    config = config or PipelineConfig()
    plan = [s for s in STAGES if s in set(stages)]
    if dry_run:
        return {"dry_run": True, "stages": plan, "pab_version": _pab_version}

    seam = {"opener": opener, "fetcher": fetcher, "searcher": searcher}
    summary: dict[str, Any] = {}
    for stage in plan:
        func = _STAGE_FUNCS[stage]
        # forward only the seam(s) the stage actually declares as parameters
        # (signature, not co_varnames, so a same-named local can't misroute)
        params = inspect.signature(func).parameters
        kwargs = {k: v for k, v in seam.items() if k in params}
        summary[stage] = func(store, config, **kwargs)
    return summary


# -- CLI --------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """The ``pab`` CLI parser."""
    p = argparse.ArgumentParser(
        prog="pab", description="Run the PAB end-to-end matchup pipeline."
    )
    p.add_argument(
        "--db",
        default=str(Path(DATA_DIR) / "pab.db"),
        help="SQLite store path (created if absent).",
    )
    p.add_argument(
        "--stage",
        action="append",
        choices=STAGES,
        dest="stages",
        help="Run only this stage (repeatable). Default: all.",
    )
    p.add_argument(
        "--outdir", default=None, help="Output dir (default DATA_DIR/pipeline)."
    )
    p.add_argument("--profiles-csv", default=None, help="Profile-selection CSV.")
    p.add_argument("--replace", action="store_true", help="Re-do completed work.")
    p.add_argument("--no-figures", action="store_true", help="Skip the figure stage.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the stage plan and exit without touching anything.",
    )
    return p


def main(argv=None) -> int:
    """CLI entry point (``pab``). Returns a process exit code."""
    from pab.db import Store

    args = build_parser().parse_args(argv)
    config = PipelineConfig(
        profiles_csv=args.profiles_csv,
        outdir=args.outdir,
        replace=args.replace,
        make_figures=not args.no_figures,
    )
    stages = args.stages or list(STAGES)
    if args.dry_run:
        plan = run(None, config, stages=stages, dry_run=True)
        print("pab pipeline (dry run) — stages:", " → ".join(plan["stages"]))
        print("db:", args.db, "| outdir:", config.out())
        return 0
    created = datetime.now(UTC).isoformat()
    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)  # sqlite won't create the dir
    with Store.open(db) as store:
        summary = run(store, config, stages=stages)
    print(f"pab pipeline done ({created}); stages: {list(summary)}")
    for stage, res in summary.items():
        print(f"  {stage}: {res}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

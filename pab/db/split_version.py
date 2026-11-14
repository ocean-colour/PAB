"""Split a released PAB store into a per-version database.

The v2 line of work re-fits every matchup with a new BING configuration, but it
must not disturb the **frozen** v1.0 database that the published site links
(``$PAB_DATA_DIR/v1/pab.db``, sha256 ``09de0a6d…f978273``). So v2 starts from a
*copy* of v1 with the old BING records removed and everything else — floats,
profiles, mixed-layer summaries, granules, matchups, pixels, and the NASA-GIOP
baseline — carried over untouched.

Two things are deliberately **kept**:

* the **NASA-GIOP** ``fits``/``fit_results`` rows, which are the algorithm
  baseline the v2 comparison is measured against and are not being recomputed;
* ``matchups.scene_path``, so the v2 report site reuses the PACE scene
  quick-looks already rendered for v1 rather than regenerating 14,586 PNGs.

Note that ``fits.pab_version`` / ``matchups.pab_version`` on the copied rows
still read ``"1.0"``/``"1.1"``: those stamp when a *record* was created, not
which database file it now lives in.

Usage::

    python -m pab.db.split_version \\
        --src $PAB_DATA_DIR/v1/pab.db --dst $PAB_DATA_DIR/v2/pab.db

The source is opened **read-only** and its sha256 is checked before and after,
so a run can never damage the frozen release.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from pathlib import Path
from typing import Any

from pab.db import schema

_log = logging.getLogger(__name__)

#: Algorithm whose ``fits``/``fit_results`` rows are dropped from the copy.
DEFAULT_DROP_ALGORITHM = "BING"


def sha256(path: str | Path, *, chunk: int = 1 << 20) -> str:
    """Return the hex sha256 of a file, read in ``chunk``-sized blocks."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def _connect_ro(path: str | Path) -> sqlite3.Connection:
    """Open ``path`` read-only (URI mode), so a bug cannot write to it."""
    return sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True)


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return ``{table: row count}`` for every table in :data:`schema.TABLE_NAMES`."""
    return {
        t: int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
        for t in schema.TABLE_NAMES
    }


def _algorithm_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return ``{fits.algorithm: row count}``."""
    return {
        str(a): int(n)
        for a, n in conn.execute("SELECT algorithm, COUNT(*) FROM fits GROUP BY 1")
    }


def _quantity_prefix_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Return ``{leading token of fit_results.quantity: row count}``.

    ``BING_ExpBPow_bbp440`` counts under ``BING``, ``NASA_GIOP_bbp_442`` under
    ``NASA`` — enough to prove no rows of the dropped algorithm survive.
    """
    sql = (
        "SELECT substr(quantity, 1, instr(quantity, '_') - 1) AS p, COUNT(*) "
        "FROM fit_results GROUP BY 1"
    )
    return {str(p): int(n) for p, n in conn.execute(sql)}


def copy_database(src: str | Path, dst: str | Path, *, overwrite: bool = False) -> Path:
    """Copy the SQLite database at ``src`` to ``dst``.

    Uses the ``sqlite3`` online-backup API rather than a file copy for two
    reasons: it takes a transactionally consistent snapshot, and it creates
    ``dst`` with normal permissions. A plain ``shutil.copy2`` would propagate
    the frozen release's ``a-w`` mode onto the copy, and the very next
    statement — the ``DELETE`` — would fail.

    Args:
        src: Existing database (opened read-only).
        dst: Destination path; parent directories are created.
        overwrite: Replace ``dst`` if it already exists.

    Returns:
        The destination path.

    Raises:
        FileNotFoundError: if ``src`` does not exist.
        FileExistsError: if ``dst`` exists and ``overwrite`` is False.
    """
    src, dst = Path(src), Path(dst)
    if not src.exists():
        raise FileNotFoundError(f"Source database not found: {src}")
    if dst.exists() and not overwrite:
        raise FileExistsError(f"{dst} exists; pass overwrite=True to replace it.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    src_conn = _connect_ro(src)
    try:
        dst_conn = sqlite3.connect(str(dst))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
    return dst


def drop_algorithm(conn: sqlite3.Connection, algorithm: str) -> dict[str, int]:
    """Delete one algorithm's ``fits`` rows and their ``fit_results``.

    ``fit_results`` go first so the foreign key to ``fits`` is never dangling,
    even mid-transaction. Both deletes happen in a single transaction.

    Args:
        conn: Writable connection to the copy.
        algorithm: Value of ``fits.algorithm`` to remove (e.g. ``"BING"``).

    Returns:
        ``{"fits": n, "fit_results": n}`` — rows actually deleted.
    """
    conn.execute("PRAGMA foreign_keys = ON")
    with conn:
        n_results = conn.execute(
            "DELETE FROM fit_results WHERE fit_id IN "
            "(SELECT fit_id FROM fits WHERE algorithm = ?)",
            (algorithm,),
        ).rowcount
        n_fits = conn.execute(
            "DELETE FROM fits WHERE algorithm = ?", (algorithm,)
        ).rowcount
    return {"fits": int(n_fits), "fit_results": int(n_results)}


def verify(
    src: str | Path,
    dst: str | Path,
    *,
    dropped: str = DEFAULT_DROP_ALGORITHM,
    src_sha256: str | None = None,
) -> dict[str, Any]:
    """Check the copy is sound and differs from the source only as intended.

    Runs SQLite's own consistency checks on ``dst`` and compares it to ``src``
    table by table: everything except ``fits``/``fit_results`` must match
    exactly, those two must have lost precisely the ``dropped`` algorithm's
    rows, and ``matchups.scene_path`` must survive intact.

    Args:
        src: The (frozen) source database.
        dst: The freshly built copy.
        dropped: Algorithm that should no longer appear in ``dst``.
        src_sha256: If given, ``src`` must still hash to this afterwards.

    Returns:
        A report dict; ``report["ok"]`` is True only if ``report["problems"]``
        is empty.
    """
    src, dst = Path(src), Path(dst)
    problems: list[str] = []
    s, d = _connect_ro(src), _connect_ro(dst)
    try:
        integrity = [r[0] for r in d.execute("PRAGMA integrity_check")]
        if integrity != ["ok"]:
            problems.append(f"integrity_check: {integrity}")

        fk = d.execute("PRAGMA foreign_key_check").fetchall()
        if fk:
            problems.append(f"foreign_key_check: {len(fk)} violation(s): {fk[:5]}")

        src_counts, dst_counts = table_counts(s), table_counts(d)
        for t in schema.TABLE_NAMES:
            if t in ("fits", "fit_results"):
                continue
            if src_counts[t] != dst_counts[t]:
                problems.append(
                    f"{t}: {dst_counts[t]} rows in copy, {src_counts[t]} in source"
                )

        src_alg, dst_alg = _algorithm_counts(s), _algorithm_counts(d)
        if dropped in dst_alg:
            problems.append(f"fits still has {dst_alg[dropped]} {dropped!r} rows")
        for alg, n in src_alg.items():
            if alg == dropped:
                continue
            if dst_alg.get(alg) != n:
                problems.append(
                    f"fits[{alg}]: {dst_alg.get(alg)} rows in copy, {n} in source"
                )

        src_pre, dst_pre = _quantity_prefix_counts(s), _quantity_prefix_counts(d)
        drop_pre = dropped.split("_")[0]
        if drop_pre in dst_pre:
            problems.append(
                f"fit_results still has {dst_pre[drop_pre]} {drop_pre}_* rows"
            )
        for pre, n in src_pre.items():
            if pre == drop_pre:
                continue
            if dst_pre.get(pre) != n:
                problems.append(
                    f"fit_results[{pre}_*]: {dst_pre.get(pre)} in copy, {n} in source"
                )

        # No fit_results may outlive their fits row.
        orphans = int(
            d.execute(
                "SELECT COUNT(*) FROM fit_results r "
                "LEFT JOIN fits f USING (fit_id) WHERE f.fit_id IS NULL"
            ).fetchone()[0]
        )
        if orphans:
            problems.append(f"{orphans} orphan fit_results rows")

        # R7: the v2 site reuses v1's scene quick-looks.
        scene_sql = "SELECT COUNT(*) FROM matchups WHERE scene_path IS NOT NULL"
        src_scenes = int(s.execute(scene_sql).fetchone()[0])
        dst_scenes = int(d.execute(scene_sql).fetchone()[0])
        if src_scenes != dst_scenes:
            problems.append(
                f"matchups.scene_path: {dst_scenes} non-null in copy, "
                f"{src_scenes} in source"
            )

        src_ver = int(s.execute("PRAGMA user_version").fetchone()[0])
        dst_ver = int(d.execute("PRAGMA user_version").fetchone()[0])
        if src_ver != dst_ver:
            problems.append(f"user_version: {dst_ver} in copy, {src_ver} in source")

        report: dict[str, Any] = {
            "src": str(src),
            "dst": str(dst),
            "dropped": dropped,
            "integrity_check": integrity,
            "foreign_key_violations": len(fk),
            "src_counts": src_counts,
            "dst_counts": dst_counts,
            "src_algorithms": src_alg,
            "dst_algorithms": dst_alg,
            "src_quantity_prefixes": src_pre,
            "dst_quantity_prefixes": dst_pre,
            "scene_paths": dst_scenes,
            "schema_version": dst_ver,
            "dst_bytes": dst.stat().st_size,
        }
    finally:
        s.close()
        d.close()

    if src_sha256 is not None:
        now = sha256(src)
        report["src_sha256"] = now
        report["src_sha256_expected"] = src_sha256
        if now != src_sha256:
            problems.append(
                f"source sha256 changed: {now} != {src_sha256} — v1 IS NOT FROZEN"
            )

    report["problems"] = problems
    report["ok"] = not problems
    return report


def split_version(
    src: str | Path,
    dst: str | Path,
    *,
    dropped: str = DEFAULT_DROP_ALGORITHM,
    overwrite: bool = False,
    vacuum: bool = True,
) -> dict[str, Any]:
    """Build a per-version database from ``src`` with ``dropped``'s fits removed.

    Copy → delete → ``VACUUM`` → :func:`verify`. The source's sha256 is taken
    before the copy and re-checked at the end, so the run proves it left the
    frozen release alone.

    Args:
        src: Source database (never written to).
        dst: Destination path; parents are created.
        dropped: ``fits.algorithm`` to strip from the copy.
        overwrite: Replace ``dst`` if present.
        vacuum: ``VACUUM`` the copy to reclaim the deleted pages.

    Returns:
        The :func:`verify` report, plus ``"deleted"`` (rows removed) and
        ``"src_sha256"``.
    """
    src, dst = Path(src), Path(dst)
    before = sha256(src)
    _log.info("source %s sha256 %s (%d B)", src, before, src.stat().st_size)

    copy_database(src, dst, overwrite=overwrite)
    _log.info("copied to %s (%d B)", dst, dst.stat().st_size)

    conn = sqlite3.connect(str(dst))
    try:
        deleted = drop_algorithm(conn, dropped)
        _log.info(
            "deleted %d %s fits and %d fit_results",
            deleted["fits"],
            dropped,
            deleted["fit_results"],
        )
        if vacuum:
            conn.execute("VACUUM")
            _log.info("vacuumed; %s now %d B", dst, dst.stat().st_size)
    finally:
        conn.close()

    report = verify(src, dst, dropped=dropped, src_sha256=before)
    report["deleted"] = deleted
    return report


def _format_report(report: dict[str, Any]) -> str:
    """Render a :func:`verify` report as a human-readable block."""
    lines = [
        f"src  {report['src']}",
        f"dst  {report['dst']}  ({report['dst_bytes']:,} B, schema v"
        f"{report['schema_version']})",
        f"integrity_check      {report['integrity_check']}",
        f"foreign_key_check    {report['foreign_key_violations']} violation(s)",
        "",
        f"{'table':<16}{'v1':>12}{'v2':>12}",
    ]
    for t in schema.TABLE_NAMES:
        lines.append(
            f"{t:<16}{report['src_counts'][t]:>12,}{report['dst_counts'][t]:>12,}"
        )
    lines += [
        "",
        f"fits by algorithm     v1 {report['src_algorithms']}",
        f"                      v2 {report['dst_algorithms']}",
        f"fit_results prefixes  v1 {report['src_quantity_prefixes']}",
        f"                      v2 {report['dst_quantity_prefixes']}",
        f"matchups.scene_path   {report['scene_paths']:,} non-null (kept)",
    ]
    if "src_sha256" in report:
        same = report["src_sha256"] == report["src_sha256_expected"]
        lines.append(
            f"source sha256         {report['src_sha256']} "
            f"({'unchanged' if same else 'CHANGED!'})"
        )
    if report["problems"]:
        lines += ["", "PROBLEMS:"] + [f"  - {p}" for p in report["problems"]]
    else:
        lines += ["", "OK — no problems found."]
    return "\n".join(lines)


def main(argv=None) -> int:
    """CLI driver: ``python -m pab.db.split_version --src SRC --dst DST``.

    Both paths are required and neither is defaulted, per the one-canonical-DB
    working agreement. Exits non-zero if verification finds any problem.
    """
    import argparse

    p = argparse.ArgumentParser(
        prog="python -m pab.db.split_version",
        description=(
            "Copy a PAB store to a new per-version database with one "
            "algorithm's fits removed (v1 -> v2: drop BING, keep NASA-GIOP)."
        ),
    )
    p.add_argument("--src", required=True, help="Source database (read-only).")
    p.add_argument("--dst", required=True, help="Destination database to create.")
    p.add_argument(
        "--dropped",
        default=DEFAULT_DROP_ALGORITHM,
        help=f"fits.algorithm to strip (default: {DEFAULT_DROP_ALGORITHM}).",
    )
    p.add_argument(
        "--overwrite", action="store_true", help="Replace an existing --dst."
    )
    p.add_argument("--no-vacuum", action="store_true", help="Skip the VACUUM.")
    p.add_argument(
        "--fit-chains",
        action="store_true",
        help="Also create an empty fit_chains/ dir beside --dst.",
    )
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
    )

    report = split_version(
        args.src,
        args.dst,
        dropped=args.dropped,
        overwrite=args.overwrite,
        vacuum=not args.no_vacuum,
    )
    print(_format_report(report))

    if args.fit_chains:
        chains = Path(args.dst).parent / "fit_chains"
        chains.mkdir(parents=True, exist_ok=True)
        print(f"\nfit_chains dir: {chains}")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

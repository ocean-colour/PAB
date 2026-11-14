"""Backfill the negative-blue QA count for fits that predate it (O4, step 2).

Since O4 every BING fit records ``n_neg_blue`` — the number of windowed bands
with ``Rrs < 0`` at 400–450 nm (:func:`pab.fit.run.rrs_qa_quantities`) — as
an ordinary ``fit_results`` quantity (``BING_<model_pair>_n_neg_blue``). The
15,971 ``pab_version = '2.0'`` fits were made before that, and the database
holds no spectra (``matchup_pixels`` has pixel index, flags and geometry
only): the fitted spectrum lives in the chain NPZ (``wave``/``Rrs`` exactly as
:func:`pab.fit.run.prepare_spectrum` produced them), so the backfill reads
each fit's NPZ and upserts **one** row per fit. Nothing else is touched —
this is a QA backfill on existing records at the same version (the design's
documented precedent, the 1.0 Chl-a/CDOM re-ingest), not a re-analysis, so
``fits.pab_version`` stays ``2.0``.

The stored ``fits.chains_path`` values are PVC paths
(``/data/v2/fit_chains/<fit_id>.npz``); the NPZ is resolved by **basename**
under ``--chains-root`` (the workstation copy, HOWTO §5b).

Usage::

    # the plan, writing nothing (the database is opened read-only)
    python -m pab.fit.rrs_qa_backfill --db $PAB_DATA_DIR/v2/pab.db \\
        --chains-root $PAB_DATA_DIR/v2/fit_chains --dry-run

    # the real thing: a byte copy is made (or checked) first
    python -m pab.fit.rrs_qa_backfill --db $PAB_DATA_DIR/v2/pab.db \\
        --chains-root $PAB_DATA_DIR/v2/fit_chains \\
        --backup-copy $PAB_DATA_DIR/v2/pab_pre_negblue_$(date +%Y%m%d).db

Write discipline (the O-series preamble): a non-dry run **refuses** to start
without ``--backup-copy`` — a byte copy of the database made here (or an
existing file whose sha256 equals the database's) — and prints, before and
after, the file's sha256 and size, every table's row count, a checksum over
the pre-existing ``fits`` and ``fit_results`` rows and ``PRAGMA
integrity_check``. After the run it **verifies** that no table other than
``fit_results`` changed, that ``fit_results`` grew by exactly the rows
written, that the pre-existing rows hash the same (the design's provenance
rule: no existing 2.0 row changed) and that the integrity check still passes;
any failure exits non-zero and names the backup to restore from. A fit that
already carries the quantity is skipped (counted) unless ``--replace``; a
missing or unreadable NPZ is counted and skipped, with one summary warning.
``v1/`` is refused outright.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import sqlite3
from pathlib import Path
from typing import Any

import numpy as np

from pab.db.schema import TABLE_NAMES
from pab.db.store import Store
from pab.fit.run import NEG_BLUE_QUANTITY, rrs_qa_quantities

_log = logging.getLogger(__name__)

#: Fits are written to the store in batches of this many (each batch is one
#: transaction, so an interrupted run resumes by re-running: done fits skip).
BATCH = 1000


def quantity_name(model_pair: str = "ExpBPow") -> str:
    """The namespaced ``fit_results.quantity`` the count is stored under."""
    return f"BING_{model_pair}_{NEG_BLUE_QUANTITY}"


# -- the per-fit work --------------------------------------------------------
def resolve_chain(chains_path: str | None, chains_root: str | Path) -> Path | None:
    """``chains_root / basename(chains_path)`` when that file exists, else None.

    The database records where the chains were written *on the machine that
    fitted them* (the PVC); the workstation copy keeps the file names, so the
    basename is the join key.
    """
    if not chains_path:
        return None
    candidate = Path(chains_root) / Path(chains_path).name
    return candidate if candidate.is_file() else None


def count_from_npz(path: str | Path) -> int:
    """``n_neg_blue`` of the spectrum stored in a chain NPZ (``wave``/``Rrs``).

    Only those two members are decompressed; the chains themselves are not
    read.
    """
    with np.load(path, allow_pickle=False) as npz:
        wave, rrs = npz["wave"], npz["Rrs"]
    return int(rrs_qa_quantities(wave, rrs)[0]["value"])


def plan(store: Store, *, pab_version: str, model_pair: str) -> list[dict[str, Any]]:
    """The fits in scope — one dict per BING fit of ``pab_version`` /
    ``model_pair`` with its stored ``chains_path`` and whether it already
    carries the quantity (``existing``, the stored value or ``None``)."""
    rows = store.query(
        """
        SELECT f.fit_id, f.chains_path, q.value AS existing
        FROM fits f
        LEFT JOIN fit_results q ON q.fit_id = f.fit_id AND q.quantity = ?
        WHERE f.algorithm = 'BING' AND f.model_pair = ? AND f.pab_version = ?
        ORDER BY f.fit_id
        """,
        (quantity_name(model_pair), model_pair, pab_version),
    )
    return rows


def backfill(
    store: Store,
    *,
    chains_root: str | Path,
    pab_version: str = "2.0",
    model_pair: str = "ExpBPow",
    dry_run: bool = False,
    replace: bool = False,
    batch: int = BATCH,
) -> dict[str, Any]:
    """Compute (and unless ``dry_run``, upsert) ``n_neg_blue`` for every fit in
    scope.

    Returns a summary dict: ``n_fits`` (in scope), ``n_written`` (rows
    upserted, 0 under ``dry_run``), ``n_computed`` (values read from an NPZ —
    what a dry run *would* write), ``n_skipped_existing`` (already had the
    quantity and ``replace`` is False), ``n_missing_npz`` plus ``missing``
    (``[(fit_id, reason), …]``), ``n_flagged`` (computed values ≥ 1) and
    ``values`` (``{fit_id: n_neg_blue}`` for every computed fit).
    """
    qname = quantity_name(model_pair)
    todo = plan(store, pab_version=pab_version, model_pair=model_pair)
    summary: dict[str, Any] = {
        "quantity": qname,
        "pab_version": pab_version,
        "chains_root": str(chains_root),
        "dry_run": dry_run,
        "replace": replace,
        "n_fits": len(todo),
        "n_written": 0,
        "n_computed": 0,
        "n_skipped_existing": 0,
        "n_missing_npz": 0,
        "missing": [],
        "n_flagged": 0,
        "values": {},
    }
    pending: list[dict[str, Any]] = []

    def _flush():
        if pending and not dry_run:
            summary["n_written"] += store.upsert_many("fit_results", pending)
        pending.clear()

    for k, row in enumerate(todo, 1):
        if row["existing"] is not None and not replace:
            summary["n_skipped_existing"] += 1
            continue
        npz = resolve_chain(row["chains_path"], chains_root)
        if npz is None:
            summary["n_missing_npz"] += 1
            summary["missing"].append((row["fit_id"], "no such file"))
            continue
        try:
            n_neg = count_from_npz(npz)
        except (OSError, KeyError, ValueError) as exc:  # unreadable / not a chain NPZ
            summary["n_missing_npz"] += 1
            summary["missing"].append((row["fit_id"], f"{type(exc).__name__}: {exc}"))
            continue
        summary["n_computed"] += 1
        summary["n_flagged"] += int(n_neg >= 1)
        summary["values"][row["fit_id"]] = n_neg
        pending.append(
            {
                "fit_id": row["fit_id"],
                "quantity": qname,
                "value": float(n_neg),
                "value_lo": float(n_neg),
                "value_hi": float(n_neg),
                "unit": "bands",
            }
        )
        if len(pending) >= batch:
            _flush()
        if k % 2000 == 0:
            _log.info("%s %d/%d fits", "planned" if dry_run else "backfilled", k, len(todo))
    _flush()

    if summary["n_missing_npz"]:
        shown = ", ".join(f for f, _ in summary["missing"][:5])
        more = "" if summary["n_missing_npz"] <= 5 else ", …"
        _log.warning(
            "%d of %d fits have no readable chain NPZ under %s and were skipped "
            "(%s%s)",
            summary["n_missing_npz"],
            summary["n_fits"],
            chains_root,
            shown,
            more,
        )
    return summary


# -- write discipline --------------------------------------------------------
def sha256(path: str | Path, *, chunk: int = 1 << 20) -> str:
    """Hex sha256 of a file."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def _connect_ro(path: str | Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True)


def rows_checksum(conn: sqlite3.Connection, *, exclude_quantity: str) -> dict[str, str]:
    """sha256 over every ``fits`` row and every ``fit_results`` row **other
    than** ``exclude_quantity`` (the one the backfill writes), in key order.

    Identical before and after a run means no pre-existing row was changed —
    the provenance rule the O-series preamble asks for. The written quantity
    is excluded so the invariant holds for ``--replace`` too.
    """
    out = {}
    for table, sql in (
        ("fits", "SELECT * FROM fits ORDER BY fit_id"),
        (
            "fit_results",
            "SELECT * FROM fit_results WHERE quantity != ? ORDER BY fit_id, quantity",
        ),
    ):
        h = hashlib.sha256()
        params = (exclude_quantity,) if "?" in sql else ()
        for row in conn.execute(sql, params):
            h.update(repr(tuple(row)).encode())
            h.update(b"\n")
        out[table] = h.hexdigest()
    return out


def fingerprint(db: str | Path, *, exclude_quantity: str) -> dict[str, Any]:
    """Everything the before/after comparison needs, read from a **read-only**
    connection: file sha256 + size, per-table counts, the count of
    ``exclude_quantity`` rows, :func:`rows_checksum` and ``integrity_check``."""
    db = Path(db)
    conn = _connect_ro(db)
    try:
        counts = {
            t: int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
            for t in TABLE_NAMES
        }
        n_q = int(
            conn.execute(
                "SELECT COUNT(*) FROM fit_results WHERE quantity = ?", (exclude_quantity,)
            ).fetchone()[0]
        )
        return {
            "path": str(db),
            "sha256": sha256(db),
            "size": db.stat().st_size,
            "counts": counts,
            "n_quantity_rows": n_q,
            "checksums": rows_checksum(conn, exclude_quantity=exclude_quantity),
            "integrity": [r[0] for r in conn.execute("PRAGMA integrity_check")],
        }
    finally:
        conn.close()


def format_fingerprint(fp: dict[str, Any], label: str) -> str:
    lines = [
        f"[{label}] {fp['path']}",
        f"  sha256 {fp['sha256']}  ({fp['size']:,} B)",
        "  rows   " + "  ".join(f"{t}={n:,}" for t, n in fp["counts"].items()),
        f"  {NEG_BLUE_QUANTITY} rows {fp['n_quantity_rows']:,}",
        f"  checksum fits        {fp['checksums']['fits']}",
        f"  checksum fit_results {fp['checksums']['fit_results']} (excl. the QA quantity)",
        f"  integrity_check      {fp['integrity']}",
    ]
    return "\n".join(lines)


def verify_after(before: dict[str, Any], after: dict[str, Any], summary: dict[str, Any]) -> list[str]:
    """The post-run invariants; returns the list of violations (empty = ok)."""
    problems = []
    for t in before["counts"]:
        if t == "fit_results":
            continue
        if before["counts"][t] != after["counts"][t]:
            problems.append(
                f"{t}: {before['counts'][t]:,} rows before, {after['counts'][t]:,} after"
            )
    # the non-QA fit_results rows: same number (their content is the checksum)
    other_before = before["counts"]["fit_results"] - before["n_quantity_rows"]
    other_after = after["counts"]["fit_results"] - after["n_quantity_rows"]
    if other_before != other_after:
        problems.append(
            f"fit_results other than {NEG_BLUE_QUANTITY}: {other_before:,} rows "
            f"before, {other_after:,} after"
        )
    # without --replace every written row is a new one
    expected = before["n_quantity_rows"] + summary["n_written"]
    if not summary["replace"] and after["n_quantity_rows"] != expected:
        problems.append(
            f"{NEG_BLUE_QUANTITY} rows: expected {expected:,} after, found "
            f"{after['n_quantity_rows']:,}"
        )
    if before["checksums"] != after["checksums"]:
        problems.append("a pre-existing fits/fit_results row changed (checksum mismatch)")
    if after["integrity"] != ["ok"]:
        problems.append(f"integrity_check: {after['integrity']}")
    return problems


def prepare_backup(db: str | Path, backup: str | Path, *, db_sha256: str) -> Path:
    """Make ``backup`` a byte copy of ``db``, or accept an existing one.

    An existing ``backup`` must hash to ``db_sha256`` (a fresh copy of *this*
    database); anything else is refused rather than silently reused, since
    it is what a bad run would be restored from.
    """
    db, backup = Path(db), Path(backup)
    if backup.resolve() == db.resolve():
        raise ValueError("--backup-copy must not be the database itself")
    if backup.exists():
        got = sha256(backup)
        if got != db_sha256:
            raise ValueError(
                f"existing backup {backup} has sha256 {got[:12]}…, the database "
                f"has {db_sha256[:12]}…; make a fresh copy"
            )
        return backup
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(db, backup)  # bytes only: no mode bits carried over
    got = sha256(backup)
    if got != db_sha256:
        raise ValueError(
            f"backup {backup} does not match the database after copying "
            f"({got[:12]}… vs {db_sha256[:12]}…) — is something writing to it?"
        )
    return backup


def refuse_unwritable_target(db: str | Path) -> None:
    """Refuse the frozen ``v1/`` tree and a database mid-transaction."""
    db = Path(db)
    if not db.is_file():
        raise FileNotFoundError(f"no database at {db}")
    if "v1" in db.resolve().parts:
        raise PermissionError(f"{db} is under v1/ — the frozen release is never written")
    for sidecar in (db.with_name(db.name + "-journal"), db.with_name(db.name + "-wal")):
        if sidecar.exists():
            raise RuntimeError(
                f"{sidecar.name} exists: the database has an open or interrupted "
                "transaction; finish or roll it back first"
            )


def format_summary(summary: dict[str, Any]) -> str:
    values = np.array(list(summary["values"].values()), dtype=float)
    verb = "would write" if summary["dry_run"] else "wrote"
    lines = [
        f"{summary['quantity']} backfill for pab_version {summary['pab_version']} "
        f"({'DRY RUN — nothing written' if summary['dry_run'] else 'written'})",
        f"  fits in scope          {summary['n_fits']:,}",
        f"  already had the row    {summary['n_skipped_existing']:,}"
        + ("" if summary["replace"] else " (skipped; --replace overwrites)"),
        f"  chain NPZ missing      {summary['n_missing_npz']:,}",
        f"  computed from NPZ      {summary['n_computed']:,} ({verb} that many rows)",
        f"  with n_neg_blue >= 1   {summary['n_flagged']:,}"
        + (
            f" ({100.0 * summary['n_flagged'] / summary['n_computed']:.2f} %)"
            if summary["n_computed"]
            else ""
        ),
    ]
    if values.size:
        lines.append(
            f"  n_neg_blue distribution  max {int(values.max())}, "
            f"median {np.median(values):g}, mean {values.mean():.3f}"
        )
    if not summary["dry_run"]:
        lines.append(f"  rows upserted          {summary['n_written']:,}")
    return "\n".join(lines)


# -- CLI -----------------------------------------------------------------------
def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        prog="python -m pab.fit.rrs_qa_backfill",
        description=(
            "Backfill the negative-blue QA count (n_neg_blue) into fit_results "
            "for existing BING fits, from their chain NPZs."
        ),
    )
    p.add_argument("--db", required=True, help="The PAB database (never v1/).")
    p.add_argument(
        "--chains-root",
        required=True,
        help="Directory holding the chain NPZs; fits.chains_path is resolved by basename.",
    )
    p.add_argument("--pab-version", default="2.0", help="fits.pab_version in scope (default 2.0).")
    p.add_argument("--model-pair", default="ExpBPow", help="fits.model_pair in scope.")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Open the database read-only, print the plan and the counts; write nothing.",
    )
    p.add_argument(
        "--replace",
        action="store_true",
        help="Overwrite an existing n_neg_blue row (default: skip such fits).",
    )
    p.add_argument(
        "--backup-copy",
        default=None,
        help=(
            "Required for a real run: a byte copy of --db made here before writing "
            "(or an existing copy whose sha256 equals the database's)."
        ),
    )
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    db = Path(args.db)
    chains_root = Path(args.chains_root)
    if not chains_root.is_dir():
        p.error(f"--chains-root {chains_root} is not a directory")
    qname = quantity_name(args.model_pair)

    if args.dry_run:
        if not db.is_file():
            p.error(f"no database at {db}")
        print(format_fingerprint(fingerprint(db, exclude_quantity=qname), "before (read-only)"))
        with Store.open(f"file:{db}?mode=ro", create=False) as store:
            summary = backfill(
                store,
                chains_root=chains_root,
                pab_version=args.pab_version,
                model_pair=args.model_pair,
                dry_run=True,
                replace=args.replace,
            )
        print(format_summary(summary))
        return 0

    # --- a real run ---------------------------------------------------------
    try:
        refuse_unwritable_target(db)
    except (FileNotFoundError, PermissionError, RuntimeError) as exc:
        p.error(str(exc))
    if not args.backup_copy:
        p.error(
            "a real run needs --backup-copy PATH (a dated copy such as "
            "v2/pab_pre_negblue_<date>.db); use --dry-run to see the plan"
        )
    before = fingerprint(db, exclude_quantity=qname)
    print(format_fingerprint(before, "before"))
    if before["integrity"] != ["ok"]:
        print(f"REFUSED: integrity_check failed before the run: {before['integrity']}")
        return 1
    try:
        backup = prepare_backup(db, args.backup_copy, db_sha256=before["sha256"])
    except ValueError as exc:
        print(f"REFUSED: {exc}")
        return 1
    print(f"backup copy {backup} sha256 {before['sha256']}")

    with Store.open(db, create=False) as store:
        summary = backfill(
            store,
            chains_root=chains_root,
            pab_version=args.pab_version,
            model_pair=args.model_pair,
            dry_run=False,
            replace=args.replace,
        )
    print(format_summary(summary))

    after = fingerprint(db, exclude_quantity=qname)
    print(format_fingerprint(after, "after"))
    problems = verify_after(before, after, summary)
    if problems:
        print("VERIFICATION FAILED — restore from the backup copy:")
        for prob in problems:
            print(f"  - {prob}")
        print(f"  cp {backup} {db}")
        return 1
    print(
        f"verified: only fit_results changed (+{after['counts']['fit_results'] - before['counts']['fit_results']:,} rows), "
        "pre-existing rows identical, integrity ok"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

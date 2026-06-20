"""Thin access layer over the SQLite store (the storage seam).

A small wrapper around the standard-library ``sqlite3`` providing:

* connection setup (foreign keys on, ``Row`` factory, schema creation);
* **idempotent upserts** keyed by each table's natural key
  (:data:`pab.db.schema.UPSERT_KEYS`);
* dict / DataFrame queries;
* CSV (stdlib) and Parquet (pandas) export;
* a pivot helper turning the long ``fit_results`` table into the wide,
  namespaced columns (``BING_ExpBPow_bbp`` …) the design describes.

Keeping this behind one thin class is deliberate: the backend can later change
(DuckDB/Parquet, PostgreSQL) without touching the matchup/analysis code.
"""

from __future__ import annotations

import csv
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from pab.db import schema


class Store:
    """A connection to the PAB SQLite store.

    Use :meth:`open` for a file/in-memory database, or construct directly from
    an existing connection. Supports the context-manager protocol::

        with Store.open("pab.db") as store:
            store.upsert("floats", {"wmo": 6903823})

    Args:
        conn: An open SQLite connection (already configured if you build it
            yourself; prefer :meth:`open`).
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # -- construction -------------------------------------------------------
    @classmethod
    def open(cls, path: str | Path = ":memory:", *, create: bool = True) -> Store:
        """Open (and by default create/migrate) a store at ``path``.

        Args:
            path: Filesystem path, or ``":memory:"`` for an ephemeral DB.
            create: If True, ensure the schema exists / is migrated.

        Returns:
            A ready :class:`Store`.
        """
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        store = cls(conn)
        if create:
            store.create()
        return store

    def create(self) -> None:
        """Create/migrate the schema (idempotent)."""
        schema.migrate(self.conn)

    def close(self) -> None:
        """Close the underlying connection."""
        self.conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- writes -------------------------------------------------------------
    def insert(self, table: str, row: Mapping[str, Any]) -> None:
        """Plain insert of one row (raises on key conflict)."""
        cols = list(row)
        sql = (
            f"INSERT INTO {table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' for _ in cols)})"
        )
        self.conn.execute(sql, [row[c] for c in cols])
        self.conn.commit()

    def upsert(self, table: str, row: Mapping[str, Any]) -> None:
        """Insert ``row``, or update the existing row with the same key.

        Idempotent: re-running with the same key updates in place rather than
        creating duplicates (the design's resumable-pipeline requirement). The
        conflict target is the table's natural key from
        :data:`pab.db.schema.UPSERT_KEYS`.

        Args:
            table: Target table name.
            row: Column -> value mapping. Must include the table's key columns.

        Raises:
            KeyError: if ``table`` has no registered upsert key, or ``row`` is
                missing a key column.
        """
        self.upsert_many(table, [row])

    def upsert_many(self, table: str, rows: Iterable[Mapping[str, Any]]) -> int:
        """Upsert many rows in a single transaction. Returns the row count."""
        rows = list(rows)
        if not rows:
            return 0
        if table not in schema.UPSERT_KEYS:
            raise KeyError(f"No upsert key registered for table {table!r}.")
        keys = schema.UPSERT_KEYS[table]
        cols = list(rows[0])
        for k in keys:
            if k not in cols:
                raise KeyError(f"Row for {table!r} is missing key column {k!r}.")
        non_key = [c for c in cols if c not in keys]
        placeholders = ", ".join("?" for _ in cols)
        conflict = ", ".join(keys)
        if non_key:
            updates = ", ".join(f"{c} = excluded.{c}" for c in non_key)
            action = f"DO UPDATE SET {updates}"
        else:
            action = "DO NOTHING"
        sql = (
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict}) {action}"
        )
        params = [[r[c] for c in cols] for r in rows]
        self.conn.executemany(sql, params)
        self.conn.commit()
        return len(rows)

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        """Run an arbitrary statement and commit (for migrations/maintenance)."""
        cur = self.conn.execute(sql, params)
        self.conn.commit()
        return cur

    # -- reads --------------------------------------------------------------
    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        """Run a SELECT and return rows as a list of plain dicts."""
        cur = self.conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def query_df(self, sql: str, params: Sequence[Any] = ()):
        """Run a SELECT and return a :class:`pandas.DataFrame`."""
        import pandas as pd

        return pd.read_sql_query(sql, self.conn, params=list(params))

    def table_df(self, table: str):
        """Return an entire table as a DataFrame (ordered by rowid/PK)."""
        return self.query_df(f"SELECT * FROM {table}")

    def count(self, table: str) -> int:
        """Return the number of rows in ``table``."""
        return int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    # -- export -------------------------------------------------------------
    def export_csv(self, table: str, path: str | Path) -> Path:
        """Export a table (or, if it contains a space, a SELECT) to CSV.

        Uses the stdlib ``csv`` module so CSV export carries no pandas
        dependency.

        Returns:
            The written path.
        """
        sql = table if " " in table.strip() else f"SELECT * FROM {table}"
        cur = self.conn.execute(sql)
        path = Path(path)
        with path.open("w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow([d[0] for d in cur.description])
            writer.writerows(cur.fetchall())
        return path

    def export_parquet(self, table: str, path: str | Path) -> Path:
        """Export a table (or SELECT) to Parquet via pandas/pyarrow."""
        sql = table if " " in table.strip() else f"SELECT * FROM {table}"
        df = self.query_df(sql)
        path = Path(path)
        df.to_parquet(path, index=False)
        return path

    # -- namespaced fit results --------------------------------------------
    def fit_results_wide(self, *, fit_ids: Sequence[str] | None = None):
        """Pivot ``fit_results`` long rows into wide, namespaced columns.

        Each ``quantity`` (e.g. ``BING_ExpBPow_bbp``) becomes a column carrying
        the posterior median, with companion ``<quantity>_lo``/``_hi`` columns
        for the credible interval; the frame is indexed by ``fit_id``.

        Args:
            fit_ids: Optional subset of fit IDs to include.

        Returns:
            A :class:`pandas.DataFrame` (one row per fit).
        """
        import pandas as pd

        sql = "SELECT fit_id, quantity, value, value_lo, value_hi FROM fit_results"
        params: list[Any] = []
        if fit_ids is not None:
            placeholders = ", ".join("?" for _ in fit_ids)
            sql += f" WHERE fit_id IN ({placeholders})"
            params = list(fit_ids)
        long = pd.read_sql_query(sql, self.conn, params=params)
        if long.empty:
            return pd.DataFrame()
        med = long.pivot(index="fit_id", columns="quantity", values="value")
        lo = long.pivot(index="fit_id", columns="quantity", values="value_lo")
        hi = long.pivot(index="fit_id", columns="quantity", values="value_hi")
        lo = lo.add_suffix("_lo")
        hi = hi.add_suffix("_hi")
        return pd.concat([med, lo, hi], axis=1)

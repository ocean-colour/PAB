"""SQLite schema for the PAB extracted-value store.

This module defines the table DDL and a light forward-migration mechanism. It
depends only on the standard-library ``sqlite3`` (no ORM), per the coding plan.

The schema captures the four entity groups the design calls for
(``docs/design/PAB_design.md`` -> *Storage and retrieval*):

* **floats / profiles** — BGC-Argo float identifiers and their vertical
  profiles (one row per WMO/cycle);
* **mixed-layer summaries** — one per profile: MLD, de-spiked/averaged
  ``bbp700`` and ``CHLA``, mean ``PSAL``/``TEMP``;
* **the matchup index** — ``profile <-> granule`` links and the ~10
  ``Rrs`` pixels selected per matchup;
* **namespaced fit results** — per-spectrum BING fits (metadata + provenance)
  plus their scalar IOP quantities in long format, named e.g.
  ``BING_ExpBPow_bbp`` so a second model pair (``BING_GIOP_bbp``) or the NASA
  baseline (``NASA_L2IOP_bbp``) coexists without colliding.

Bulky artifacts (MCMC chains, figures) are **not** stored here; the ``fits``
table records their on-disk paths, keyed by fit ID.

Units (recorded here for the schema-reference docs):

* depths/MLD in metres (m); ``bbp700`` and IOPs in m\\ :sup:`-1`;
  ``Rrs`` in sr\\ :sup:`-1`; ``CHLA`` in mg m\\ :sup:`-3`;
  ``PSAL`` in PSU; ``TEMP`` in degrees Celsius; wavelengths in nm;
  distances in km; time offsets in hours; timestamps as ISO-8601 text.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

#: Bumped whenever the DDL changes; stored in ``PRAGMA user_version`` so a
#: database file knows which schema it was created under (see ``migrate``).
SCHEMA_VERSION = 3

#: Ordered list of ``CREATE TABLE``/``CREATE INDEX`` statements. ``IF NOT
#: EXISTS`` keeps ``create_all`` idempotent.
TABLES: tuple[str, ...] = (
    # --- BGC-Argo floats & profiles ----------------------------------------
    """
    CREATE TABLE IF NOT EXISTS floats (
        wmo          INTEGER PRIMARY KEY,
        project_name TEXT,
        data_center  TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS profiles (
        profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
        wmo        INTEGER NOT NULL REFERENCES floats(wmo),
        cycle      INTEGER NOT NULL,
        latitude   REAL,
        longitude  REAL,
        time       TEXT,
        data_mode  TEXT,
        UNIQUE (wmo, cycle)
    )
    """,
    # --- Mixed-layer summary (1:1 with a profile) --------------------------
    """
    CREATE TABLE IF NOT EXISTS mld_summary (
        profile_id  INTEGER PRIMARY KEY REFERENCES profiles(profile_id),
        mld         REAL,            -- mixed-layer depth (m)
        mld_method  TEXT,            -- e.g. 'deBoyerMontegut_0.03'
        bbp700      REAL,            -- de-spiked mixed-layer mean (m^-1)
        bbp700_std  REAL,
        chla        REAL,            -- mixed-layer mean (mg m^-3)
        chla_std    REAL,
        psal        REAL,            -- mixed-layer mean (PSU)
        temp        REAL,            -- mixed-layer mean (degC)
        n_points    INTEGER,         -- samples within the MLD
        qa_path     TEXT,            -- per-profile Q&A figure on disk (not in DB)
        created     TEXT,
        pab_version TEXT
    )
    """,
    # --- PACE granule index ------------------------------------------------
    """
    CREATE TABLE IF NOT EXISTS granules (
        granule_id  TEXT PRIMARY KEY,  -- CMR concept-id / producer granule id
        short_name  TEXT,
        time_start  TEXT,
        time_end    TEXT,
        footprint   TEXT,              -- WKT polygon
        cloud_cover REAL,
        data_url    TEXT
    )
    """,
    # --- Matchup index (profile <-> granule), keyed by matchup_id ----------
    """
    CREATE TABLE IF NOT EXISTS matchups (
        matchup_id  TEXT PRIMARY KEY,  -- deterministic, encodes profile+granule
        profile_id  INTEGER NOT NULL REFERENCES profiles(profile_id),
        granule_id  TEXT NOT NULL REFERENCES granules(granule_id),
        distance_km REAL,              -- float <-> nearest pixel
        dtime_hours REAL,              -- |profile time - granule time|
        n_spectra   INTEGER,           -- valid spectra selected (~10)
        scene_path  TEXT,              -- PACE scene quick-look PNG on disk (not in DB)
        created     TEXT,
        pab_version TEXT,
        UNIQUE (profile_id, granule_id)
    )
    """,
    # --- The ~10 selected pixels/spectra per matchup -----------------------
    """
    CREATE TABLE IF NOT EXISTS matchup_pixels (
        pixel_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        matchup_id  TEXT NOT NULL REFERENCES matchups(matchup_id),
        ix          INTEGER,           -- pixel index (along-track)
        iy          INTEGER,           -- pixel index (cross-track)
        latitude    REAL,
        longitude   REAL,
        distance_km REAL,
        rank        INTEGER,           -- 1 = nearest valid pixel
        flagged     INTEGER,           -- 0/1 l2_flags screen result
        UNIQUE (matchup_id, ix, iy)
    )
    """,
    # --- BING fits (one row per fitted spectrum) ---------------------------
    """
    CREATE TABLE IF NOT EXISTS fits (
        fit_id       TEXT PRIMARY KEY,  -- encodes matchup+pixel+model+version
        matchup_id   TEXT NOT NULL REFERENCES matchups(matchup_id),
        pixel_id     INTEGER REFERENCES matchup_pixels(pixel_id),
        algorithm    TEXT,              -- e.g. 'BING'
        model_pair   TEXT,              -- e.g. 'ExpBPow'
        anw_model    TEXT,              -- e.g. 'ExpBricaud'
        bbnw_model   TEXT,              -- e.g. 'Pow'
        rrs_source   TEXT,              -- 'L2_AOP' | 'PAB_L1B:<algo/version>'
        prior_set    TEXT,
        nsteps       INTEGER,
        nburn        INTEGER,
        nwalkers     INTEGER,
        wave_min     REAL,              -- fit window (nm)
        wave_max     REAL,
        chisq        REAL,              -- reduced chi-squared
        aic          REAL,
        bic          REAL,
        accept_frac  REAL,              -- MCMC acceptance fraction
        success      INTEGER,           -- 0/1 LM+MCMC succeeded
        chains_path  TEXT,              -- NPZ on disk (not in DB)
        figure_path  TEXT,              -- PNG/PDF on disk (not in DB)
        pkg_versions TEXT,              -- JSON of pab.config.package_versions()
        pab_version  TEXT NOT NULL,
        created      TEXT
    )
    """,
    # --- Namespaced scalar IOP results (long format) -----------------------
    # Long format keeps the table stable as model pairs are added: a new pair
    # writes rows with a different `quantity` prefix rather than new columns.
    # Exports pivot this to the wide, namespaced columns the design describes.
    """
    CREATE TABLE IF NOT EXISTS fit_results (
        fit_id   TEXT NOT NULL REFERENCES fits(fit_id),
        quantity TEXT NOT NULL,         -- e.g. 'BING_ExpBPow_bbp'
        value    REAL,                  -- posterior median
        value_lo REAL,                  -- 5th percentile
        value_hi REAL,                  -- 95th percentile
        unit     TEXT,
        PRIMARY KEY (fit_id, quantity)
    )
    """,
    # --- Helpful secondary indexes ----------------------------------------
    "CREATE INDEX IF NOT EXISTS ix_profiles_wmo ON profiles(wmo)",
    "CREATE INDEX IF NOT EXISTS ix_matchups_profile ON matchups(profile_id)",
    "CREATE INDEX IF NOT EXISTS ix_matchups_granule ON matchups(granule_id)",
    "CREATE INDEX IF NOT EXISTS ix_pixels_matchup ON matchup_pixels(matchup_id)",
    "CREATE INDEX IF NOT EXISTS ix_fits_matchup ON fits(matchup_id)",
    "CREATE INDEX IF NOT EXISTS ix_fit_results_quantity ON fit_results(quantity)",
)

#: Table -> tuple of column names that uniquely identify a row, used by the
#: store's idempotent upsert. (Pure-Python source of truth so the store does
#: not have to introspect the DDL.)
UPSERT_KEYS: dict[str, tuple[str, ...]] = {
    "floats": ("wmo",),
    "profiles": ("wmo", "cycle"),
    "mld_summary": ("profile_id",),
    "granules": ("granule_id",),
    "matchups": ("matchup_id",),
    "matchup_pixels": ("matchup_id", "ix", "iy"),
    "fits": ("fit_id",),
    "fit_results": ("fit_id", "quantity"),
}

#: Tables in dependency order (parents before children) — handy for export and
#: for tests that want a deterministic ordering.
TABLE_NAMES: tuple[str, ...] = (
    "floats",
    "profiles",
    "mld_summary",
    "granules",
    "matchups",
    "matchup_pixels",
    "fits",
    "fit_results",
)


def create_all(conn: sqlite3.Connection) -> None:
    """Create every table/index if absent and stamp the schema version.

    Idempotent: safe to call on an existing database.

    Args:
        conn: An open SQLite connection.
    """
    cur = conn.cursor()
    for ddl in TABLES:
        cur.execute(ddl)
    cur.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


def get_version(conn: sqlite3.Connection) -> int:
    """Return the schema version stored in ``PRAGMA user_version`` (0 if unset)."""
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _v1_to_v2(conn: sqlite3.Connection) -> None:
    """v1 → v2: add ``mld_summary.qa_path`` (per-profile Q&A figure path)."""
    conn.execute("ALTER TABLE mld_summary ADD COLUMN qa_path TEXT")


def _v2_to_v3(conn: sqlite3.Connection) -> None:
    """v2 → v3: add ``matchups.scene_path`` (PACE scene quick-look figure path)."""
    conn.execute("ALTER TABLE matchups ADD COLUMN scene_path TEXT")


# Forward migrations: map a *starting* version to a callable that upgrades the
# database by one step.
MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _v1_to_v2,
    2: _v2_to_v3,
}


def migrate(conn: sqlite3.Connection) -> int:
    """Apply forward migrations until the DB reaches ``SCHEMA_VERSION``.

    A fresh (version-0) database is initialised via :func:`create_all`. An
    existing database is stepped forward through :data:`MIGRATIONS`.

    Args:
        conn: An open SQLite connection.

    Returns:
        The schema version after migrating.

    Raises:
        RuntimeError: if the database is newer than this code, or a required
            migration step is missing.
    """
    current = get_version(conn)
    if current == 0:
        create_all(conn)
        return SCHEMA_VERSION
    if current > SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema version {current} is newer than supported "
            f"{SCHEMA_VERSION}; upgrade PAB."
        )
    while current < SCHEMA_VERSION:
        step = MIGRATIONS.get(current)
        if step is None:
            raise RuntimeError(f"No migration registered from version {current}.")
        step(conn)
        current += 1
        conn.execute(f"PRAGMA user_version = {current}")
        conn.commit()
    return current

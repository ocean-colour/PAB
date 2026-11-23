"""``pab-viz`` / ``python -m pab.viz``: launch the PAB viz Bokeh server.

Read-only: the database is opened with a ``mode=ro`` URI and chain files are
only read. The server binds to ``localhost`` unless ``--host`` says otherwise
(which also needs ``--allow-remote``).
"""

from __future__ import annotations

import argparse
import functools
import importlib.util
import os
import socket
import sys
from pathlib import Path

from pab.viz import app, data, server
from pab.viz.server import LOCAL_HOSTS  # noqa: F401 - re-exported

#: The GDAC host argopy's ``src="gdac"`` reads from (for the start-up check).
GDAC_HOST = ("data-argo.ifremer.fr", 443)


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="pab-viz", description=__doc__.splitlines()[0])
    p.add_argument("--version", default=None,
                   help="BING version family shown first (default: the newest)")
    p.add_argument("--wmo", type=int, default=None, help="float opened first")
    p.add_argument("--cycle", type=int, default=None, help="cycle opened first")
    server.add_common_args(p, port=5006)
    return p.parse_args(argv)


def capability_report(db: str, data_dir: Path) -> list[str]:
    """What this machine can show (logged at start-up)."""
    lines = []
    store = data.open_store(db)
    try:
        fams = [data.family_label(store, f) for f in data.version_families(store)]
        n = store.query("SELECT COUNT(*) AS n FROM matchups")[0]["n"]
    finally:
        store.close()
    lines.append(f"DB          {db} (read-only): {n:,} matchups; BING families {fams}")
    chains = data_dir / "fit_chains"
    if chains.is_dir():
        counts: dict[str, int] = {}
        with os.scandir(chains) as it:
            for e in it:
                if e.name.endswith(".npz"):
                    v = e.name.rsplit("_v", 1)[-1][:-4]
                    counts[v] = counts.get(v, 0) + 1
        lines.append(f"chains      {chains}: " + ", ".join(
            f"{k}: {v:,}" for k, v in sorted(counts.items())))
    else:
        lines.append(f"chains      {chains}: MISSING -- model curves unavailable")
    for mod in ("bing", "robust"):
        ok = importlib.util.find_spec(mod) is not None
        lines.append(f"{mod:<11} {'ok' if ok else 'MISSING -- reconstruction will fail'}")
    try:
        socket.create_connection(GDAC_HOST, timeout=3).close()
        lines.append(f"network     {GDAC_HOST[0]} reachable (Argo fetched on demand)")
    except OSError as exc:
        lines.append(f"network     {GDAC_HOST[0]} NOT reachable ({exc}); "
                     "Argo panels will show stored values only")
    return lines


def main(argv=None) -> int:
    args = parse_args(argv)
    server.setup_logging("pab-viz")
    db = server.check_args(args, "pab-viz")
    if db is None:
        return 2
    data_dir = data.set_data_dir(args.data_dir or db.parent)
    for line in capability_report(str(db), data_dir):
        print("pab-viz:", line)

    cfg = app.AppConfig(db_path=str(db), model_pair=args.model_pair, wmo=args.wmo,
                        cycle=args.cycle, family=args.version)
    return server.serve(functools.partial(app.make_document, cfg=cfg), port=args.port,
                        host=args.host, show=args.show, prog="pab-viz")


if __name__ == "__main__":
    sys.exit(main())

"""``pab-viz`` / ``python -m pab.viz``: launch the PAB viz Bokeh server.

Read-only: the database is opened with a ``mode=ro`` URI and chain files are
only read. The server binds to ``localhost`` unless ``--host`` says otherwise
(which also needs ``--allow-remote``).
"""

from __future__ import annotations

import argparse
import functools
import importlib.util
import logging
import os
import socket
import sys
from pathlib import Path

from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from bokeh.server.server import Server

from pab.viz import app, data

LOCAL_HOSTS = ("localhost", "127.0.0.1")

#: The GDAC host argopy's ``src="gdac"`` reads from (for the start-up check).
GDAC_HOST = ("data-argo.ifremer.fr", 443)


def _default_db() -> str | None:
    root = os.environ.get("PAB_DATA_DIR")
    return str(Path(root) / "v2" / "pab.db") if root else None


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="pab-viz", description=__doc__.splitlines()[0])
    p.add_argument("--db", default=_default_db(),
                   help="SQLite store, opened read-only (default: $PAB_DATA_DIR/v2/pab.db)")
    p.add_argument("--data-dir", default=None,
                   help="folder holding fit_chains/ (default: the --db folder)")
    p.add_argument("--version", default=None,
                   help="BING version family shown first (default: the newest)")
    p.add_argument("--model-pair", default=data.DEFAULT_MODEL_PAIR)
    p.add_argument("--wmo", type=int, default=None, help="float opened first")
    p.add_argument("--cycle", type=int, default=None, help="cycle opened first")
    p.add_argument("--port", type=int, default=5006)
    p.add_argument("--host", default="localhost", help="interface to bind (default: localhost)")
    p.add_argument("--allow-remote", action="store_true",
                   help="required to bind anything other than localhost")
    p.add_argument("--show", action="store_true", help="open a browser tab")
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
    sys.stdout.reconfigure(line_buffering=True)  # log lines show up when piped / tee'd
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout,
                        format="pab-viz: %(levelname)s %(name)s: %(message)s")
    logging.getLogger("pab.viz").setLevel(logging.INFO)
    if not args.db:
        print("pab-viz: --db is required (or set PAB_DATA_DIR)", file=sys.stderr)
        return 2
    db = Path(args.db).expanduser().resolve()
    if not db.is_file():
        print(f"pab-viz: no database at {db}", file=sys.stderr)
        return 2
    if args.host not in LOCAL_HOSTS and not args.allow_remote:
        print(f"pab-viz: refusing to bind {args.host!r} without --allow-remote",
              file=sys.stderr)
        return 2
    data_dir = data.set_data_dir(args.data_dir or db.parent)
    for line in capability_report(str(db), data_dir):
        print("pab-viz:", line)

    cfg = app.AppConfig(db_path=str(db), model_pair=args.model_pair, wmo=args.wmo,
                        cycle=args.cycle, family=args.version)
    application = Application(FunctionHandler(functools.partial(app.make_document, cfg=cfg)))
    origins = [f"{h}:{args.port}" for h in LOCAL_HOSTS]
    if args.host not in LOCAL_HOSTS:
        origins.append(f"{args.host}:{args.port}")
    server = Server({"/": application}, port=args.port, address=args.host,
                    allow_websocket_origin=origins)
    server.start()
    url = f"http://{'localhost' if args.host in LOCAL_HOSTS else args.host}:{args.port}/"
    print(f"pab-viz: serving {url}  (Ctrl-C to stop)")
    if args.show:
        server.io_loop.add_callback(server.show, "/")
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        print("\npab-viz: stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())

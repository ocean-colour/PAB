"""Launch helpers shared by the viz servers (``pab-viz``, the BING-fit editor).

Read-only database, ``localhost`` unless ``--allow-remote`` (I-Q7), and one
place that starts a Bokeh server, so the two command lines cannot drift.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from bokeh.server.server import Server

LOCAL_HOSTS = ("localhost", "127.0.0.1")


def default_db() -> str | None:
    """``$PAB_DATA_DIR/v2/pab.db`` (never ``v1``), or ``None`` without the variable."""
    root = os.environ.get("PAB_DATA_DIR")
    return str(Path(root) / "v2" / "pab.db") if root else None


def add_common_args(p: argparse.ArgumentParser, *, port: int) -> None:
    """``--db``, ``--data-dir``, ``--model-pair``, ``--port``, ``--host``,
    ``--allow-remote`` and ``--show``."""
    from pab.viz import data

    p.add_argument("--db", default=default_db(),
                   help="SQLite store, opened read-only (default: $PAB_DATA_DIR/v2/pab.db)")
    p.add_argument("--data-dir", default=None,
                   help="folder holding fit_chains/ (default: the --db folder)")
    p.add_argument("--model-pair", default=data.DEFAULT_MODEL_PAIR)
    p.add_argument("--port", type=int, default=port)
    p.add_argument("--host", default="localhost", help="interface to bind (default: localhost)")
    p.add_argument("--allow-remote", action="store_true",
                   help="required to bind anything other than localhost")
    p.add_argument("--show", action="store_true", help="open a browser tab")


def check_args(args, prog: str) -> Path | None:
    """The resolved ``--db`` path, or ``None`` after printing why not (no DB,
    or a non-localhost bind without ``--allow-remote``)."""
    if not args.db:
        print(f"{prog}: --db is required (or set PAB_DATA_DIR)", file=sys.stderr)
        return None
    db = Path(args.db).expanduser().resolve()
    if not db.is_file():
        print(f"{prog}: no database at {db}", file=sys.stderr)
        return None
    if args.host not in LOCAL_HOSTS and not args.allow_remote:
        print(f"{prog}: refusing to bind {args.host!r} without --allow-remote",
              file=sys.stderr)
        return None
    return db


def setup_logging(prog: str) -> None:
    sys.stdout.reconfigure(line_buffering=True)  # log lines show up when piped / tee'd
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout,
                        format=f"{prog}: %(levelname)s %(name)s: %(message)s")
    logging.getLogger("pab.viz").setLevel(logging.INFO)


def serve(make_document, *, port: int, host: str, show: bool, prog: str) -> int:
    """Serve ``make_document(doc)`` at ``/`` until Ctrl-C."""
    application = Application(FunctionHandler(make_document))
    origins = [f"{h}:{port}" for h in LOCAL_HOSTS]
    if host not in LOCAL_HOSTS:
        origins.append(f"{host}:{port}")
    server = Server({"/": application}, port=port, address=host,
                    allow_websocket_origin=origins)
    server.start()
    url = f"http://{'localhost' if host in LOCAL_HOSTS else host}:{port}/"
    print(f"{prog}: serving {url}  (Ctrl-C to stop)")
    if show:
        server.io_loop.add_callback(server.show, "/")
    try:
        server.io_loop.start()
    except KeyboardInterrupt:
        print(f"\n{prog}: stopped")
    return 0

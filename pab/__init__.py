"""PAB — matchup analyses between PACE (satellite ocean color) and BGC-Argo data.

See ``docs/design/PAB_design.md`` for the design and
``docs/design/PAB_coding_plan.md`` for the development plan.
"""

import os

# Headless by default. PAB renders figures in batch/pipeline runs — including the
# `ingest` Q&A plots, which execute *alongside argopy's worker threads*. An
# interactive Matplotlib backend (e.g. TkAgg) tears its Tk objects down on the
# wrong thread there, aborting the process ("Tcl_AsyncDelete: async handler
# deleted by the wrong thread"). Set before Matplotlib is imported; a user who
# truly wants an interactive backend can still export MPLBACKEND themselves.
os.environ.setdefault("MPLBACKEND", "Agg")

from pab.config import pab_version  # noqa: E402  (after the MPLBACKEND default)

__version__ = pab_version

__all__ = ["pab_version", "__version__"]

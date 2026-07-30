"""Small shared helpers for the pipeline's parallel stages.

``ingest`` (network + argopy parsing), ``match`` (granule open + extract) and
``fit`` (BING MCMC) all fan out the same way: workers do the expensive
per-record work, the parent keeps the single SQLite writer. These two helpers
are what they share.
"""

from __future__ import annotations

__all__ = ["picklable", "init_worker"]


def picklable(obj) -> bool:
    """Whether ``obj`` survives a pickle round-trip to a spawned worker.

    ``None`` trivially does; a module-level function does; a lambda, closure or
    locally-defined function does not. Callers use this to decide between a
    process pool and a safe fallback (threads, or serial) instead of failing
    every record in the pool.
    """
    if obj is None:
        return True
    import pickle

    try:
        pickle.dumps(obj)
    except Exception:  # noqa: BLE001 — any pickling failure means "don't fork it"
        return False
    return True


def init_worker() -> None:  # pragma: no cover - runs in worker processes
    """Cap BLAS/OpenMP threads in a worker so N workers don't oversubscribe.

    The pool itself is the parallelism; each worker should stay single-threaded.
    """
    import os

    for var in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        os.environ.setdefault(var, "1")

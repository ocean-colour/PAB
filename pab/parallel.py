"""Small shared helpers for the pipeline's parallel stages.

``ingest`` (network + argopy parsing), ``match`` (granule open + extract) and
``fit`` (BING MCMC) all fan out the same way: workers do the expensive
per-record work, the parent keeps the single SQLite writer. These two helpers
are what they share.
"""

from __future__ import annotations

__all__ = [
    "picklable",
    "init_worker",
    "PROGRESS_EVERY",
    "cgroup_mem_gb",
    "mem_breakdown",
]

#: How often a long stage emits a progress line (records). A stage that runs for
#: tens of minutes in silence is indistinguishable from a hung one — `match` was
#: exactly that when a 1000-profile run was OOM-killed five minutes into it with
#: nothing logged.
PROGRESS_EVERY: int = 50


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


def cgroup_mem_gb() -> float | None:
    """Current memory charged to this container, in GB, or ``None`` off-cgroup.

    This is the number the OOM killer watches — RSS summed over the parent and
    every worker, plus page cache. Logging it alongside stage progress turns "the
    pod died at 15 min" into "memory climbed 3 GB/min from the third chunk", which
    is the difference between diagnosing a leak in one run and in five.
    """
    for path in ("/sys/fs/cgroup/memory.current",  # cgroup v2
                 "/sys/fs/cgroup/memory/memory.usage_in_bytes"):  # v1
        try:
            with open(path) as fh:
                return int(fh.read().strip()) / 1024**3
        except (OSError, ValueError):
            continue
    return None


def mem_breakdown() -> str:
    """``"cgroup X.X | parent Y.Y + N kids Z.Z GB"`` — who is holding the memory.

    The cgroup total alone says a pod is dying but not why. Splitting parent from
    children is what distinguishes "the driver is accumulating state" from "the
    workers are leaking", and those have completely different fixes. Three
    consecutive OOM investigations guessed at this instead of measuring it.
    """
    import os

    def _rss_gb(pid: str | int) -> float:
        try:
            with open(f"/proc/{pid}/status") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024**2
        except OSError:
            pass
        return 0.0

    me = os.getpid()
    parent = _rss_gb(me)
    kids, kid_rss = 0, 0.0
    try:
        for entry in os.listdir("/proc"):
            if not entry.isdigit() or int(entry) == me:
                continue
            try:
                with open(f"/proc/{entry}/status") as fh:
                    ppid = next(
                        (ln.split()[1] for ln in fh if ln.startswith("PPid:")), None
                    )
            except OSError:
                continue
            if ppid == str(me):
                kids += 1
                kid_rss += _rss_gb(entry)
    except OSError:
        pass
    total = cgroup_mem_gb()
    head = "cgroup ?" if total is None else f"cgroup {total:.1f}"
    return f"{head} | parent {parent:.1f} + {kids} kids {kid_rss:.1f} GB"

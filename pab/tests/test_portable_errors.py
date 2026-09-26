"""Worker exceptions that cannot be pickled must not hide their cause.

The 2026-09-25 ``match`` run logged ``TypeError: can't pickle
multidict._multidict.CIMultiDictProxy objects`` whose real cause was a NASA
**503** on an OB.DAAC granule: ``aiohttp``'s ``ClientResponseError`` carries
the HTTP headers as a ``CIMultiDictProxy``, which pickle refuses, so the pool
reported a serialization bug instead of the server error (Q8b).
"""

from __future__ import annotations

import pickle
from concurrent.futures import ProcessPoolExecutor

import pytest

from pab.parallel import WorkerError, picklable, portable_errors


class _Unpicklable(Exception):
    """Stands in for aiohttp's ClientResponseError: refuses to pickle."""

    def __reduce__(self):
        raise TypeError("can't pickle _Unpicklable objects")


def test_unpicklable_exception_is_flattened():
    with pytest.raises(WorkerError) as ei:
        with portable_errors("granule G1"):
            raise _Unpicklable("503, message='Service Unavailable'")
    msg = str(ei.value)
    assert "granule G1" in msg
    assert "_Unpicklable" in msg
    assert "503" in msg, "the actual cause must survive"
    assert ei.value.origin == "_Unpicklable"


def test_flattened_error_survives_a_pickle_round_trip():
    """The whole point: the replacement must cross a process boundary."""
    try:
        with portable_errors("granule G1"):
            raise _Unpicklable("503")
    except WorkerError as exc:
        again = pickle.loads(pickle.dumps(exc))
        assert isinstance(again, WorkerError)
        assert "503" in str(again)
        assert again.origin == "_Unpicklable"


def test_picklable_exception_is_reraised_unchanged():
    """Callers that branch on a specific type must keep working."""
    with pytest.raises(TimeoutError) as ei:
        with portable_errors("granule G1"):
            raise TimeoutError("read timed out")
    assert not isinstance(ei.value, WorkerError)
    assert str(ei.value) == "read timed out"


def test_no_exception_passes_through():
    with portable_errors("granule G1"):
        value = 1 + 1
    assert value == 2


def test_unpicklable_is_actually_unpicklable():
    """Guard the guard: if this ever pickles, the tests above prove nothing."""
    assert picklable(_Unpicklable("x")) is False
    assert picklable(TimeoutError("x")) is True


def _raise_unpicklable():  # module level so the pool can submit it
    with portable_errors("granule G1"):
        raise _Unpicklable("503, message='Service Unavailable'")


def test_real_process_pool_reports_the_cause():
    """End to end: without the guard this surfaces an unrelated pickling error."""
    with ProcessPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_raise_unpicklable)
        with pytest.raises(Exception) as ei:  # noqa: PT011 — type is the assertion
            fut.result()
    msg = str(ei.value)
    assert "503" in msg, f"cause lost crossing the pool boundary: {msg!r}"
    assert "can't pickle" not in msg

"""`build_fits` must report progress and per-fit timing.

Prompt 6's slice ran 21 minutes in silence: `fit` was the only long stage with
neither progress nor timing, while `match`, `geometry` and `discover` all have
`PROGRESS_EVERY`. Two consequences, both real:

* the "s/fit" the gate needed had to be reconstructed afterwards from `created`
  timestamps, and
* that reconstruction is what revealed the naive total-wall figure (385 s/fit)
  was inflated by a one-time JAX compile, with the true steady-state cost at
  164 s/fit -- the difference between tripping Q12's 240 s pause trigger and
  clearing it.

A 15-23 h full send that logs nothing is undiagnosable while it runs, which is
exactly when diagnosis matters.
"""

from __future__ import annotations

import logging

from pab.fit.models import FitConfig


def test_startup_cost_is_reported_separately_from_per_fit_cost(caplog):
    """Worker spawn + JAX compile is a per-POOL cost; folding it into s/fit
    inflates the figure and can trip a pause trigger on an artefact."""
    from pab.db.store import Store
    from pab.fit import run
    from pab.tests.test_fit import _seed_matchup
    from pab.tests.test_pace import make_granule

    with Store.open(":memory:") as store:
        _seed_matchup(store)
        with caplog.at_level(logging.INFO, logger="pab.fit"):
            run.build_fits(
                store,
                config=FitConfig.v1(),
                opener=lambda _src: make_granule(),
                jobs=2,
            )

    msgs = [r.message for r in caplog.records]
    assert any("first result after" in m for m in msgs), (
        "build_fits does not report its startup cost; s/fit will silently "
        f"include the JAX compile. Saw: {msgs}"
    )


def test_progress_logging_exists_and_uses_the_shared_interval():
    """`fit` should use the same PROGRESS_EVERY as the other long stages."""
    import inspect

    from pab.fit import run
    from pab.parallel import PROGRESS_EVERY

    src = inspect.getsource(run._build_fits_parallel)
    assert "PROGRESS_EVERY" in src, "fit has no progress logging"
    assert "fit progress:" in src, "fit's progress line is not labelled"
    assert "median" in src and "s/fit" in src, (
        "fit progress does not report per-fit timing, which is the number the "
        "go/no-go gate is measured against"
    )
    assert isinstance(PROGRESS_EVERY, int) and PROGRESS_EVERY > 0

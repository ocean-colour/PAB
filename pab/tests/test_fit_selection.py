"""`fit` honours an explicit matchup selection — the leading-slice seam.

Mirrors the `match` selection added in Prompt 5 Q5. The trap that change was
made to close is the one pinned hardest here: a stage that silently ignores a
selection reports success having done the *unrestricted* thing, which cost a
job launch in Prompt 5 Task 4.
"""

from __future__ import annotations

from pab.fit.models import FitConfig
from pab.pipeline import PipelineConfig


def test_no_selection_means_the_whole_store():
    """`None` is 'no selection given' — a bare `pab --stage fit` is unchanged."""
    assert PipelineConfig().matchup_ids() is None


def test_explicit_matchups_become_a_set():
    cfg = PipelineConfig(matchups=["m1", "m2", "m1"])
    assert cfg.matchup_ids() == {"m1", "m2"}


def test_matchups_csv_is_read(tmp_path):
    csv = tmp_path / "slice.csv"
    csv.write_text("matchup_id,basin\nm1,Pacific\nm2,Atlantic\n")
    assert PipelineConfig(matchups_csv=str(csv)).matchup_ids() == {"m1", "m2"}


def test_csv_and_flags_union(tmp_path):
    csv = tmp_path / "slice.csv"
    csv.write_text("matchup_id\nm1\n")
    cfg = PipelineConfig(matchups=["m2"], matchups_csv=str(csv))
    assert cfg.matchup_ids() == {"m1", "m2"}


def test_empty_selection_means_nothing_not_everything():
    """The `None` vs `set()` distinction that makes the default safe."""
    cfg = PipelineConfig(matchups=[])
    assert cfg.matchup_ids() == set()
    assert cfg.matchup_ids() is not None


def test_fit_stage_forwards_the_selection(monkeypatch):
    """The failure mode from Prompt 5 Task 4: the flag exists but is ignored."""
    from pab import pipeline

    seen = {}

    def _fake_build_fits(store, **kw):
        seen.update(kw)
        return {"written": [], "skipped": [], "failed": []}

    import pab.fit.run as run

    monkeypatch.setattr(run, "build_fits", _fake_build_fits)
    cfg = PipelineConfig(matchups=["m1", "m2"], fit=FitConfig())
    pipeline.fit(store=object(), config=cfg)

    assert "selection" in seen, "fit() dropped the selection on the floor"
    assert seen["selection"] == {"m1", "m2"}


def test_a_selection_that_excludes_everything_opens_no_granule():
    """The filter must bite *before* any granule I/O, as it does in `match`."""
    from pab.db.store import Store
    from pab.fit import run
    from pab.tests.test_fit import _seed_matchup

    with Store.open(":memory:") as store:
        _seed_matchup(store)

        def _explode(_source):
            raise AssertionError("a filtered-out matchup must not open its granule")

        out = run.build_fits(
            store,
            config=FitConfig.v1(),  # gordon: no geometry requirement
            opener=_explode,
            selection={"a-matchup-that-is-not-in-the-store"},
        )
        assert out["written"] == []
        assert out["failed"] == []
        assert out["skipped"] == []


def test_the_same_store_without_a_selection_does_attempt_the_matchup():
    """Guards the guard: the test above must pass for the right reason."""
    from pab.db.store import Store
    from pab.fit import run
    from pab.tests.test_fit import _seed_matchup

    with Store.open(":memory:") as store:
        matchup_id, _ = _seed_matchup(store)
        opened: list[str] = []

        def _counting_opener(source):
            opened.append(source)
            raise RuntimeError("stop after the open")

        out = run.build_fits(
            store, config=FitConfig.v1(), opener=_counting_opener, selection=None
        )
        attempted = set(out["written"]) | set(out["failed"])
        assert attempted, "nothing was attempted even without a selection"
        assert all(matchup_id in a for a in attempted), attempted

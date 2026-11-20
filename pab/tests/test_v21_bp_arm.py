"""The v2.1 fixed-``B_p`` arm driver (``nautilus/v21_bp_arm.py``)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from pab.fit import FitConfig
from pab.fit.models import GEOM_NORMALIZED, GEOM_OBSERVED

_PATH = Path(__file__).resolve().parents[2] / "nautilus" / "v21_bp_arm.py"


@pytest.fixture(scope="module")
def arm():
    spec = importlib.util.spec_from_file_location("v21_bp_arm", _PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_arm_configs_differ_by_geometry_only(arm):
    n = arm.arm_config("normalized", 0.014)
    o = arm.arm_config("observed", 0.014)
    assert n.geometry_mode == GEOM_NORMALIZED and o.geometry_mode == GEOM_OBSERVED
    assert n.fit_Bp is False and o.fit_Bp is False
    assert n.Bp_value == o.Bp_value == 0.014
    # nothing but the geometry differs between the two passes
    assert o == FitConfig(**{**n.__dict__, "geometry_mode": GEOM_OBSERVED})
    # and the observed pass is the 2.0.1 configuration with B_p fixed
    assert o == FitConfig.v2_0_1(fit_Bp=False, Bp_value=0.014)


def test_arm_config_rejects_an_unknown_mode(arm):
    with pytest.raises(ValueError, match="geometry-mode"):
        arm.arm_config("nadir", 0.014)


def test_read_selection(arm, tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("matchup_id,band\nA,1\nB,2\n")
    assert arm.read_selection(p) == {"A", "B"}
    (tmp_path / "e.csv").write_text("matchup_id\n")
    with pytest.raises(ValueError):
        arm.read_selection(tmp_path / "e.csv")


def test_parser_requires_the_mode(arm):
    with pytest.raises(SystemExit):
        arm.build_parser().parse_args(["--db", "x", "--data-dir", "d",
                                       "--matchups-csv", "c", "--replay-chains", "r"])

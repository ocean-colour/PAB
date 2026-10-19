#!/usr/bin/env python
"""O8 — the emulator out-of-domain slice test (``on_out_of_domain="ztt"``).

Prompts/Outliers O8 of ``claude_prompts/v2/report_improvements.md``
(Q&A/Outliers 5 = A). Nothing here is production: no database is written, no
chain is persisted under ``$PAB_DATA_DIR`` (the script refuses to run unless
``PAB_DATA_DIR`` points somewhere else), no BING or robust code is changed on
disk — the policy is installed by **monkeypatching at runtime**, in the parent
and in every worker.

What is tested
--------------
``bing.evaluate._robust_forward_jit`` builds (and ``lru_cache``s) a jitted
closure around ``robust.rt.forward(...)`` and never passes
``on_out_of_domain``, so production runs robust's default ``"warn"`` — a
*host-side* warning that is silent under ``jit``. ``"ztt"`` is the traceable
alternative: it zeroes the emulator's learned correction on every sample whose
features leave the trained range, so the model degrades to the analytic ZTT
backbone there. ``bing.evaluate`` looks ``forward`` up on the ``robust.rt``
module at call time, so replacing that attribute **before** the closure is
built is enough (:func:`install_policy`).

Three arms, all under the **2.0 priors** (``FitConfig.v2_0()``, log-uniform to
10⁵ m⁻¹ — the question is whether the runaway basin survives, not whether a
ceiling hides it):

``warn``
    The production forward model (control).
``ztt``
    ``robust.rt.forward = partial(forward, on_out_of_domain="ztt")`` — the
    policy exactly as robust ships it. **Because the packaged emulator was
    trained at nadir view / zero azimuth (its ``cos_theta_v`` and ``cos_dphi``
    domain is ``[1, 1]``) and every PAB pixel is off-nadir (θ_v 13–60°), the
    per-sample mask is True for every sample of every fit, so this arm is the
    pure ZTT backbone** (``mode="ztt"``) — proven on real inputs by
    :func:`prove_patch`.
``ztt_iop``
    A diagnostic arm beyond the prompt's two: the same ``"ztt"`` policy with
    ``Emulator.out_of_domain_mask`` patched to judge only the five features
    the emulator actually learned from (``log10_u``, ``eta_bb``, ``B_p``,
    ``wave_nm``, ``cos_theta_s``), ignoring the two constant view-geometry
    features. This is the question the prompt meant — does the basin survive
    when the emulator is confined to its *IOP* domain.

Per spectrum and arm: the LM warm-start under the production initial guess
(all 101), the χ² profile versus fixed ``Bnw`` (the §4 method; the four
report cases), a full production-length MCMC (8 runaways + 8 ordinary),
``emulator.out_of_domain(...)`` at the LM solution / posterior median, and
every ``DomainWarning`` BING raises (``warnings.catch_warnings(record=True)``;
``PYTHONWARNINGS`` is left alone).

Usage::

    PAB_DATA_DIR=<scratch> python run_ztt_slice.py run \
        --db $PAB_DATA_DIR_REAL/v2/pab.db --chains $PAB_DATA_DIR_REAL/v2/fit_chains \
        --sample-list /tmp/claude-1000/pab-outliers/chains_sample.txt \
        --outdir <scratch>/o8 [--jobs 8] [--arms warn,ztt,ztt_iop] [--lm-only]
    python run_ztt_slice.py analyze --outdir <scratch>/o8 --figdir versions/v2/ztt_slice

The database is opened read-only (``file:…?mode=ro``) for geometry, the Chl
seed and the float/2.0/2.0.1 values; the spectra come from the 2.0 chain NPZs
(``wave``, ``Rrs``, ``varRrs`` exactly as ``prepare_spectrum`` produced them —
the O6 replay seam's input, Q&A/Outliers 8 = C).
"""

from __future__ import annotations

import argparse
import csv
import functools
import json
import os
import sys
import time
import warnings
from pathlib import Path

import numpy as np

ARMS = ("warn", "ztt", "ztt_iop")
ARM_COLOR = {"warn": "#2a78d6", "ztt": "#eb6834", "ztt_iop": "#1baf7a"}
ARM_LABEL = {
    "warn": 'on_out_of_domain="warn" (production)',
    "ztt": 'on_out_of_domain="ztt" (as shipped = pure ZTT off-nadir)',
    "ztt_iop": '"ztt" judged on IOP features only (diagnostic)',
}
GREY = "#9a9891"

#: The four report cases (§4 of high_bbp_outliers.md) — the χ² profile set.
REPORT_CASES = ((6903874, 139), (4903784, 112), (7901007, 400), (2903902, 30))
#: Two more runaways O5 re-fitted (the all-positive Baltic one with a poor
#: physical basin; a 10-band negative one); two further ones are drawn.
EXTRA_MCMC_RUNAWAYS = ((4903489, 51), (4903462, 128))
SEED = 42
N_ORDINARY = 50
N_MCMC_EACH = 8
VIEW_FEATURES = ("cos_theta_v", "cos_dphi")
#: ``Bnw`` (log10 b_bp at 600 nm) above which an LM solution is in the runaway
#: basin (the physical basin is below −1; the wall is at 0–1; the ceiling 5).
RUNAWAY_BNW = 3.0
AT_CEILING_BNW = 4.5
PROFILE_GRID = (-4, -3.5, -3, -2.5, -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5, 3, 4, 4.9)
#: The packaged emulator's trained ``B_p`` range (``load_default().domain``,
#: 2026-10-19); the ``fit_Bp`` prior is [0.004, 0.05] and the seed is 0.01.
BP_DOMAIN = (0.010264424, 0.018003248)

POLICY = "warn"
_ORIG: dict = {}


# --------------------------------------------------------------------- policy
def _iop_only_mask(self, iops, phase_params, geometry, wave=None, *, tol=None,
                   theta_s_limits="default"):
    """``Emulator.out_of_domain_mask`` ignoring the constant view-geometry features.

    Same arithmetic as robust's (``robust/rt/emulator.py``), with the excess of
    ``cos_theta_v``/``cos_dphi`` forced to −∞ so they can never trip the mask.
    """
    import jax.numpy as jnp
    from robust.rt import emulator as E

    tol = E.DOMAIN_TOL if tol is None else tol
    if theta_s_limits == "default":
        theta_s_limits = E.SUPPORTED_THETA_S
    x = E.features(iops, phase_params, geometry, wave)
    lo, hi = E._effective_domain(self.domain, theta_s_limits)
    span = hi - lo
    scale = jnp.where(span > 0.0, span, E._STD_FLOOR)
    excess = jnp.maximum(lo - x, x - hi) / scale
    keep = jnp.asarray([name not in VIEW_FEATURES for name in E.FEATURES])
    excess = jnp.where(keep, excess, -jnp.inf)
    return jnp.any(~(excess <= tol), axis=(-1, -2))


def install_policy(policy: str) -> None:
    """Install one arm's forward model **before** BING builds its jitted closure.

    ``bing.evaluate`` does ``from robust import rt as robust_rt`` and calls
    ``robust_rt.forward(...)`` inside the closure, so rebinding the module
    attribute is seen by BING; the ``lru_cache`` is cleared so a closure built
    under another policy cannot be reused.
    """
    global POLICY
    import bing.evaluate as ev
    import robust.rt as rrt
    from robust.rt import emulator as E
    from robust.rt import hybrid as H

    if policy not in ARMS:
        raise ValueError(f"unknown arm {policy!r}; one of {ARMS}")
    _ORIG.setdefault("forward", H.forward)
    _ORIG.setdefault("mask", E.Emulator.out_of_domain_mask)
    if policy == "warn":
        rrt.forward = _ORIG["forward"]
    else:
        rrt.forward = functools.partial(_ORIG["forward"], on_out_of_domain="ztt")
    E.Emulator.out_of_domain_mask = _iop_only_mask if policy == "ztt_iop" else _ORIG["mask"]
    ev._robust_forward_jit.cache_clear()
    POLICY = policy


def _worker_init(policy: str) -> None:  # pragma: no cover - worker process
    from pab.parallel import init_worker

    init_worker()  # thread caps before JAX initialises
    install_policy(policy)


# ------------------------------------------------------------------ fit setup
def _config():
    from pab.fit.models import FitConfig

    return FitConfig.v2_0()


def _setup(spec):
    """Rebuild one fit's inputs exactly as ``fit_spectrum`` does (2.0 priors)."""
    from bing.models import utils as model_utils

    from pab.fit import run as frun
    from pab.fit.models import build_models

    config = _config()
    with np.load(spec["npz"], allow_pickle=False) as z:
        wave = np.asarray(z["wave"], float)
        Rrs = np.asarray(z["Rrs"], float)
        var = np.asarray(z["varRrs"], float)
        chains = np.asarray(z["chains"], float)
        names = [str(n) for n in z["param_names"]]
    geom = frun.obs_geometry(spec["theta_s"], spec["theta_v"], spec["dphi"])
    wave_w, Rrs_w, var_w = frun.prepare_spectrum(wave, Rrs, np.sqrt(var), config=config)
    p, rt_dict, models = build_models(config, wave_w, geom=geom)
    chl = spec["chl"]
    chl_val = chl if chl is not None else 0.1  # fit_spectrum's seed rule
    model_utils.init_other_bits(models, Chl=np.array([chl_val], float), Y=None, Rrs=Rrs_w)
    frun.set_inelastic_Ed(models, geom, rt_dict)
    low, high = frun._prior_bounds(models)
    p0 = np.clip(frun._initial_guess(models, Rrs_w), low, high)
    from bing.rt import defs as rt_defs

    p0 = np.append(p0, float(config.Bp_value))
    low = np.append(low, rt_defs.BP_PRIOR_PMIN)
    high = np.append(high, rt_defs.BP_PRIOR_PMAX)
    p0 = np.clip(p0, low, high)
    burn = config.analysis_burn
    flat = chains[burn:].reshape(-1, chains.shape[-1])
    stored_med = np.median(flat, axis=0)
    step0_med = np.median(chains[0], axis=0)
    bp = flat[:, names.index("Bp")]
    return dict(
        config=config, wave=wave_w, Rrs=Rrs_w, var=var_w, geom=geom, rt_dict=rt_dict,
        models=models, low=low, high=high, p0=p0, names=names, chl=chl_val,
        stored_med=stored_med, step0_med=step0_med,
        stored_Bp_in_domain_frac=float(np.mean((bp >= BP_DOMAIN[0]) & (bp <= BP_DOMAIN[1]))),
    )


def _model_rrs(st, params):
    from pab.fit import run as frun

    a_p, bb_p, bp = frun._split_flat(np.asarray(params, float)[None, :], st["models"][0].nparam, st["rt_dict"])
    return np.squeeze(frun.reconstruct_rrs(st["models"], a_p[0], bb_p[0], st["rt_dict"], geom=st["geom"], Bp=float(bp[0])))


def _red_chi2(st, params):
    pred = _model_rrs(st, params)
    return float(np.sum((pred - st["Rrs"]) ** 2 / st["var"]) / max(st["Rrs"].size - len(params), 1))


def _out_of_domain(st, params):
    """``emulator.out_of_domain`` at a parameter vector (BING's own adapter).

    Returns ``{feature: {lo, hi, worst, fraction, excess}}`` with the project's
    default θ_s envelope, plus two summaries: ``any`` (robust's verdict — what
    the shipped ``"ztt"`` mask acts on) and ``iop_only`` (ignoring the two
    view-geometry features).
    """
    import bing.evaluate as ev
    from robust.rt import emulator as E

    from pab.fit import run as frun

    a_p, bb_p, bp = frun._split_flat(np.asarray(params, float)[None, :], st["models"][0].nparam, st["rt_dict"])
    inp = ev._build_robust_inputs(st["models"][0], a_p[0], st["models"][1], bb_p[0], st["rt_dict"], st["geom"], float(bp[0]))
    em = E.load_default()
    rep = em.out_of_domain(inp.iops, inp.phase_params, inp.geometry, np.asarray(st["wave"], float))
    out = {k: dict(lo=b.lo, hi=b.hi, worst=b.worst, fraction=b.fraction, excess=b.excess) for k, b in rep.items()}
    return dict(features=out, any=bool(out), iop_only=any(k not in VIEW_FEATURES for k in out))


def _lm(st, p_start, low=None, high=None):
    from bing.fitting import chisq_fit

    low = st["low"] if low is None else low
    high = st["high"] if high is None else high
    pb, _cov, _ = chisq_fit.fit(
        (st["Rrs"], st["var"], np.clip(p_start, low, high), 0, st["geom"]),
        st["models"], st["rt_dict"], bounds=(low, high),
    )
    return np.asarray(pb, float)


def _bbp700(names, params):
    i_b, i_beta = names.index("Bnw"), names.index("beta")
    return float(10.0 ** params[i_b] * (600.0 / 700.0) ** params[i_beta])


def _pdict(names, params):
    d = {n: float(v) for n, v in zip(names, params, strict=True)}
    d["bbp700"] = _bbp700(names, params)
    return d


def _warn_strings(records):
    return [f"{w.category.__name__}: {w.message}" for w in records]


# ---------------------------------------------------------------------- tasks
def lm_task(spec):
    """LM warm-start from the production initial guess; χ² of the stored 2.0
    posterior median under this arm's forward; out-of-domain at p0 and the LM
    solution; the DomainWarning BING raises at the initial-guess check."""
    t0 = time.monotonic()
    st = _setup(spec)
    names = st["names"]
    out = dict(arm=POLICY, fit_id=spec["fit_id"], group=spec["group"], wmo=spec["wmo"], cycle=spec["cycle"])
    out["chi2_p0"] = _red_chi2(st, st["p0"])
    out["chi2_stored_median"] = _red_chi2(st, st["stored_med"])
    out["stored_median"] = _pdict(names, st["stored_med"])
    out["stored_Bp_in_domain_frac"] = st["stored_Bp_in_domain_frac"]
    out["p0"] = _pdict(names, st["p0"])
    out["ood_p0"] = _out_of_domain(st, st["p0"])
    out["ood_stored_median"] = _out_of_domain(st, st["stored_med"])
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        try:
            p_lm = _lm(st, st["p0"])
            out["lm_success"] = True
        except (RuntimeError, ValueError) as exc:
            p_lm = st["p0"].copy()
            out["lm_success"] = False
            out["lm_error"] = repr(exc)[:200]
    out["warnings_p0_check"] = _warn_strings(rec)
    out["p_lm"] = _pdict(names, p_lm)
    out["chi2_lm"] = _red_chi2(st, p_lm)
    out["ood_lm"] = _out_of_domain(st, p_lm)
    out["Bnw_lm"] = float(p_lm[names.index("Bnw")])
    out["runaway_basin"] = bool(out["Bnw_lm"] > RUNAWAY_BNW)
    out["at_ceiling"] = bool(out["Bnw_lm"] > AT_CEILING_BNW)
    out["elapsed_s"] = time.monotonic() - t0
    return out


def profile_task(spec):
    """Reduced-χ² profile versus fixed ``Bnw`` (§4 method): the other five
    parameters re-optimised by LM from three starts per grid point."""
    t0 = time.monotonic()
    st = _setup(spec)
    names = st["names"]
    i_b = names.index("Bnw")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            p_lm = _lm(st, st["p0"])
        except (RuntimeError, ValueError):
            p_lm = st["p0"].copy()
        prof = []
        for bfix in PROFILE_GRID:
            lo, hi = st["low"].copy(), st["high"].copy()
            lo[i_b], hi[i_b] = bfix - 1e-6, bfix + 1e-6
            best, best_p = np.inf, None
            for start in (p_lm, st["p0"], st["stored_med"]):
                s = start.copy()
                s[i_b] = bfix
                try:
                    pp = _lm(st, s, lo, hi)
                except (RuntimeError, ValueError):
                    continue
                c = _red_chi2(st, pp)
                if c < best:
                    best, best_p = c, pp
            prof.append(dict(Bnw=bfix, chi2=best if np.isfinite(best) else None,
                             params=None if best_p is None else _pdict(names, best_p)))
    return dict(arm=POLICY, fit_id=spec["fit_id"], wmo=spec["wmo"], cycle=spec["cycle"],
                profile=prof, chi2_lm=_red_chi2(st, p_lm), Bnw_lm=float(p_lm[i_b]),
                chi2_stored_median=_red_chi2(st, st["stored_med"]),
                Bnw_stored_median=float(st["stored_med"][i_b]), elapsed_s=time.monotonic() - t0)


def mcmc_task(spec, chains_dir):
    """Full production-length ``fit_spectrum`` under the 2.0 priors, every
    DomainWarning recorded (in order: LM p0 check, MCMC p0 check, posterior
    median check)."""
    from pab.fit import run as frun

    t0 = time.monotonic()
    st = _setup(spec)
    config = st["config"]
    with np.load(spec["npz"], allow_pickle=False) as z:
        wave, Rrs, var = np.asarray(z["wave"], float), np.asarray(z["Rrs"], float), np.asarray(z["varRrs"], float)
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        res = frun.fit_spectrum(wave, Rrs, np.sqrt(var), Chl=spec["chl"], geom=st["geom"], config=config)
    dom = [w for w in rec if w.category.__name__ == "DomainWarning"]
    names = res.param_names
    chains = res.chains
    flat = chains[config.analysis_burn:].reshape(-1, chains.shape[-1])
    med = np.median(flat, axis=0)
    q = {d["quantity"]: dict(value=d["value"], lo=d["value_lo"], hi=d["value_hi"]) for d in res.quantities}
    i_b = names.index("Bnw")
    out = dict(
        arm=POLICY, fit_id=spec["fit_id"], group=spec["group"], wmo=spec["wmo"], cycle=spec["cycle"],
        success=bool(res.success), chisq=float(res.chisq), accept_frac=float(res.accept_frac),
        quantities=q, posterior_median=_pdict(names, med),
        step0_Bnw_median=float(np.median(chains[0, :, i_b])),
        min_Bnw_anywhere=float(chains[:, :, i_b].min()),
        frac_steps_Bnw_above_3=float(np.mean(np.median(chains[:, :, i_b], axis=1) > RUNAWAY_BNW)),
        ood_posterior_median=_out_of_domain(st, med),
        domain_warnings=_warn_strings(dom), n_domain_warnings=len(dom),
        other_warnings=_warn_strings([w for w in rec if w.category.__name__ != "DomainWarning"])[:5],
        chain_start=res.chain_start, nsteps=config.nsteps, nburn=config.nburn,
        elapsed_s=time.monotonic() - t0,
    )
    path = Path(chains_dir) / f"{spec['fit_id']}__{POLICY}.npz"
    np.savez_compressed(path, chains=chains.astype(np.float32), wave=res.wave, Rrs=res.Rrs,
                        varRrs=res.varRrs, param_names=np.asarray(names), arm=POLICY)
    out["chains_path"] = str(path)
    return out


# ---------------------------------------------------------------------- proof
def prove_patch(spec, outdir):
    """Prove the policy is live, on synthetic IOPs and on a real runaway fit.

    (1) robust alone: in-domain IOPs at nadir → policy == hybrid; in-domain IOPs
    off-nadir → policy == pure ZTT (the view-geometry breach); out-of-domain IOPs
    → policy == pure ZTT. (2) Through BING's jitted path on the stored 2.0
    posterior median of a runaway: ``warn`` ≠ ``ztt``, and ``ztt`` equals the
    un-jitted ``mode="ztt"`` evaluation of the same inputs; ``ztt_iop`` leaves
    an in-domain ordinary fit's forward identical to ``warn``'s.
    """
    import bing.evaluate as ev
    import robust.rt as rrt
    from robust.rt import emulator as E
    from robust.rt import hybrid as H

    from pab.fit import run as frun

    em = E.load_default()
    wave = np.arange(400.0, 701.0, 5.0)
    n = wave.size
    bb_w = 0.5 * 0.0038 * (wave / 500.0) ** -4.32

    def iops(a0, bbp0):
        return rrt.IOPs.from_total_bb(a0 * np.ones(n), bbp0 * np.ones(n) + bb_w, wave=wave)

    pp = rrt.PhaseParams(B_p=0.014)
    cases = {
        "in-domain IOPs, nadir": (iops(0.05, 0.002), rrt.Geometry(theta_s=30.0, theta_v=0.0, dphi=0.0)),
        "in-domain IOPs, off-nadir (theta_v 30, dphi 90)": (iops(0.05, 0.002), rrt.Geometry(theta_s=30.0, theta_v=30.0, dphi=90.0)),
        "out-of-domain IOPs (u -> 1), nadir": (iops(0.05, 50.0), rrt.Geometry(theta_s=30.0, theta_v=0.0, dphi=0.0)),
    }
    proof = {"domain": dict(features=list(E.FEATURES), lo=np.asarray(em.domain[0]).tolist(), hi=np.asarray(em.domain[1]).tolist()), "synthetic": {}}
    for name, (io, g) in cases.items():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            hyb = np.asarray(H.forward(io, pp, g, wave, mode="hybrid", emulator=em))
            ztt = np.asarray(H.forward(io, pp, g, wave, mode="ztt"))
            pol = np.asarray(H.forward(io, pp, g, wave, mode="hybrid", emulator=em, on_out_of_domain="ztt"))
        proof["synthetic"][name] = dict(
            mask=bool(np.asarray(_ORIG.get("mask", E.Emulator.out_of_domain_mask)(em, io, pp, g, wave))),
            mask_iop_only=bool(np.asarray(_iop_only_mask(em, io, pp, g, wave))),
            breaches=list(em.out_of_domain(io, pp, g, wave)),
            max_rel_correction=float(np.max(np.abs(hyb - ztt) / ztt)),
            policy_equals_ztt=bool(np.allclose(pol, ztt)), policy_equals_hybrid=bool(np.allclose(pol, hyb)),
        )
    # (2) through BING's jitted path, real inputs
    st = _setup(spec)
    a_p, bb_p, bp = frun._split_flat(st["stored_med"][None, :], st["models"][0].nparam, st["rt_dict"])
    inp = ev._build_robust_inputs(st["models"][0], a_p[0], st["models"][1], bb_p[0], st["rt_dict"], st["geom"], float(bp[0]))
    inel = rrt.Inelastic(raman=inp.include_raman, fluorescence=inp.include_fl, phi_C=inp.phi_C, emission_shape=inp.emission_shape, cdom_fl=None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ztt_direct = np.asarray(_ORIG.get("forward", H.forward)(inp.iops, inp.phase_params, inp.geometry, np.asarray(st["wave"], float), mode="ztt", inelastic=inel, corrections=False))
        rrs = {}
        for arm in ARMS:
            install_policy(arm)
            rrs[arm] = np.asarray(_model_rrs(st, st["stored_med"]))
            assert ev.robust_rt.forward is rrt.forward
    install_policy("warn")
    proof["real_runaway"] = dict(
        fit_id=spec["fit_id"], theta_s=spec["theta_s"], theta_v=spec["theta_v"], dphi=spec["dphi"],
        stored_median=_pdict(st["names"], st["stored_med"]),
        max_rel_diff_warn_vs_ztt=float(np.max(np.abs(rrs["warn"] - rrs["ztt"]) / np.abs(rrs["ztt"]))),
        ztt_arm_equals_mode_ztt=bool(np.allclose(rrs["ztt"], ztt_direct, rtol=1e-5, atol=1e-9)),
        ztt_iop_arm_equals_mode_ztt=bool(np.allclose(rrs["ztt_iop"], ztt_direct, rtol=1e-5, atol=1e-9)),
        ood_stored_median=_out_of_domain(st, st["stored_med"]),
        cache_info=str(ev._robust_forward_jit.cache_info()),
    )
    Path(outdir, "proof_of_patch.json").write_text(json.dumps(proof, indent=1))
    print("proof of patch:", json.dumps(proof["synthetic"], indent=1))
    print("real runaway:", {k: v for k, v in proof["real_runaway"].items() if k not in ("stored_median", "ood_stored_median")})
    return proof


# -------------------------------------------------------------------- inputs
def _ro_store(db):
    from pab.db.store import Store

    return Store.open(f"file:{db}?mode=ro", create=False)


def _parse_basename(name):
    """``<matchup_id>_<ix>_<iy>_ExpBPow_v2.0.npz`` → (matchup_id, ix, iy)."""
    stem = name[: -len(".npz")] if name.endswith(".npz") else name
    stem = stem[: stem.rindex("_ExpBPow_v")]
    parts = stem.rsplit("_", 2)
    return parts[0], int(parts[1]), int(parts[2])


def build_specs(db, chains, refit_csv, sample_list, outdir):
    """The 101 inputs: 51 runaways (refit_51.csv) + 50 ordinary 2.0 fits drawn
    with seed 42 from the Outliers-1 300-fit sample list."""
    from pab.fit.run import make_fit_id

    store = _ro_store(db)
    chains = Path(chains)
    specs = []

    def spec_for(matchup_id, ix, iy, group):
        fit_id = make_fit_id(matchup_id, ix, iy, "ExpBPow", version="2.0")
        rows = store.query(
            "SELECT p.pixel_id, p.theta_s, p.theta_v, p.dphi, m.profile_id, s.chla, s.bbp700 AS float_bbp700, "
            "pr.wmo, pr.cycle, f.chisq AS chisq_2_0, f.success AS success_2_0 "
            "FROM matchup_pixels p JOIN matchups m ON m.matchup_id = p.matchup_id "
            "JOIN profiles pr ON pr.profile_id = m.profile_id "
            "LEFT JOIN mld_summary s ON s.profile_id = m.profile_id "
            "JOIN fits f ON f.pixel_id = p.pixel_id AND f.pab_version = '2.0' AND f.algorithm = 'BING' "
            "WHERE p.matchup_id = ? AND p.ix = ? AND p.iy = ?",
            (matchup_id, ix, iy),
        )
        if len(rows) != 1:
            raise RuntimeError(f"{fit_id}: expected one pixel row, got {len(rows)}")
        r = rows[0]
        qs = store.query(
            "SELECT quantity, value FROM fit_results WHERE fit_id = ? AND quantity IN "
            "('BING_ExpBPow_bbp700', 'BING_ExpBPow_n_neg_blue', 'BING_ExpBPow_chl')", (fit_id,)
        )
        qd = {q["quantity"].rsplit("_", 1)[-1] if not q["quantity"].endswith("n_neg_blue") else "n_neg_blue": q["value"] for q in qs}
        q201 = store.query(
            "SELECT value FROM fit_results WHERE fit_id = ? AND quantity = 'BING_ExpBPow_bbp700'",
            (make_fit_id(matchup_id, ix, iy, "ExpBPow", version="2.0.1"),)
        )
        chl = None if r["chla"] is None or not np.isfinite(r["chla"]) else float(r["chla"])
        return dict(
            fit_id=fit_id, matchup_id=matchup_id, ix=ix, iy=iy, pixel_id=r["pixel_id"], group=group,
            wmo=int(r["wmo"]), cycle=int(r["cycle"]), theta_s=r["theta_s"], theta_v=r["theta_v"], dphi=r["dphi"],
            chl=chl, float_bbp700=r["float_bbp700"], bbp700_2_0=qd.get("bbp700"), chl_2_0=qd.get("chl"),
            n_neg_blue=qd.get("n_neg_blue"), chisq_2_0=r["chisq_2_0"], success_2_0=r["success_2_0"],
            bbp700_2_0_1=q201[0]["value"] if q201 else None, npz=str(chains / f"{fit_id}.npz"),
        )

    with open(refit_csv) as fh:
        for row in csv.DictReader(fh):
            mid, ix, iy = _parse_basename(row["fit_id_2_0"] + ".npz")
            specs.append(spec_for(mid, ix, iy, "runaway"))
    runaway_ids = {s["fit_id"] for s in specs}
    names = sorted(line.strip() for line in open(sample_list) if line.strip())
    names = [n for n in names if n[: -len(".npz")] not in runaway_ids]
    rng = np.random.default_rng(SEED)
    pick = rng.choice(len(names), N_ORDINARY, replace=False)
    for k in sorted(pick):
        mid, ix, iy = _parse_basename(names[k])
        specs.append(spec_for(mid, ix, iy, "ordinary"))
    store.close()
    for s in specs:
        if not Path(s["npz"]).is_file():
            raise FileNotFoundError(s["npz"])
    # MCMC subsets
    by_key = {(s["wmo"], s["cycle"]): s for s in specs}
    mcmc_run = [by_key[k]["fit_id"] for k in REPORT_CASES + EXTRA_MCMC_RUNAWAYS]
    rest = sorted(s["fit_id"] for s in specs if s["group"] == "runaway" and s["fit_id"] not in mcmc_run)
    rng2 = np.random.default_rng(SEED)
    mcmc_run += [rest[i] for i in sorted(rng2.choice(len(rest), N_MCMC_EACH - len(mcmc_run), replace=False))]
    ordinary = [s["fit_id"] for s in specs if s["group"] == "ordinary"]
    mcmc_ord = ordinary[:N_MCMC_EACH]
    for s in specs:
        s["mcmc"] = s["fit_id"] in mcmc_run or s["fit_id"] in mcmc_ord
        s["profile"] = (s["wmo"], s["cycle"]) in REPORT_CASES
    Path(outdir, "specs.json").write_text(json.dumps(specs, indent=1))
    return specs


# ----------------------------------------------------------------------- run
def _guard_data_dir():
    real = Path(os.environ.get("PAB_DATA_DIR_REAL", "/home/xavier/Oceanography/data/Color/PAB")).resolve()
    cur = Path(os.environ.get("PAB_DATA_DIR", "")).resolve() if os.environ.get("PAB_DATA_DIR") else None
    if cur is None or cur == real or real in cur.parents:
        sys.exit(f"refusing to run: PAB_DATA_DIR must point at scratch, not {cur}")
    from pab.fit import artifacts

    if Path(artifacts.DATA_DIR).resolve() != cur:
        sys.exit(f"pab.fit.artifacts.DATA_DIR = {artifacts.DATA_DIR} ≠ PAB_DATA_DIR = {cur}")


def run(args):
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor, as_completed

    _guard_data_dir()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    chains_dir = outdir / "chains"
    chains_dir.mkdir(exist_ok=True)
    specs = build_specs(args.db, args.chains, args.refit_csv, args.sample_list, outdir)
    print(f"{len(specs)} spectra: {sum(s['group'] == 'runaway' for s in specs)} runaways, "
          f"{sum(s['group'] == 'ordinary' for s in specs)} ordinary; MCMC for {sum(s['mcmc'] for s in specs)}; "
          f"profiles for {sum(s['profile'] for s in specs)}", flush=True)
    proof_spec = next(s for s in specs if (s["wmo"], s["cycle"]) == REPORT_CASES[0])
    prove_patch(proof_spec, outdir)

    arms = [a for a in args.arms.split(",") if a]
    ctx = mp.get_context("spawn")
    timing = {}
    for arm in arms:
        t_arm = time.monotonic()
        results = dict(arm=arm, lm=[], profile=[], mcmc=[])
        with ProcessPoolExecutor(max_workers=args.jobs, mp_context=ctx, initializer=_worker_init, initargs=(arm,)) as ex:
            futs = {}
            if not args.lm_only:
                for s in specs:
                    if s["mcmc"]:
                        futs[ex.submit(mcmc_task, s, str(chains_dir))] = ("mcmc", s["fit_id"])
            for s in specs:
                if s["profile"]:
                    futs[ex.submit(profile_task, s)] = ("profile", s["fit_id"])
            for s in specs:
                futs[ex.submit(lm_task, s)] = ("lm", s["fit_id"])
            n_done = 0
            for fut in as_completed(futs):
                kind, fid = futs[fut]
                try:
                    results[kind].append(fut.result())
                except Exception as exc:  # noqa: BLE001
                    results[kind].append(dict(arm=arm, fit_id=fid, error=repr(exc)[:500]))
                    print(f"[{arm}] {kind} {fid} FAILED: {exc!r}"[:300], flush=True)
                n_done += 1
                if n_done % 20 == 0 or kind == "mcmc":
                    print(f"[{arm}] {n_done}/{len(futs)} done ({kind} {fid[:20]}…, {time.monotonic() - t_arm:.0f} s)", flush=True)
                Path(outdir, f"results_{arm}.json").write_text(json.dumps(results, indent=1, default=float))
        timing[arm] = time.monotonic() - t_arm
        print(f"[{arm}] arm done in {timing[arm] / 60:.1f} min", flush=True)
    Path(outdir, "timing.json").write_text(json.dumps(timing, indent=1))


# ------------------------------------------------------------------- analyze
def _load(outdir):
    specs = json.loads(Path(outdir, "specs.json").read_text())
    res = {}
    for p in sorted(Path(outdir).glob("results_*.json")):
        r = json.loads(p.read_text())
        res[r["arm"]] = r
    return specs, res


def analyze(args):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    outdir = Path(args.outdir)
    figdir = Path(args.figdir)
    figdir.mkdir(parents=True, exist_ok=True)
    specs, res = _load(outdir)
    arms = [a for a in ARMS if a in res]
    spec_by = {s["fit_id"]: s for s in specs}
    lm = {a: {r["fit_id"]: r for r in res[a]["lm"] if "error" not in r} for a in arms}
    summary = {"arms": arms, "n_specs": len(specs)}
    lines = []

    def say(s=""):
        lines.append(s)
        print(s)

    # --- Q1: LM endpoints of the 51 -------------------------------------
    say("## LM warm-start from the production initial guess (2.0 priors)")
    say("| arm | runaways: at ceiling (Bnw > 4.5) | runaway basin (Bnw > 3) | physical (Bnw < 0) | LM raised | ordinary: runaway basin | median χ²_red runaways / ordinary |")
    say("|---|---|---|---|---|---|---|")
    for a in arms:
        rr = [r for r in lm[a].values() if r["group"] == "runaway"]
        oo = [r for r in lm[a].values() if r["group"] == "ordinary"]
        row = dict(
            n_runaway=len(rr), at_ceiling=sum(r["at_ceiling"] for r in rr), runaway_basin=sum(r["runaway_basin"] for r in rr),
            physical=sum(r["Bnw_lm"] < 0 for r in rr), lm_failed=sum(not r["lm_success"] for r in rr),
            ordinary_runaway=sum(r["runaway_basin"] for r in oo), n_ordinary=len(oo),
            med_chi2_runaway=float(np.median([r["chi2_lm"] for r in rr])), med_chi2_ordinary=float(np.median([r["chi2_lm"] for r in oo])),
        )
        summary[f"lm_{a}"] = row
        say(f"| {a} | {row['at_ceiling']}/{row['n_runaway']} | {row['runaway_basin']}/{row['n_runaway']} | {row['physical']}/{row['n_runaway']} | {row['lm_failed']} | {row['ordinary_runaway']}/{row['n_ordinary']} | {row['med_chi2_runaway']:.2f} / {row['med_chi2_ordinary']:.2f} |")
    # cross-tab of the 51: warn basin vs each other arm's basin
    if "warn" in lm:
        say()
        say("## The 51 runaways: LM basin under warn × under the policy arm")
        for a in arms:
            if a == "warn":
                continue
            pairs = [(lm["warn"][f]["runaway_basin"], lm[a][f]["runaway_basin"]) for f in lm[a] if lm[a][f]["group"] == "runaway" and f in lm["warn"]]
            ct = dict(both_runaway=sum(w and z for w, z in pairs), rescued=sum(w and not z for w, z in pairs),
                      newly_runaway=sum((not w) and z for w, z in pairs), both_physical=sum((not w) and (not z) for w, z in pairs))
            summary[f"crosstab_warn_vs_{a}"] = ct
            still = sorted((lm[a][f]["wmo"], lm[a][f]["cycle"], spec_by[f]["n_neg_blue"]) for f in lm[a] if lm[a][f]["group"] == "runaway" and lm[a][f]["runaway_basin"])
            summary[f"still_runaway_{a}"] = still
            say(f"- warn → {a}: runaway in both {ct['both_runaway']}, rescued by the arm {ct['rescued']}, **newly runaway under the arm {ct['newly_runaway']}**, physical in both {ct['both_physical']}; still at the ceiling under {a}: " + ", ".join(f"{w}/{c} (n_neg_blue {int(n) if n is not None else '?'})" for w, c, n in still))
    # χ² of the stored 2.0 posterior median under each arm's forward
    say()
    say("## χ²_red of the stored 2.0 posterior median (the runaway solution) under each arm's forward model")
    for a in arms:
        rr = [r["chi2_stored_median"] for r in lm[a].values() if r["group"] == "runaway"]
        oo = [r["chi2_stored_median"] for r in lm[a].values() if r["group"] == "ordinary"]
        summary[f"chi2_stored_{a}"] = dict(runaway_median=float(np.median(rr)), runaway_min=float(np.min(rr)), runaway_max=float(np.max(rr)), ordinary_median=float(np.median(oo)))
        say(f"- {a}: runaways median {np.median(rr):.2f} (range {np.min(rr):.2f}–{np.max(rr):.1f}); ordinary median {np.median(oo):.2f}")

    # --- Q3: ordinary deltas ---------------------------------------------
    say()
    say("## The 50 ordinary fits: LM solution, arm minus warn (fits whose LM converged in both arms)")
    say("| arm | n | median Δlog10 b_bp(700) [16–84 %] | |Δ| > 0.1 dex | |Δ| > 0.3 dex | median Δχ²_red | χ² worse by > 1 | χ² better by > 1 | LM raised | out of domain at LM solution (robust verdict / IOP-only) |")
    say("|---|---|---|---|---|---|---|---|---|---|")
    for a in arms:
        all_oo = [(lm["warn"][f], lm[a][f]) for f in lm[a] if lm[a][f]["group"] == "ordinary" and f in lm["warn"]]
        oo = [(x, y) for x, y in all_oo if x["lm_success"] and y["lm_success"]]
        dl = np.array([np.log10(y["p_lm"]["bbp700"]) - np.log10(x["p_lm"]["bbp700"]) for x, y in oo])
        dc = np.array([y["chi2_lm"] - x["chi2_lm"] for x, y in oo])
        ood_any = sum(y["ood_lm"]["any"] for _, y in all_oo)
        ood_iop = sum(y["ood_lm"]["iop_only"] for _, y in all_oo)
        row = dict(n=len(oo), n_all=len(all_oo), lm_failed=sum(not y["lm_success"] for _, y in all_oo),
                   med_dlog=float(np.median(dl)), n_gt_0p1=int(np.sum(np.abs(dl) > 0.1)), n_gt_0p3=int(np.sum(np.abs(dl) > 0.3)),
                   med_dchi2=float(np.median(dc)), n_worse=int(np.sum(dc > 1)), n_better=int(np.sum(dc < -1)), ood_any=ood_any, ood_iop=ood_iop,
                   p16_dlog=float(np.percentile(dl, 16)), p84_dlog=float(np.percentile(dl, 84)), max_abs_dlog=float(np.max(np.abs(dl))))
        summary[f"ordinary_{a}"] = row
        say(f"| {a} | {row['n']} | {row['med_dlog']:+.3f} [{row['p16_dlog']:+.3f}, {row['p84_dlog']:+.3f}] | {row['n_gt_0p1']}/{row['n']} | {row['n_gt_0p3']}/{row['n']} | {row['med_dchi2']:+.3f} | {row['n_worse']} | {row['n_better']} | {row['lm_failed']} | {ood_any}/{row['n_all']} / {ood_iop}/{row['n_all']} |")
    # out-of-domain features at the ordinary LM solutions (warn arm)
    say()
    say("## Which features are out of domain (robust's `out_of_domain`, default θ_s envelope)")
    for grp in ("ordinary", "runaway"):
        for where in ("ood_p0", "ood_lm", "ood_stored_median"):
            cnt = {}
            rows = [r for r in lm["warn"].values() if r["group"] == grp]
            for r in rows:
                for k in r[where]["features"]:
                    cnt[k] = cnt.get(k, 0) + 1
            summary[f"ood_{grp}_{where}"] = dict(n=len(rows), **cnt)
            say(f"- {grp}, {where.replace('ood_', '')} (n = {len(rows)}): " + ", ".join(f"{k} {v}" for k, v in sorted(cnt.items(), key=lambda kv: -kv[1])))
    # Bp specifics at ordinary LM (warn)
    bps = np.array([r["p_lm"]["Bp"] for r in lm["warn"].values() if r["group"] == "ordinary"])
    summary["ordinary_Bp_lm_warn"] = dict(median=float(np.median(bps)), n_below_0p01026=int(np.sum(bps < 0.010264)), n_above_0p018=int(np.sum(bps > 0.018003)), n=len(bps))
    say(f"- ordinary LM `B_p` (warn): median {np.median(bps):.4f}; {summary['ordinary_Bp_lm_warn']['n_below_0p01026']} below 0.01026 and {summary['ordinary_Bp_lm_warn']['n_above_0p018']} above 0.018 of {len(bps)} (the trained range)")

    # --- DomainWarnings -------------------------------------------------
    say()
    say("## DomainWarnings")
    for a in arms:
        n_w = sum(bool(r["warnings_p0_check"]) for r in lm[a].values())
        summary[f"lm_warnings_{a}"] = dict(n_fits_with_warning_at_p0=n_w, n=len(lm[a]))
        say(f"- {a}: LM initial-guess check warned on {n_w}/{len(lm[a])} fits")
    mc = {a: {r["fit_id"]: r for r in res[a]["mcmc"] if "error" not in r} for a in arms}
    for a in arms:
        if not mc[a]:
            continue
        nw = [r["n_domain_warnings"] for r in mc[a].values()]
        pm = sum(r["ood_posterior_median"]["any"] for r in mc[a].values())
        pmi = sum(r["ood_posterior_median"]["iop_only"] for r in mc[a].values())
        pmi_ord = sum(r["ood_posterior_median"]["iop_only"] for r in mc[a].values() if r["group"] == "ordinary")
        n_ord = sum(r["group"] == "ordinary" for r in mc[a].values())
        summary[f"mcmc_warnings_{a}"] = dict(n=len(nw), warnings_per_fit=sorted(set(nw)), posterior_median_ood_any=pm, posterior_median_ood_iop_only=pmi, ordinary_posterior_median_ood_iop_only=pmi_ord, n_ordinary=n_ord)
        say(f"- {a}: MCMC fits raised {sorted(set(nw))} DomainWarnings each (n = {len(nw)}); posterior median out of domain by robust's verdict {pm}/{len(nw)}, by IOP features only {pmi}/{len(nw)} (ordinary: {pmi_ord}/{n_ord})")

    # --- MCMC table -------------------------------------------------------
    say()
    say("## Full MCMC (2.0 priors, 10,000 + 1,000 steps)")
    say("| case | group | float b_bp(700) | 2.0 (stored) | " + " | ".join(f"{a}: b_bp(700) [5–95] / χ²_red / step-0 Bnw" for a in arms) + " |")
    say("|---|---|---|---|" + "---|" * len(arms))
    mcmc_rows = []
    for fid in sorted(mc[arms[0]], key=lambda f: (spec_by[f]["group"], spec_by[f]["wmo"], spec_by[f]["cycle"])):
        s = spec_by[fid]
        cells = []
        rec = dict(fit_id=fid, wmo=s["wmo"], cycle=s["cycle"], group=s["group"], float_bbp700=s["float_bbp700"], bbp700_2_0=s["bbp700_2_0"], chisq_2_0=s["chisq_2_0"], bbp700_2_0_1=s["bbp700_2_0_1"])
        for a in arms:
            r = mc[a].get(fid)
            if r is None:
                cells.append("—")
                continue
            q = r["quantities"]["bbp700"]
            rec[f"{a}_bbp700"], rec[f"{a}_lo"], rec[f"{a}_hi"], rec[f"{a}_chisq"], rec[f"{a}_step0_Bnw"], rec[f"{a}_chl"], rec[f"{a}_Bp"] = q["value"], q["lo"], q["hi"], r["chisq"], r["step0_Bnw_median"], r["quantities"]["chl"]["value"], r["quantities"]["Bp"]["value"]
            cells.append(f"{q['value']:.2e} [{q['lo']:.1e}, {q['hi']:.1e}] / {r['chisq']:.2f} / {r['step0_Bnw_median']:.2f}")
        mcmc_rows.append(rec)
        fl = "—" if s["float_bbp700"] is None else f"{s['float_bbp700']:.2e}"
        say(f"| {s['wmo']}/{s['cycle']} | {s['group']} | {fl} | {s['bbp700_2_0']:.2e} / χ² {s['chisq_2_0']:.2f} | " + " | ".join(cells) + " |")
    summary["mcmc_rows"] = mcmc_rows
    for a in arms:
        rr = [r for r in mc[a].values() if r["group"] == "runaway"]
        oo = [r for r in mc[a].values() if r["group"] == "ordinary"]
        summary[f"mcmc_{a}"] = dict(
            runaway_n=len(rr), runaway_at_wall=sum(r["step0_Bnw_median"] > RUNAWAY_BNW for r in rr),
            runaway_below_gate=sum(r["quantities"]["bbp700"]["value"] < 1.0 for r in rr),
            ordinary_n=len(oo),
        )
        if oo and "warn" in mc:
            d = [np.log10(mc[a][f]["quantities"]["bbp700"]["value"]) - np.log10(mc["warn"][f]["quantities"]["bbp700"]["value"]) for f in mc[a] if mc[a][f]["group"] == "ordinary" and f in mc["warn"]]
            dc = [mc[a][f]["chisq"] - mc["warn"][f]["chisq"] for f in mc[a] if mc[a][f]["group"] == "ordinary" and f in mc["warn"]]
            summary[f"mcmc_{a}"].update(ordinary_med_dlog_vs_warn=float(np.median(d)), ordinary_max_abs_dlog_vs_warn=float(np.max(np.abs(d))), ordinary_med_dchi2_vs_warn=float(np.median(dc)))
        say(f"- {a}: runaways with the chain started at the wall (step-0 Bnw > 3): {summary[f'mcmc_{a}']['runaway_at_wall']}/{len(rr)}; below the 1 m⁻¹ gate: {summary[f'mcmc_{a}']['runaway_below_gate']}/{len(rr)}"
            + (f"; ordinary Δlog10 b_bp vs warn median {summary[f'mcmc_{a}']['ordinary_med_dlog_vs_warn']:+.3f} (max |Δ| {summary[f'mcmc_{a}']['ordinary_max_abs_dlog_vs_warn']:.3f}), Δχ² median {summary[f'mcmc_{a}']['ordinary_med_dchi2_vs_warn']:+.3f}" if "ordinary_med_dlog_vs_warn" in summary[f"mcmc_{a}"] else ""))

    # --- profiles ----------------------------------------------------------
    prof = {a: {r["fit_id"]: r for r in res[a]["profile"] if "error" not in r} for a in arms}
    say()
    say("## χ²_red profile versus fixed Bnw (the four report cases)")
    prof_summary = {}
    for fid in sorted(prof[arms[0]], key=lambda f: REPORT_CASES.index((spec_by[f]["wmo"], spec_by[f]["cycle"]))):
        s = spec_by[fid]
        say(f"- **{s['wmo']}/{s['cycle']}**")
        for a in arms:
            r = prof[a].get(fid)
            if r is None:
                continue
            pts = [(p["Bnw"], p["chi2"]) for p in r["profile"] if p["chi2"] is not None]
            b = np.array([p[0] for p in pts])
            c = np.array([p[1] for p in pts])
            phys = c[b < 0]
            wall = c[(b >= 0) & (b <= 2)]
            run = c[b >= 3]
            i_min = int(np.argmin(c))
            d = dict(min_Bnw=float(b[i_min]), min_chi2=float(c[i_min]), phys_min=float(phys.min()) if phys.size else None,
                     wall_max=float(wall.max()) if wall.size else None, wall_argmax_Bnw=float(b[(b >= 0) & (b <= 2)][np.argmax(wall)]) if wall.size else None,
                     runaway_min=float(run.min()) if run.size else None, chi2_at_4p9=float(c[b == 4.9][0]) if np.any(b == 4.9) else None,
                     lm_Bnw=r["Bnw_lm"], lm_chi2=r["chi2_lm"], stored_chi2=r["chi2_stored_median"])
            prof_summary[f"{s['wmo']}/{s['cycle']}:{a}"] = d
            say(f"  - {a}: minimum χ² {d['min_chi2']:.2f} at Bnw {d['min_Bnw']:+.1f}; physical-side min {d['phys_min']:.2f}; wall max {d['wall_max']:.3g} at Bnw {d['wall_argmax_Bnw']:+.1f}; runaway-side min {d['runaway_min']:.2f}, at 4.9: {d['chi2_at_4p9']:.2f}; LM from p0 ends at Bnw {d['lm_Bnw']:+.2f} (χ² {d['lm_chi2']:.2f})")
    summary["profiles"] = prof_summary
    Path(outdir, "summary.json").write_text(json.dumps(summary, indent=1, default=float))
    Path(outdir, "summary.md").write_text("\n".join(lines) + "\n")

    # ------------------------------------------------------------ figures
    plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e1", "grid.linewidth": 0.6})
    # Fig 1: profiles
    fig, axes = plt.subplots(2, 2, figsize=(9, 6.4), sharex=True)
    for ax, fid in zip(axes.ravel(), sorted(prof[arms[0]], key=lambda f: REPORT_CASES.index((spec_by[f]["wmo"], spec_by[f]["cycle"]))), strict=True):
        s = spec_by[fid]
        for a in arms:
            r = prof[a].get(fid)
            if r is None:
                continue
            pts = [(p["Bnw"], p["chi2"]) for p in r["profile"] if p["chi2"] is not None]
            ax.plot([p[0] for p in pts], [p[1] for p in pts], "--" if a == "ztt_iop" else "-", color=ARM_COLOR[a], lw=2 if a != "ztt_iop" else 1.4, marker="o", ms=4 if a != "ztt_iop" else 3, label=a)
            ax.plot([r["Bnw_lm"]], [r["chi2_lm"]], marker="v", color=ARM_COLOR[a], ms=9, mec="white", mew=1, ls="none")
        ax.plot([prof["warn"][fid]["Bnw_stored_median"]], [prof["warn"][fid]["chi2_stored_median"]], marker="^", color="#0b0b0b", ms=8, ls="none", label="stored 2.0 posterior (warn)" if ax is axes[0, 0] else None)
        ax.set_yscale("log")
        ax.set_title(f"{s['wmo']}/{s['cycle']}  (float b_bp(700) {s['float_bbp700']:.1e})", fontsize=9)
        if s["float_bbp700"]:
            ax.axvline(np.log10(s["float_bbp700"] * (700 / 600) ** 1.0), color=GREY, lw=1, ls=":")
    for ax in axes[1]:
        ax.set_xlabel("fixed log₁₀ Bnw  (b_bp at 600 nm, m⁻¹)")
    for ax in axes[:, 0]:
        ax.set_ylabel("reduced χ² (others re-optimised)")
    h, lbl = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, lbl + [], loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("χ² profile vs fixed Bnw under the three forward-model arms (▽ LM from the production p0; dotted: float, β = 1)", y=1.05, fontsize=9)
    fig.tight_layout()
    fig.savefig(figdir / "ztt_profiles.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Fig 2: LM Bnw per arm, runaways and ordinary
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8), sharey=True)
    rng = np.random.default_rng(0)
    for ax, grp in zip(axes, ("runaway", "ordinary"), strict=True):
        for j, a in enumerate(arms):
            vals = np.array([r["Bnw_lm"] for r in lm[a].values() if r["group"] == grp])
            ax.scatter(j + rng.uniform(-0.18, 0.18, vals.size), vals, s=16, color=ARM_COLOR[a], alpha=0.85, edgecolor="white", linewidth=0.5)
            n_run = int(np.sum(vals > RUNAWAY_BNW))
            ax.text(j, 5.6, f"{n_run}/{vals.size}\nBnw > 3", ha="center", va="bottom", fontsize=8, color="#52514e")
        ax.axhline(RUNAWAY_BNW, color=GREY, lw=1, ls="--")
        ax.axhline(-1.0, color=GREY, lw=1, ls=":")
        ax.set_xticks(range(len(arms)))
        ax.set_xticklabels(arms)
        ax.set_title(f"{grp} ({'51' if grp == 'runaway' else '50'} spectra)", fontsize=9)
        ax.set_ylim(-6.5, 7.2)
    axes[0].set_ylabel("LM solution: log₁₀ Bnw")
    axes[0].text(len(arms) - 0.5, -0.85, "2.0.1 ceiling (0.1 m⁻¹)", fontsize=7, color="#52514e", ha="right")
    fig.suptitle("Where the LM warm-start ends from the production initial guess, 2.0 priors (ceiling at 5)", fontsize=9)
    fig.tight_layout()
    fig.savefig(figdir / "ztt_lm_basins.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Fig 3: ordinary deltas vs warn (LM)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    for a in arms:
        if a == "warn":
            continue
        oo = [(lm["warn"][f], lm[a][f]) for f in lm[a] if lm[a][f]["group"] == "ordinary" and f in lm["warn"] and lm[a][f]["lm_success"] and lm["warn"][f]["lm_success"]]
        x = np.array([np.log10(p["p_lm"]["bbp700"]) for p, _ in oo])
        dl = np.array([np.log10(y["p_lm"]["bbp700"]) - np.log10(p["p_lm"]["bbp700"]) for p, y in oo])
        dc = np.array([y["chi2_lm"] - p["chi2_lm"] for p, y in oo])
        n_fail = sum(1 for f in lm[a] if lm[a][f]["group"] == "ordinary" and not lm[a][f]["lm_success"])
        lbl = a + (f" ({n_fail} LM failure{'s' if n_fail != 1 else ''} not shown)" if n_fail else "")
        axes[0].scatter(x, dl, s=18, color=ARM_COLOR[a], label=lbl, edgecolor="white", linewidth=0.5)
        axes[1].scatter([p["chi2_lm"] for p, _ in oo], dc, s=18, color=ARM_COLOR[a], label=lbl, edgecolor="white", linewidth=0.5)
    axes[0].axhline(0, color=GREY, lw=1)
    axes[1].axhline(0, color=GREY, lw=1)
    axes[0].set_xlabel("log₁₀ b_bp(700) under warn (LM)")
    axes[0].set_ylabel("Δ log₁₀ b_bp(700), arm − warn")
    axes[1].set_xlabel("reduced χ² under warn (LM)")
    axes[1].set_ylabel("Δ reduced χ², arm − warn")
    axes[1].set_xscale("log")
    axes[0].legend(frameon=False)
    fig.suptitle("The 50 ordinary fits: what the policy does where the fit was already physical", fontsize=9)
    fig.tight_layout()
    fig.savefig(figdir / "ztt_ordinary_delta.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    # Fig 4: MCMC b_bp vs float
    if mcmc_rows:
        fig, ax = plt.subplots(figsize=(5.2, 5))
        lo, hi = 1e-4, 1e-1
        ax.plot([lo, hi], [lo, hi], color=GREY, lw=1)
        ax.fill_between([lo, hi], [lo / 2, hi / 2], [lo * 2, hi * 2], color="#e6e5e1", alpha=0.6, lw=0)
        for rec in mcmc_rows:
            if rec["float_bbp700"] is None:
                continue
            for a in arms:
                if f"{a}_bbp700" not in rec:
                    continue
                v = rec[f"{a}_bbp700"]
                xoff = {"warn": 0.93, "ztt": 1.0, "ztt_iop": 1.075}[a]  # so coincident arms stay visible
                ax.errorbar(rec["float_bbp700"] * xoff, v, yerr=[[max(v - rec[f"{a}_lo"], 0)], [max(rec[f"{a}_hi"] - v, 0)]], fmt="o" if rec["group"] == "runaway" else "s",
                            color=ARM_COLOR[a], ms=6 if rec["group"] == "runaway" else 5, mec="white", mew=0.6, elinewidth=0.8, alpha=0.9, capsize=0)
        for a in arms:
            ax.plot([], [], "o", color=ARM_COLOR[a], label=a)
        ax.plot([], [], "o", color="#52514e", label="runaway (8)")
        ax.plot([], [], "s", color="#52514e", label="ordinary (8)")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(lo, hi)
        ax.set_ylim(1e-6, 1e5)
        ax.set_xlabel("float b_bp(700) (m⁻¹)")
        ax.set_ylabel("MCMC posterior median b_bp(700), 2.0 priors (m⁻¹)")
        ax.axhline(1.0, color="#e34948", lw=1, ls="--")
        ax.text(hi * 0.9, 1.5, "1 m⁻¹ gate", color="#e34948", ha="right", fontsize=8)
        ax.legend(frameon=False, fontsize=8, loc="upper left")
        ax.set_title("Full MCMC under each arm vs the float (band: 5–95 %; arms offset ±7 % in x)", fontsize=9)
        fig.tight_layout()
        fig.savefig(figdir / "ztt_mcmc_vs_float.png", dpi=150, bbox_inches="tight")
        plt.close(fig)
    print(f"figures → {figdir}; summary → {outdir / 'summary.md'}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--db", required=True)
    r.add_argument("--chains", required=True)
    r.add_argument("--refit-csv", default=str(Path(__file__).resolve().parents[1] / "high_bbp_outliers" / "refit_51.csv"))
    r.add_argument("--sample-list", required=True, help="the 300 basenames of the Outliers-1 sample (chains_sample.txt)")
    r.add_argument("--outdir", required=True)
    r.add_argument("--jobs", type=int, default=8)
    r.add_argument("--arms", default=",".join(ARMS))
    r.add_argument("--lm-only", action="store_true")
    a = sub.add_parser("analyze")
    a.add_argument("--outdir", required=True)
    a.add_argument("--figdir", default=str(Path(__file__).resolve().parent))
    args = ap.parse_args(argv)
    if args.cmd == "run":
        run(args)
    else:
        analyze(args)


if __name__ == "__main__":
    main()

# PAB image for Nautilus: pab + its special-source deps + the sci stack.
# Build from a STAGING context that holds only the five packages (not bing's
# 94 GB of papers/posters). See claude_prompts/nautilus_prompts.md → Container.
#   docker build -f PAB/Dockerfile -t gitlab-registry.nrp-nautilus.io/profx/pab:2.0.0 <staging>
FROM python:3.12

# The five source revisions this image was built from, as a JSON object.
# pab.config.git_shas() reads this and PREFERS it over `git rev-parse`, because
# the image has no .git — without it every fit's provenance records "unknown".
ARG PAB_GIT_SHAS="{}"
ENV PAB_GIT_SHAS=${PAB_GIT_SHAS}
LABEL org.opencontainers.image.revision="${PAB_GIT_SHAS}"

ENV MPLBACKEND=Agg PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1 OS_COLOR=/opt/os_color
RUN pip install --upgrade pip

WORKDIR /opt/src

# ---------------------------------------------------------------------------
# LAYER 1 -- third-party dependencies ONLY, deliberately BEFORE any COPY of our
# own source. This is the ~7.7 GB layer (jax, scipy, matplotlib, healpy, ...).
#
# Until 2026-09-26 the source COPYs sat above a single combined pip install, so
# editing one line of PAB invalidated all 7.7 GB and every rebuild pushed ~2.5 GB
# for what was really a ~175 MB change. The registry also does not resume a
# partial layer, so a stalled push re-sent the whole thing from zero -- that is
# what cost 66 min on :2.0.1 and a restart on :2.0.2 (JXP, Q8a).
#
# Keep this list in sync with the five local packages' requirements. It does NOT
# need to be exhaustive: layer 2 installs the local packages *with* deps, so
# anything missed here is simply installed there instead of being dropped. That
# is why this is not `--no-deps`, which would silently discard the ~25 real
# dependencies bing/setup.py declares.
# ---------------------------------------------------------------------------
# CPU-ONLY torch, installed FIRST and from PyTorch's cpu index (JXP, Q12 -> (2)).
#
# Nothing in PAB or bing imports torch or timm; `bing/setup.py:31` declares
# `timm==0.3.2`, which requires torch, and the default PyPI torch wheel bundles
# the NVIDIA CUDA stack: 1.2 GB torch + 3.2 GB nvidia/ + 0.9 GB triton = ~5.3 GB,
# over half the image -- on a cluster with no GPUs. Installing the cpu build
# first means the later `timm` requirement is already satisfied, so pip never
# reaches for the CUDA wheels.
#
# `--index-url` here replaces PyPI for THIS command only; the general install
# below is a separate `pip install` that still uses PyPI. Keep them separate.
RUN pip install --index-url https://download.pytorch.org/whl/cpu \
      torch torchvision

# `timm==0.3.2` is named here even though nothing imports it, so that its
# closure lands in this cached layer rather than in layer 2 above the source
# COPYs. Measured both ways: without it layer 2 was 6.35 GB (5.27 GB of it this
# closure) and a source edit rebuilt ~7.96 GB; with it, layer 2 is 712 MB and a
# source edit rebuilds ~934 MB -- an 8.5x reduction.
#
# CAVEAT, not established: those builds all shared one PAB_GIT_SHAS value.
# `ARG PAB_GIT_SHAS` is declared above these installs, so its value is part of
# every subsequent RUN's cache key -- a new commit may well invalidate this
# layer anyway, making the 8.5x unachievable in practice. JXP chose to leave it
# (Q14); the two-build test that would settle it is written up there.
RUN pip install \
      numpy scipy pandas xarray pyarrow matplotlib \
      h5netcdf h5py netcdf4 \
      earthaccess "argopy==1.4.0" "erddapy==3.2.1" gsw healpy emcee bokeh boto3 \
      jax flax optax jaxtyping \
      sphinx sphinx-rtd-theme \
      "timm==0.3.2" \
 && python -c "from erddapy.erddapy import _quote_string_constraints; print('erddapy/argopy compat OK')"

# ---------------------------------------------------------------------------
# LAYER 2 -- our own code. COPYs are ordered by how often each changes, least
# first, so editing PAB invalidates as little as possible.
#
# The BING backscatter models init bb_w from a Loisel+2023 Hydrolight run
# (ocpy.hydrolight.loisel23.load_ds(4,0) -> $OS_COLOR/Loisel2023/Hydrolight400.nc).
# Every fit needs it; ship just that one 18 MB file (not the full 19 GB dataset).
# ---------------------------------------------------------------------------
COPY os_color/ /opt/os_color/
COPY remote_sensing/ remote_sensing/
COPY ocpy/ ocpy/
COPY bing/ bing/
COPY retrieve-or-bust/ retrieve-or-bust/
COPY PAB/ PAB/

RUN pip install ./remote_sensing ./ocpy ./bing ./retrieve-or-bust ./PAB \
 && python -c "import pab, bing, ocpy, remote_sensing, robust; print('pab', pab.pab_version)"

# bing/ocpy use find_packages() with no package_data, so `pip install ./pkg`
# drops their data/ dirs (gordon_coefficients, Bricaud tables, adg .mat). Those
# are loaded via resources.files('pkg')/'data'/... at fit time — and ocpy's
# Bricaud table at *import* of bing.models.anw — so copy them into the installed
# packages. Path is discovered from the module (no python-version hardcoding).
RUN python -c "import shutil, os, bing, ocpy; [shutil.copytree(s, os.path.join(os.path.dirname(p.__file__), 'data'), dirs_exist_ok=True) for p, s in [(bing, '/opt/src/bing/bing/data'), (ocpy, '/opt/src/ocpy/ocpy/data')]]" \
 && python -c "import bing.models.anw; import bing.models.bbnw; from importlib import resources; import os; \
[print('data OK', p) for p in [resources.files('bing').joinpath('data','RT','gordon_coefficients_with_G0.csv'), resources.files('bing').joinpath('data','adg','ADG_part_data_fig2_spec.mat')] if os.path.exists(p)]; \
assert all(os.path.exists(p) for p in [resources.files('bing').joinpath('data','RT','gordon_coefficients_with_G0.csv'), resources.files('bing').joinpath('data','adg','ADG_part_data_fig2_spec.mat')]); print('FIT DEPS OK')" \
 && python -c "from ocpy.hydrolight import loisel23; ds=loisel23.load_ds(4,0); print('LOISEL OK', tuple(ds.Lambda.shape))"

# --- 2.0 radiative transfer: robust/JAX ------------------------------------
# Unlike bing/ocpy, retrieve-or-bust DOES declare package_data for its .npz
# files, so `pip install` carries them. Verified here rather than assumed: the
# emulator weights and the Ed table are 8 KB that every 2.0 fit depends on.
#
# The second guard is a REGRESSION TEST, not a smoke test. A stale `robust`
# (< e1f4289, "off nadir") imports fine and returns a number from the forward
# call — it just returns the SAME number at every wavelength, because the
# constant-in-training cos_theta_v/cos_dphi features were divided by a 1e-8
# guard, saturating every tanh. That silently applies a flat -22% bias to Rrs
# at every off-nadir pixel. Asserting the correction VARIES across the band is
# what distinguishes a fixed robust from a broken one.
RUN python -c "from robust.rt import ed; w, tab = ed.load_table(); assert w.size == 81 and w.min() <= 352 and w.max() >= 700, (w.size, w.min(), w.max()); print('ED OK', int(w.min()), int(w.max()), tab.shape)"  && python -c "import warnings, numpy as np; from robust.rt import emulator as E, types as T, conventions as C; em = E.load_default(); w = np.asarray(C.canonical_wave()); n = w.size; iops = T.IOPs(a=np.full((1,n),0.05), bb_w=np.full((1,n),0.002), bb_p=np.full((1,n),0.002)); g = T.Geometry(theta_s=np.array([29.47]), theta_v=np.array([54.58]), dphi=np.array([81.33])); warnings.simplefilter('ignore'); d = np.asarray(em.relative_delta(iops, T.PhaseParams(B_p=np.array([0.012])), g, w)).ravel(); assert d.std() > 1e-3, 'emulator correction is FLAT off-nadir (%.4f) -- stale robust, rebuild from e1f4289 or later' % d[0]; print('ROBUST OK off-nadir delta %.4f..%.4f std %.4f' % (d.min(), d.max(), d.std()))"  && python -c "from pab.fit.run import fit_spectrum, set_inelastic_Ed, reconstruct_rrs; from pab.fit.models import FitConfig; from pab.config import package_versions; pv = package_versions(); assert pv['pab'] == '2.0', pv['pab']; assert pv['robust'] != 'not installed'; c = FitConfig(); assert c.rt_backend == 'robust_hybrid' and c.fit_Bp and c.wave_max == 700.0; print('PAB 2.0 OK', c.rt_backend, c.wave_min, c.wave_max, '| git_sha', pv['git_sha'])"

ENTRYPOINT ["pab"]

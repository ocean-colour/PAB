# PAB image for Nautilus: pab + its special-source deps + the sci stack.
# Build from a STAGING context that holds only the four packages (not bing's
# 94 GB of papers/posters). See claude_prompts/nautilus_prompts.md → Container.
#   docker build -f PAB/Dockerfile -t gitlab-registry.nrp-nautilus.io/profx/pab:1.0 <staging>
FROM python:3.12

ENV MPLBACKEND=Agg PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1 OS_COLOR=/opt/os_color
RUN pip install --upgrade pip

WORKDIR /opt/src
# deps first (PAB depends on them); each is a trimmed local checkout
COPY remote_sensing/ remote_sensing/
COPY ocpy/ ocpy/
COPY bing/ bing/
COPY PAB/ PAB/
# The BING backscatter models init bb_w from a Loisel+2023 Hydrolight run
# (ocpy.hydrolight.loisel23.load_ds(4,0) -> $OS_COLOR/Loisel2023/Hydrolight400.nc).
# Every fit needs it; ship just that one 18 MB file (not the full 19 GB dataset).
COPY os_color/ /opt/os_color/

RUN pip install \
      ./remote_sensing ./ocpy ./bing ./PAB \
      numpy scipy pandas xarray pyarrow matplotlib \
      h5netcdf h5py netcdf4 \
      earthaccess "argopy==1.4.0" "erddapy==3.2.1" gsw healpy emcee bokeh boto3 \
      sphinx sphinx-rtd-theme \
 && python -c "import pab, bing, ocpy, remote_sensing; print('pab', pab.pab_version)" \
 && python -c "from erddapy.erddapy import _quote_string_constraints; print('erddapy/argopy compat OK')"

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

ENTRYPOINT ["pab"]

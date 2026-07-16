# PAB image for Nautilus: pab + its special-source deps + the sci stack.
# Build from a STAGING context that holds only the four packages (not bing's
# 94 GB of papers/posters). See claude_prompts/nautilus_prompts.md → Container.
#   docker build -f PAB/Dockerfile -t gitlab-registry.nrp-nautilus.io/profx/pab:1.0 <staging>
FROM python:3.12

ENV MPLBACKEND=Agg PIP_NO_CACHE_DIR=1 PYTHONUNBUFFERED=1
RUN pip install --upgrade pip

WORKDIR /opt/src
# deps first (PAB depends on them); each is a trimmed local checkout
COPY remote_sensing/ remote_sensing/
COPY ocpy/ ocpy/
COPY bing/ bing/
COPY PAB/ PAB/

RUN pip install \
      ./remote_sensing ./ocpy ./bing ./PAB \
      numpy scipy pandas xarray pyarrow matplotlib \
      h5netcdf h5py netcdf4 \
      earthaccess argopy gsw healpy emcee bokeh boto3 \
      sphinx sphinx-rtd-theme \
 && python -c "import pab, bing, ocpy, remote_sensing; print('pab', pab.pab_version)"

ENTRYPOINT ["pab"]

#!/usr/bin/env bash
# Build + push the PAB image for Nautilus from the LOCAL working trees.
#
# Why a staging context: bing/ is ~94 GB (papers, posters), so `docker build`
# over python/ would ship the lot. We rsync only the four packages (minus
# .git/papers/posters/caches) plus the one Loisel Hydrolight file into a ~90 MB
# context, then build from that.
#
#   bash nautilus/build_image.sh                # build only
#   bash nautilus/build_image.sh --push         # build + push :1.0.3 and :latest
#
# Requires `docker login gitlab-registry.nrp-nautilus.io` (deploy token) for
# --push. The image is PUBLIC, so pods need no imagePullSecret.
set -euo pipefail

SRC=${SRC:-/mnt/tank/Oceanography/python}
OS_COLOR_SRC=${OS_COLOR:-/home/xavier/Oceanography/data/Color}
IMAGE=${IMAGE:-gitlab-registry.nrp-nautilus.io/profx/pab}
TAG=${TAG:-1.0.3}
STAGE=${STAGE:-/tmp/pab_build_ctx}

echo "== staging build context in $STAGE (from $SRC)"
rm -rf "$STAGE"
mkdir -p "$STAGE"
for pkg in remote_sensing ocpy bing PAB; do
  rsync -a --delete \
    --exclude '.git' --exclude 'papers' --exclude 'posters' \
    --exclude '__pycache__' --exclude '*.egg-info' --exclude '.pytest_cache' \
    --exclude 'report_site/_build' \
    "$SRC/$pkg/" "$STAGE/$pkg/"
done
# the single Loisel+2023 Hydrolight file every bbnw model needs (not the 19 GB set)
mkdir -p "$STAGE/os_color/Loisel2023"
cp "$OS_COLOR_SRC/Loisel2023/Hydrolight400.nc" "$STAGE/os_color/Loisel2023/"
du -sh "$STAGE"

echo "== building $IMAGE:$TAG"
docker build -f "$STAGE/PAB/Dockerfile" -t "$IMAGE:$TAG" -t "$IMAGE:latest" "$STAGE"

echo "== smoke test"
docker run --rm "$IMAGE:$TAG" --dry-run
docker run --rm --entrypoint python "$IMAGE:$TAG" -c \
  "from pab.matchup.engine import GranuleIndex, footprint_bbox; \
import pab; print('pab', pab.pab_version, '| spatial candidate filter present')"

if [[ "${1:-}" == "--push" ]]; then
  echo "== pushing"
  docker push "$IMAGE:$TAG"
  docker push "$IMAGE:latest"
  docker manifest inspect "$IMAGE:$TAG" >/dev/null && echo "push OK: $IMAGE:$TAG"
fi

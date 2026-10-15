#!/usr/bin/env bash
# Build + push the PAB image for Nautilus from the LOCAL working trees.
#
# Why a staging context: bing/ is ~94 GB (papers, posters), so `docker build`
# over python/ would ship the lot. We rsync only the five packages (minus
# .git/papers/posters/caches) plus the one Loisel Hydrolight file into a ~90 MB
# context, then build from that.
#
#   bash nautilus/build_image.sh                # build only
#   bash nautilus/build_image.sh --push         # build + push :2.0.0 and :latest
#
# Requires `docker login gitlab-registry.nrp-nautilus.io` (deploy token) for
# --push. The image is PUBLIC, so pods need no imagePullSecret.
set -euo pipefail

SRC=${SRC:-/mnt/tank/Oceanography/python}
OS_COLOR_SRC=${OS_COLOR:-/home/xavier/Oceanography/data/Color}
IMAGE=${IMAGE:-gitlab-registry.nrp-nautilus.io/profx/pab}
TAG=${TAG:-2.0.0}
STAGE=${STAGE:-/tmp/pab_build_ctx}

echo "== staging build context in $STAGE (from $SRC)"
rm -rf "$STAGE"
mkdir -p "$STAGE"
# retrieve-or-bust carries the 2.0 radiative transfer. Its rt/files/*.npz
# (emulator weights) and rt/data/*.npz (the Ed table every 2.0 fit reads) are
# runtime-critical and MUST NOT be excluded; its context/ (16 MB) and
# notebooks/ are what is worth dropping.
for pkg in remote_sensing ocpy bing retrieve-or-bust PAB; do
  rsync -a --delete \
    --exclude '.git' --exclude 'papers' --exclude 'posters' \
    --exclude '__pycache__' --exclude '*.egg-info' --exclude '.pytest_cache' \
    --exclude 'report_site/_build' \
    --exclude 'notebooks' --exclude 'context' --exclude 'reports' \
    "$SRC/$pkg/" "$STAGE/$pkg/"
done

# The emulator fix (e1f4289 "off nadir") is what keeps robust_hybrid from
# applying a silent flat -22% bias to Rrs off-nadir. Fail here rather than ship
# an image whose fits are quietly wrong; the Dockerfile re-checks behaviourally.
test -f "$STAGE/retrieve-or-bust/robust/rt/files/emulator_l23.npz" \
  || { echo "FATAL: emulator weights missing from the staged context"; exit 1; }
test -f "$STAGE/retrieve-or-bust/robust/rt/data/ed_l23.npz" \
  || { echo "FATAL: Ed table missing from the staged context"; exit 1; }
grep -q 'std > _STD_FLOOR' "$STAGE/retrieve-or-bust/robust/rt/emulator.py" \
  || { echo "FATAL: staged robust predates e1f4289 (off-nadir standardisation fix)"; exit 1; }
echo "== staged robust: weights + Ed table present, off-nadir fix present"

# bing/setup.py pins `retrieve-or-bust @ git+...@cdom-rt`. That branch was
# merged (PR #21) and deleted, so pip now dies with
#   error: pathspec 'cdom-rt' did not match any file(s) known to git
# The requirement is redundant here anyway — retrieve-or-bust is installed from
# the staged source in the same pip command — so drop it from the STAGED copy
# only. The live bing/setup.py is left alone: that pin exists for ReadTheDocs,
# where there is no local checkout, and re-pointing it is bing's own call
# (its comment already says "re-point or drop the @cdom-rt once robust/rt
# merges to main"). Dropping only this line keeps bing's other ~25 deps
# resolving normally, which a blanket --no-deps would not.
if grep -q 'retrieve-or-bust @ git+' "$STAGE/bing/setup.py"; then
  sed -i "/retrieve-or-bust @ git+/d" "$STAGE/bing/setup.py"
  echo "== staged bing: dropped the stale @cdom-rt direct reference"
else
  echo "== staged bing: no @cdom-rt pin found (already re-pointed upstream?)"
fi
# the single Loisel+2023 Hydrolight file every bbnw model needs (not the 19 GB set)
mkdir -p "$STAGE/os_color/Loisel2023"
cp "$OS_COLOR_SRC/Loisel2023/Hydrolight400.nc" "$STAGE/os_color/Loisel2023/"
du -sh "$STAGE"

# The five source revisions, read from the live checkouts and baked into the
# image as PAB_GIT_SHAS. pab.config.git_shas() prefers this over `git rev-parse`
# precisely because the image has no .git — without it every fit's provenance
# records "unknown" for all five.
SHAS=$(cd "$SRC" && python - <<'PY'
import json, subprocess
repos = {"PAB": "PAB", "bing": "bing", "ocpy": "ocpy",
         "remote_sensing": "remote_sensing", "retrieve-or-bust": "retrieve-or-bust"}
out = {}
for name, d in repos.items():
    try:
        out[name] = subprocess.run(["git", "-C", d, "rev-parse", "--short", "HEAD"],
                                   capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        out[name] = "unknown"
print(json.dumps(out, separators=(",", ":")))
PY
)
echo "== baking PAB_GIT_SHAS=$SHAS"
case "$SHAS" in *unknown*) echo "WARNING: at least one SHA is unknown";; esac

echo "== building $IMAGE:$TAG"
docker build -f "$STAGE/PAB/Dockerfile" \
  --build-arg "PAB_GIT_SHAS=$SHAS" \
  -t "$IMAGE:$TAG" -t "$IMAGE:latest" "$STAGE"

echo "== smoke test"
docker run --rm "$IMAGE:$TAG" --dry-run
docker run --rm --entrypoint python "$IMAGE:$TAG" -c \
  "from pab.matchup.engine import GranuleIndex, footprint_bbox; \
import pab; print('pab', pab.pab_version, '| spatial candidate filter present')"
# 2.0: the provenance SHAs must have survived into the running process, and the
# geometry stage must be in the default stage order.
docker run --rm --entrypoint python "$IMAGE:$TAG" -c \
  "from pab.config import package_versions; from pab.pipeline import STAGES; \
pv = package_versions(); shas = pv['git_sha']; \
assert all(v != 'unknown' for v in shas.values()), shas; \
assert 'geometry' in STAGES and STAGES.index('match') < STAGES.index('geometry') < STAGES.index('fit'); \
print('PROVENANCE OK', shas); print('STAGES OK', STAGES)"

if [[ "${1:-}" == "--push" ]]; then
  echo "== pushing"
  docker push "$IMAGE:$TAG"
  docker push "$IMAGE:latest"
  docker manifest inspect "$IMAGE:$TAG" >/dev/null && echo "push OK: $IMAGE:$TAG"
fi

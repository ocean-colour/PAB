# Source this (bash or zsh) to run the OCSSW tools (l2gen, getanc, ...):
#
#     source papers/bbp/py/ocssw_env.sh
#     l2gen --version        # msl12 10.3.0-V2026.4
#
# It changes nothing permanently: only the current shell's environment.
#
# OCSSW lives in $OS_COLOR/ocssw (tag V2026.4, macosx_arm64 binaries).
# The NASA binaries are linked against XQuartz (/opt/X11/lib/libSM, libICE,
# libX11, libXext), which is not installed on this Mac. The four libraries are
# supplied instead by a small conda prefix, $OS_COLOR/ocssw_x11, found through
# DYLD_FALLBACK_LIBRARY_PATH. If XQuartz is ever installed, that line is
# harmless (the /opt/X11 paths resolve first).
#
# See papers/bbp/prompts/scrutinize.md, Q&A/Atmospheric Corrections 2.

: "${OS_COLOR:?OS_COLOR must be set (the folder holding ocssw/)}"

export OCSSWROOT="${OS_COLOR%/}/ocssw"
OCSSW_X11="${OS_COLOR%/}/ocssw_x11"

source "$OCSSWROOT/OCSSW_bash.env"
export DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:+$DYLD_FALLBACK_LIBRARY_PATH:}$OCSSW_X11/lib"

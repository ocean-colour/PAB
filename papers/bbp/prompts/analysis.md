# Analysis for the paper

## Goals

Examine, discuss the analysis methods used in the paper.

## Prompts

### RT

1.  For the v2 PAB analysis, we adopted the `robust_hybrid` RT model from the RoB repository (`Oceanography/python/retrieve-or-bust`).  As I understand it, the 
packaged emulator was trained at nadir view and zero relative azimuth, 
while the pixels fitted here are viewed at θ_v 13–60°.  
# LaTeX for the paper

## Goals

Deal with LaTeX for our paper.

## Context

- `paper_allie_2026nov16.docx` is a Google Doc saved as .docx which is our current draft of the paper.  It is in the folder above this one.
- `Projects/Overleaf/pace_argo_bbp/` is an Overleaf project for the paper.  The main manuscript file is named `pace_argo_bbp.tex`.  You will see that it uses the EGU Copernicus template.

## Prompts

### Word to LaTeX

1.  I am going to ask you to convert the Google Doc to LaTeX respecing the Copernicus template.  We will ignore any Figures or Tables.  
Before doing so, review the files under Context/ and ask
me any questions that you the Q&A/Conversion section below. 
Use Opus 5.5.  Log your work.

2. I have answered the first round of questions in the Q&A/Conversion section below.  Please continue with the conversion.  Do not write the LateX file yet.
Use Opus 5.5.  Log your work.


## Q&A

### Conversion

Questions from Claude after reviewing `paper_allie_2026nov16.docx` and
`~/Projects/Overleaf/pace_argo_bbp/pace_argo_bbp.tex` (2026-11-16).
Each has a proposed default in **[brackets]**. Answer inline (A: ...).

**Template / front matter**

1. **Journal.** The template still has `\documentclass[journal abbreviation, manuscript]{copernicus}`.
   Which journal: Ocean Science (`os`), Biogeosciences (`bg`), or EGUsphere-only (`egusphere`)?
   **[`os`, `manuscript` option]**
   >A: `bg`

2. **Title, authors, affiliations, corresponding email.** The docx has none of these
   (it starts at "ABSTRACT"). Please give them (and author order), or should I leave
   `TEXT` placeholders? Also `\runningtitle` / `\runningauthor`.
   **[placeholders]**
   >A: `TEXT` placeholders for Title;  Authors = Allison James, J. Xavier Prochaska; Affiliation = UC Santa Cruz; email = jxp@ucsc.edu

3. **Where to write.** Overwrite `pace_argo_bbp.tex` in place in the Overleaf repo
   (keeping the template's trailing comment blocks), or write a new file?
   I will not commit/push either way.
   **[overwrite in place; strip the unused template comment blocks at the end]**
   >A: overwrite in place; strip the unused template comment blocks at the end

**References**

4. **BibTeX vs. `thebibliography`.** Create `pace_argo_bbp.bib` and use
   `\bibliographystyle{copernicus}` + `\citet/\citep`, or a hand-written
   `thebibliography`?  **[.bib file]**
   >A: Yes, create a .bib file

5. **Citation/reference mismatches.** How should I handle these?
   **[fix the obvious ones; flag the rest with `% TODO` comments]**
   - Text cites "Prochaska et al., 2025" (twice) but the reference list has
     Prochaska & Frouin (2025, EGUsphere preprint). Same paper? Is there a newer
     BING paper (e.g., the inelastic/fluorescence version) that should be cited instead?
   - "Biogeochemical-Argo Planning Group, 2016" is cited but not in the reference list.
     I can add the standard entry (doi:10.13155/46601) — OK?
   - "NOAA National Ocean Service, 2024" is a web page; Copernicus prefers
     peer-reviewed sources. Keep as a URL reference, or replace?
   - Johnson et al. (2024, SOCCOM/GO-BGC snapshot) and Roesler et al. (2017) are in
     the reference list but never cited. Drop, or keep (e.g., cite Johnson 2024 in
     Data availability)?
   - Stramski et al. (2004) and Mobley (1994) lack DOIs — OK if I add them?
   >A: (i) There is a final, published version of Prochaska & Frouin (2025) in EGUsphere.  We should use that. (ii) OK (iii) Mark as TODO (iv) Drop, but add to the .bib file (v) OK, add them

**Figures and tables**

6. You said to ignore figures. The text refers to Figs. 1–17 by number. Options:
   (a) drop captions entirely and leave the text's "Figure N" as hard-coded text;
   (b) keep each caption in a `figure` environment with a `\label{fig:...}` but no
   `\includegraphics` (placeholder), and convert in-text references to `\ref`;
   (c) keep captions only as `%` comments.
   **[(b) — preserves captions and gives working cross-references for later]**
   >A: (b)

**Notation and math**

7. **Symbol for backscattering.** The docx mixes bb,p₇₀₀, b_bp₇₀₀, bbp₇₀₀, bbp,700.
   I propose macros: `\bbp` → $b_{\mathrm{bp}}$, `\bbpsev` → $b_{\mathrm{bp}}(700)$,
   `\Rrs` → $R_{\mathrm{rs}}(\lambda)$, consistent with IUPAC/Copernicus style
   (roman subscripts). Prefer $b_{\mathrm{b,p}}$ instead of $b_{\mathrm{bp}}$?
   **[$b_{\mathrm{bp}}$]**
   >A: Yes, use macros.  And use $b_{\mathrm{b,p}}$ instead of $b_{\mathrm{bp}}$

8. **Equations.** The Δ/δ definitions are an embedded image in the docx; I will
   typeset them as a numbered `align` (Eqs. 1–2). The GIOP extrapolation
   ($b_{\rm bp}(700)=b_{\rm bp}(442)\,(442/700)^{\eta}$) and the Graff et al. (2015)
   relation will also become numbered equations. OK?  **[yes]**
   >A: yes

**Content issues noticed (conversion only, or fix?)**

9. Should I transcribe the text faithfully, or correct inconsistencies while converting?
   **[transcribe faithfully, but mark each issue with a `% TODO:` comment in the .tex]**
   Issues spotted:
   - Matchup counts differ: 13,971 (abstract, outliers), 14,610 (Methods, Figs. 3–4),
     13,563 (Results, Fig. 2), 13,965 (GIOP comparison), 13,401 (Fig. 14).
   - δ is defined normalised by PACE, then re-defined normalised by Argo
     (Results para "To better isolate…"); the Discussion quotes ρ = 0.53, p = 0.007
     for the Argo relation, mixing values from the two definitions (text says ρ = 0.13,
     p = 0.007). The Fig. 8 caption's ρ values also don't match the text.
   - "Scatter comparisons in Figure 5" should likely be Figure 6.
   - GIOP exponent written as "n" in Methods and "η" in Results; the GIOP
     description appears in both Methods and Results (duplicate).
   - Seasonal-cycle overall median δ = +0.37 (Fig. 11) vs. 0.36 elsewhere.
   - Mixed-layer mean (Methods) vs. "surface-layer median over the upper 25 m"
     (Discussion).
   - Fig. 9 caption contains stray quoted text ("Based on the run1k subsample…").
   - Discussion and Conclusions each repeat the float-drift (20% vs 36%) argument.
   - "Hydrolight" → "HydroLight" (trademark spelling)?
   >A: Transcribe faithfully, but mark each issue with a `% TODO:` comment in the .tex

10. **Section structure.** Map ABSTRACT→`abstract`, INTRODUCTION→`\introduction`,
    METHODS AND DATA→`\section{Data and methods}` with subsections (Argo dataset,
    NASA PACE, Statistical metrics, Inelastic processes), RESULTS→`\section{Results}`,
    DISCUSSION→`\section{Discussion}`, CONCLUSION→`\conclusions`. Results currently has
    no subsections — add some (e.g., Matchup statistics; Bias structure; Inelastic
    processes; BING vs. GIOP; Reverse-bias outliers), or keep flat?
    **[keep flat; add subsections only if you want]**
    >A: That is a good mapping; keep Results flat for now

11. **Back matter.** Code/data availability (point to the PAB GitHub repo, argopy/GDAC,
    NASA Earthdata?), author contributions, competing interests ("The authors declare
    that they have no conflict of interest."), acknowledgements (funding, Argo
    acknowledgement statement). Provide text, or leave placeholders with suggested
    wording?  **[suggested wording + placeholders]**
    >A: suggested wording + placeholders

### Conversion plan (prompt #2, 2026-11-16)

Everything below is decided; `pace_argo_bbp.tex` has **not** been written yet.
`pace_argo_bbp.bib` **has** been created in the Overleaf directory (see Logs).

**Preamble / front matter**
- `\documentclass[bg, manuscript]{copernicus}`
- Macros (preamble):
  - `\newcommand{\bbp}{b_{\mathrm{b,p}}}` (math-mode)
  - `\newcommand{\bbpsev}{\ensuremath{b_{\mathrm{b,p}}(700)}}`
  - `\newcommand{\Rrs}{\ensuremath{R_{\mathrm{rs}}(\lambda)}}`
  - `\newcommand{\Rrssev}{\ensuremath{R_{\mathrm{rs}}(700)}}`
  - also `\aph` → $a_{\mathrm{ph}}(\lambda)$, `\acdom` → $a_{\mathrm{CDOM}}(\lambda)$,
    `\anw` → $a_{\mathrm{nw}}(\lambda)$, `\bbnw` → $b_{\mathrm{b,nw}}(\lambda)$,
    `\Cphyto` → $C_{\mathrm{phyto}}$
  - All variants in the docx (bb,p₇₀₀, b_bp₇₀₀, bbp₇₀₀, bbp,700, bb,p(λ)) map to
    `\bbpsev` or `$\bbp(\lambda)$`.
- `\title{TEXT}` (`% TODO: title`); `\runningtitle{TEXT}`; `\runningauthor{A. James and J. X. Prochaska}`
- `\Author[1]{Allison}{James}`, `\Author[1][jxp@ucsc.edu]{J. Xavier}{Prochaska}`
  (Prochaska is the corresponding author; author order as given)
- `\affil[1]{University of California, Santa Cruz, Santa Cruz, CA, USA}`
  (`% TODO: department`)
- Template dates (`\received` etc.) kept empty; `\copyrightstatement` removed.

**Section map** (Results kept flat)

| docx | LaTeX |
|---|---|
| ABSTRACT | `abstract` env. |
| INTRODUCTION | `\introduction` |
| METHODS AND DATA | `\section{Data and methods}` |
| Argo Dataset | `\subsection{BGC-Argo dataset}` |
| NASA PACE | `\subsection{NASA PACE}` (incl. BING + GIOP paragraphs) |
| Statistical metrics | `\subsection{Statistical metrics}` |
| Inelastic processes | `\subsection{Inelastic processes}`; Raman/fluorescence bullets → `itemize` |
| RESULTS | `\section{Results}` |
| DISCUSSION | `\section{Discussion}` |
| CONCLUSION | `\conclusions` |
| references | `\bibliographystyle{copernicus}` + `\bibliography{pace_argo_bbp}` |

**Equations** (numbered, labelled)
- `eq:delta` — `align` with Δ$\bbp$ = $\bbp^{\rm PACE}-\bbp^{\rm Argo}$ and
  δ = ($\bbp^{\rm PACE}-\bbp^{\rm Argo}$)/$\bbp^{\rm PACE}$ (from docx image4.png)
- `eq:giop` — $\bbp(700)=\bbp(442)\,(442/700)^{\eta}$
- `eq:graff` — $C_{\rm phyto} = 12\,128\,\bbp + 0.59$ ($R^2=0.69$)
- The Argo-normalised re-definition of δ (Results) stays inline text, with a TODO.

**Citations** (text → key; `\citep` in parentheses, `\citet` in running text)

| docx | key |
|---|---|
| Behrenfeld et al., 2005 | `behrenfeld2005` |
| Biogeochemical-Argo Planning Group, 2016 | `bgcargo2016` (added) |
| Claustre et al., 2020 | `claustre2020` |
| Erickson et al., 2019 | `erickson2019` |
| Flombaum et al., 2020 | `flombaum2020` |
| Graff et al., 2015 | `graff2015` |
| Johnson et al., 2017 | `johnson2017` |
| Loisel et al., 2023 | `loisel2023` |
| Mobley, 1994 | `mobley1994` |
| NOAA National Ocean Service, 2024 | `noaa2024` (`% TODO` replace with peer-reviewed source) |
| Prochaska et al., 2025 | `prochaska2025` → final BG paper, so renders "Prochaska and Frouin (2025)" |
| Serra-Pompei et al., 2023 | `serrapompei2023` |
| Stramski et al., 2004 | `stramski2004` |
| Werdell et al., 2018 / 2019 | `werdell2018` / `werdell2019` |
| Westberry et al., 2013 | `westberry2013` |
| (uncited, in .bib only) | `johnson2024`, `roesler2017` |

**Figures** — 17 `figure` environments, caption + `\label`, no `\includegraphics`
(`% TODO: add graphic`), placed after first mention. In-text "Figure N" →
`Fig.~\ref{...}` (Copernicus style: "Fig." mid-sentence, "Figure" at sentence start).

| # | label | content |
|---|---|---|
| 1 | `fig:bing_example` | BING inversion example, float 6903825-405 |
| 2 | `fig:map_delta` | global map coloured by δ |
| 3 | `fig:dist_hist` | separation-distance distribution |
| 4 | `fig:map_dt` | map coloured by Δt, circles/triangles by distance |
| 5 | `fig:map_strict` | strict (≤1 km, ≤3 h) map |
| 6 | `fig:scatter` | PACE vs Argo scatter |
| 7 | `fig:delta_vs_bbp` | δ vs PACE and Argo $\bbp$ |
| 8 | `fig:delta_argo_norm` | Argo-normalised δ |
| 9 | `fig:rrs700_bbp` | $R_{\rm rs}(700)$ vs $\bbp$ |
| 10 | `fig:rrs700_delta` | BING $R_{\rm rs}(700)$ vs δ by date |
| 11 | `fig:seasonal` | monthly median δ by hemisphere |
| 12 | `fig:hydrolight` | HydroLight Raman/fluorescence |
| 13 | `fig:flh` | FLH vs δ |
| 14 | `fig:giop_map` | GIOP map |
| 15 | `fig:giop_strict` | GIOP strict map |
| 16 | `fig:bing_giop` | BING vs GIOP comparison |
| 17 | `fig:outliers` | reverse-bias case study |

**`% TODO:` comments to place in the .tex** (text transcribed as is)
1. Matchup counts: 13,971 / 14,610 / 13,563 / 13,965 / 13,401 (abstract, Sect. 2.1, Results, Fig. 2–4, 14, 16, outliers).
2. "Scatter comparisons in Figure 5" → should be Fig. 6 (`\ref` will point to `fig:map_strict` as written, flagged).
3. Argo-normalised δ re-definition: Discussion quotes ρ = 0.53, p = 0.007 (mixes ρ from PACE relation with p from Argo relation); Fig. 8 caption ρ values don't match text; Fig. 8 caption truncated ("grows larger at higher").
4. Discussion "scaling of δ with PACE b_bp700 (ρ = 0.36)" — which δ definition?
5. GIOP exponent "n" vs η; GIOP method described twice (Methods and Results).
6. Overall median δ +0.37 (Fig. 11) vs 0.36.
7. Mixed-layer mean (Methods) vs "surface-layer median over the upper 25 m" (Discussion).
8. Fig. 9 caption stray quoted text ("Based on the run1k subsample…"); Fig. 13 caption ends "Based on the run1k subsample" — n missing.
9. Float-drift argument (20% vs 36%) repeated in Discussion (×2) and Conclusions.
10. Sensor drift sentence: "would not be expected to produce such a low bias" — wording unclear.
11. Conclusions say BING "now models … Raman scattering explicitly" whereas Results say Raman "is already accounted for" — consistent? Also "BING amplifies … 3–4×" (δ 0.36 vs 0.10) is a claim not shown elsewhere.
12. "Hydrolight" → "HydroLight" spelling (left as is).
13. Methods: "after waiting 9 days ascends" — park time varies by float; check.
14. PACE processing version "v3.1" mentioned only in the Discussion — move to Methods?
15. NOAA web citation (see above); Flombaum et al. (2020) cited for sparse in situ sampling — check it supports that.
16. Draft's "Prochaska et al., 2025" → now cites Prochaska & Frouin (2025, BG); is a separate BING-with-inelastic-processes reference needed for the "version of BING used here"?

**Back matter** (suggested wording, `TEXT`/TODO where unknown)
- `\codedataavailability{}`: BGC-Argo data from the Argo GDAC via argopy
  (Argo, 2000, doi:10.17882/42182 — `% TODO` add to .bib if kept); PACE OCI L2 AOP/IOP
  products from NASA OB.DAAC via earthaccess (`% TODO` product DOIs/version); matchup
  code at the PAB GitHub repository (`% TODO` URL + Zenodo DOI); BING at
  `% TODO` URL.
- `\authorcontribution{}`: "AJ performed the matchup analysis and wrote the
  manuscript draft. JXP conceived the study, developed the BING software, and
  edited the manuscript." (`% TODO` confirm)
- `\competinginterests{}`: "The authors declare that they have no conflict of interest."
- `acknowledgements`: standard Argo acknowledgement ("These data were collected and
  made freely available by the International Argo Program and the national
  programs that contribute to it…"), NASA PACE project, `% TODO` funding.

## Logs

### 2026-11-16 (Review for Word → LaTeX conversion; questions posed)

Executed prompt #1 under "Word to LaTeX" (no conversion yet). Reviewed
`papers/bbp/paper_allie_2026nov16.docx` (extracted with python-docx; pandoc is not
installed) and the Overleaf project `~/Projects/Overleaf/pace_argo_bbp/`
(Copernicus package v7.16; `pace_argo_bbp.tex` is still the unmodified template;
no .bib file; `Figures/` holds one png).

What I learned about the draft:
- 97 paragraphs, all in the "normal" style — headings are plain ALL-CAPS paragraphs,
  so section structure must be inferred. No title/author block, no tables, no native
  Word equations; the Δ/δ definitions are a PNG image (`image4.png`); 19 embedded
  images in total (figures).
- Subscripts are Word run formatting (195 subscript runs) plus Unicode subscript
  digits (₇₀₀), so notation is inconsistent and will need normalising via macros.
- 17 numbered figure captions are inline paragraphs.
- Reference list is mixed-style (APA-like and Copernicus-like); several
  citation/reference mismatches and internal number inconsistencies (listed in
  Q&A/Conversion, item 9).

Posted 11 questions with proposed defaults in Q&A/Conversion. Next step: convert
once answered.

### 2026-11-16 (Conversion plan + BibTeX file; .tex not yet written)

Executed prompt #2 using the answers in Q&A/Conversion. Per the instruction, did
**not** write `pace_argo_bbp.tex`. Did:

- Created `~/Projects/Overleaf/pace_argo_bbp/pace_argo_bbp.bib` (18 entries:
  16 cited + `johnson2024`, `roesler2017` kept uncited). Verified it with
  `bibtex` + `copernicus.bst` on a `\citation{*}` test aux in the scratchpad:
  18 `\bibitem`s and no warnings. Not committed (Overleaf repo untouched otherwise).
- Reference fixes found via web lookup:
  - Prochaska & Frouin (2025): the final version is **Biogeosciences 22, 4705**,
    doi:10.5194/bg-22-4705-2025 (published 17 Sep 2025). Note: it is in BG,
    not EGUsphere (EGUsphere hosted the preprint). End page still TODO.
  - Biogeochemical-Argo Planning Group (2016), Ifremer, doi:10.13155/46601 — added.
  - Stramski et al. (2004) doi:10.1016/j.pocean.2004.07.001 — added.
  - Mobley (1994) *Light and Water* has no DOI — left without one.
  - Erickson et al. (2019): the draft's pages (1766–1774) are wrong; the correct
    pages are 46(3), 1571–1579, and the full author list is now in the .bib.
  - Johnson et al. (2024) SOCCOM snapshot: author list unconfirmed (TODO in .bib).
- Wrote a full "Conversion plan" in Q&A: preamble/macros (`\bbp` = $b_{\rm b,p}$),
  front matter (bg, James & Prochaska, UCSC), section map, equation labels,
  citation-key map, 17 figure labels, 16 `% TODO` items to place in the .tex,
  and suggested back-matter wording.

Next step: write `pace_argo_bbp.tex` from the plan (prompt #3).
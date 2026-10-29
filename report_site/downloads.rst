Downloads
=========


.. raw:: html

   <ul>
   <li><a href="https://s3-west.nrp-nautilus.io/pab/v2/matchup_summary.csv">Matchup summary (CSV)</a></li>
   <li><a href="https://s3-west.nrp-nautilus.io/pab/v2/matchup_summary.parquet">Matchup summary (Parquet)</a></li>
   <li><a href="https://s3-west.nrp-nautilus.io/pab/v2/nasa_giop_summary.csv">BING vs NASA GIOP summary (CSV)</a></li>
   <li><a href="https://s3-west.nrp-nautilus.io/pab/v2/nasa_giop_summary.parquet">BING vs NASA GIOP summary (Parquet)</a></li>
   </ul>

Per-matchup MCMC chains and BING fit figures are published as object-store artifacts (NSF/Nautilus S3), keyed by ``matchup_id`` in the release manifest — available once that backend is activated. The manifest lists the chains and figures of **every** BING version in the database: 15,971 2.0 fits (15,971 chains, 15,971 figures) and 51 2.0.1 re-fits (51 chains, 51 figures); a fit superseded by a patch re-fit of the same matchup and pixel is still listed, with the superseding ``fit_id`` in its ``superseded_by`` field.

Aggregate results
=================


Population statistics binned by region and season, and an equal-area HEALPix spatial aggregation. Per-matchup detail is available through the interactive figures, not as individual pages.

By region
---------

.. raw:: html

   <div id="c33a0c6e-944f-444c-aab1-06a87a2eff1c" data-root-id="p1240" style="display: contents;"></div>
       <script type="text/javascript">
           (function() {
     const fn = function() {
       Bokeh.safely(function() {
         (function(root) {
           function embed_document(root) {
           const docs_json = '{"f266e520-b958-424f-b8c4-9b6478fd918e":{"version":"3.7.2","title":"Bokeh Application","roots":[{"type":"object","name":"DataTable","id":"p1240","attributes":{"width":760,"height":280,"source":{"type":"object","name":"ColumnDataSource","id":"p1210","attributes":{"selected":{"type":"object","name":"Selection","id":"p1211","attributes":{"indices":[],"line_indices":[]}},"selection_policy":{"type":"object","name":"UnionRenderers","id":"p1212"},"data":{"type":"map","entries":[["region",["subtropics"]],["n",[4]],["median_ratio",[2.2220254810242346]],["ratio_iqr_lo",[2.074380715670541]],["ratio_iqr_hi",[2.4606836889176313]],["spearman",[0.39999999999999997]],["log_bias",[0.3572270942058813]],["log_rms",[0.36541947956193765]],["log_mad",[0.04911063057789028]]]}}},"view":{"type":"object","name":"CDSView","id":"p1244","attributes":{"filter":{"type":"object","name":"AllIndices","id":"p1245"}}},"columns":[{"type":"object","name":"TableColumn","id":"p1213","attributes":{"field":"region","title":"region","formatter":{"type":"object","name":"StringFormatter","id":"p1214"},"editor":{"type":"object","name":"StringEditor","id":"p1215"}}},{"type":"object","name":"TableColumn","id":"p1216","attributes":{"field":"n","title":"n","formatter":{"type":"object","name":"StringFormatter","id":"p1217"},"editor":{"type":"object","name":"StringEditor","id":"p1218"}}},{"type":"object","name":"TableColumn","id":"p1219","attributes":{"field":"median_ratio","title":"median_ratio","formatter":{"type":"object","name":"StringFormatter","id":"p1220"},"editor":{"type":"object","name":"StringEditor","id":"p1221"}}},{"type":"object","name":"TableColumn","id":"p1222","attributes":{"field":"ratio_iqr_lo","title":"ratio_iqr_lo","formatter":{"type":"object","name":"StringFormatter","id":"p1223"},"editor":{"type":"object","name":"StringEditor","id":"p1224"}}},{"type":"object","name":"TableColumn","id":"p1225","attributes":{"field":"ratio_iqr_hi","title":"ratio_iqr_hi","formatter":{"type":"object","name":"StringFormatter","id":"p1226"},"editor":{"type":"object","name":"StringEditor","id":"p1227"}}},{"type":"object","name":"TableColumn","id":"p1228","attributes":{"field":"spearman","title":"spearman","formatter":{"type":"object","name":"StringFormatter","id":"p1229"},"editor":{"type":"object","name":"StringEditor","id":"p1230"}}},{"type":"object","name":"TableColumn","id":"p1231","attributes":{"field":"log_bias","title":"log_bias","formatter":{"type":"object","name":"StringFormatter","id":"p1232"},"editor":{"type":"object","name":"StringEditor","id":"p1233"}}},{"type":"object","name":"TableColumn","id":"p1234","attributes":{"field":"log_rms","title":"log_rms","formatter":{"type":"object","name":"StringFormatter","id":"p1235"},"editor":{"type":"object","name":"StringEditor","id":"p1236"}}},{"type":"object","name":"TableColumn","id":"p1237","attributes":{"field":"log_mad","title":"log_mad","formatter":{"type":"object","name":"StringFormatter","id":"p1238"},"editor":{"type":"object","name":"StringEditor","id":"p1239"}}}]}}]}}';
           const render_items = [{"docid":"f266e520-b958-424f-b8c4-9b6478fd918e","roots":{"p1240":"c33a0c6e-944f-444c-aab1-06a87a2eff1c"},"root_ids":["p1240"]}];
           root.Bokeh.embed.embed_items(docs_json, render_items);
           }
           if (root.Bokeh !== undefined) {
             embed_document(root);
           } else {
             let attempts = 0;
             const timer = setInterval(function(root) {
               if (root.Bokeh !== undefined) {
                 clearInterval(timer);
                 embed_document(root);
               } else {
                 attempts++;
                 if (attempts > 100) {
                   clearInterval(timer);
                   console.log("Bokeh: ERROR: Unable to run BokehJS code because BokehJS library is missing");
                 }
               }
             }, 10, root)
           }
         })(window);
       });
     };
     if (document.readyState != "loading") fn();
     else document.addEventListener("DOMContentLoaded", fn);
   })();
       </script>

By season
---------

.. raw:: html

   <div id="f1b96744-35a4-43ac-9528-79866dfc725e" data-root-id="p1276" style="display: contents;"></div>
       <script type="text/javascript">
           (function() {
     const fn = function() {
       Bokeh.safely(function() {
         (function(root) {
           function embed_document(root) {
           const docs_json = '{"b25e1287-9df1-4aa8-a35e-300129c00954":{"version":"3.7.2","title":"Bokeh Application","roots":[{"type":"object","name":"DataTable","id":"p1276","attributes":{"width":760,"height":280,"source":{"type":"object","name":"ColumnDataSource","id":"p1246","attributes":{"selected":{"type":"object","name":"Selection","id":"p1247","attributes":{"indices":[],"line_indices":[]}},"selection_policy":{"type":"object","name":"UnionRenderers","id":"p1248"},"data":{"type":"map","entries":[["season",["DJF","JJA","SON"]],["n",[2,1,1]],["median_ratio",[2.571468478505644,2.2859621901769267,1.823256547067537]],["ratio_iqr_lo",[2.364778625188593,2.2859621901769267,1.823256547067537]],["ratio_iqr_hi",[2.7781583318226946,2.2859621901769267,1.823256547067537]],["spearman",[{"type":"number","value":"nan"},{"type":"number","value":"nan"},{"type":"number","value":"nan"}]],["log_bias",[0.4044957761033208,0.359069042886332,0.26084778173055145]],["log_rms",[0.41058095509912146,0.359069042886332,0.26084778173055145]],["log_mad",[0.07042647090887727,0.0,0.0]]]}}},"view":{"type":"object","name":"CDSView","id":"p1280","attributes":{"filter":{"type":"object","name":"AllIndices","id":"p1281"}}},"columns":[{"type":"object","name":"TableColumn","id":"p1249","attributes":{"field":"season","title":"season","formatter":{"type":"object","name":"StringFormatter","id":"p1250"},"editor":{"type":"object","name":"StringEditor","id":"p1251"}}},{"type":"object","name":"TableColumn","id":"p1252","attributes":{"field":"n","title":"n","formatter":{"type":"object","name":"StringFormatter","id":"p1253"},"editor":{"type":"object","name":"StringEditor","id":"p1254"}}},{"type":"object","name":"TableColumn","id":"p1255","attributes":{"field":"median_ratio","title":"median_ratio","formatter":{"type":"object","name":"StringFormatter","id":"p1256"},"editor":{"type":"object","name":"StringEditor","id":"p1257"}}},{"type":"object","name":"TableColumn","id":"p1258","attributes":{"field":"ratio_iqr_lo","title":"ratio_iqr_lo","formatter":{"type":"object","name":"StringFormatter","id":"p1259"},"editor":{"type":"object","name":"StringEditor","id":"p1260"}}},{"type":"object","name":"TableColumn","id":"p1261","attributes":{"field":"ratio_iqr_hi","title":"ratio_iqr_hi","formatter":{"type":"object","name":"StringFormatter","id":"p1262"},"editor":{"type":"object","name":"StringEditor","id":"p1263"}}},{"type":"object","name":"TableColumn","id":"p1264","attributes":{"field":"spearman","title":"spearman","formatter":{"type":"object","name":"StringFormatter","id":"p1265"},"editor":{"type":"object","name":"StringEditor","id":"p1266"}}},{"type":"object","name":"TableColumn","id":"p1267","attributes":{"field":"log_bias","title":"log_bias","formatter":{"type":"object","name":"StringFormatter","id":"p1268"},"editor":{"type":"object","name":"StringEditor","id":"p1269"}}},{"type":"object","name":"TableColumn","id":"p1270","attributes":{"field":"log_rms","title":"log_rms","formatter":{"type":"object","name":"StringFormatter","id":"p1271"},"editor":{"type":"object","name":"StringEditor","id":"p1272"}}},{"type":"object","name":"TableColumn","id":"p1273","attributes":{"field":"log_mad","title":"log_mad","formatter":{"type":"object","name":"StringFormatter","id":"p1274"},"editor":{"type":"object","name":"StringEditor","id":"p1275"}}}]}}]}}';
           const render_items = [{"docid":"b25e1287-9df1-4aa8-a35e-300129c00954","roots":{"p1276":"f1b96744-35a4-43ac-9528-79866dfc725e"},"root_ids":["p1276"]}];
           root.Bokeh.embed.embed_items(docs_json, render_items);
           }
           if (root.Bokeh !== undefined) {
             embed_document(root);
           } else {
             let attempts = 0;
             const timer = setInterval(function(root) {
               if (root.Bokeh !== undefined) {
                 clearInterval(timer);
                 embed_document(root);
               } else {
                 attempts++;
                 if (attempts > 100) {
                   clearInterval(timer);
                   console.log("Bokeh: ERROR: Unable to run BokehJS code because BokehJS library is missing");
                 }
               }
             }, 10, root)
           }
         })(window);
       });
     };
     if (document.readyState != "loading") fn();
     else document.addEventListener("DOMContentLoaded", fn);
   })();
       </script>

HEALPix cells
-------------

(HEALPix aggregation requires ``healpy`` / ``remote_sensing``)

Matchup quality
---------------


Space/time separation and spectra count per matchup: how close (km) and how near in time (h) the PACE scene was to the float, and how many valid spectra fed the BING fit.

.. raw:: html

   <div id="d80821ff-d905-4e25-989b-5ef2e5f5e400" data-root-id="p1300" style="display: contents;"></div>
       <script type="text/javascript">
           (function() {
     const fn = function() {
       Bokeh.safely(function() {
         (function(root) {
           function embed_document(root) {
           const docs_json = '{"3fe65316-552c-4454-9b23-a7b1dc3e0d14":{"version":"3.7.2","title":"Bokeh Application","roots":[{"type":"object","name":"DataTable","id":"p1300","attributes":{"width":760,"height":280,"source":{"type":"object","name":"ColumnDataSource","id":"p1282","attributes":{"selected":{"type":"object","name":"Selection","id":"p1283","attributes":{"indices":[],"line_indices":[]}},"selection_policy":{"type":"object","name":"UnionRenderers","id":"p1284"},"data":{"type":"map","entries":[["wmo",[7902226,7902226,7902226,7902226]],["cycle",[5,21,27,42]],["distance_km",[0.45363401755565114,0.31878166076202985,0.29346372675796967,0.5806917788962407]],["dtime_hours",[19.557777171111113,13.404861045277778,3.130138495,0.7098616008333334]],["n_spectra",[10,10,10,10]]]}}},"view":{"type":"object","name":"CDSView","id":"p1304","attributes":{"filter":{"type":"object","name":"AllIndices","id":"p1305"}}},"columns":[{"type":"object","name":"TableColumn","id":"p1285","attributes":{"field":"wmo","title":"wmo","formatter":{"type":"object","name":"StringFormatter","id":"p1286"},"editor":{"type":"object","name":"StringEditor","id":"p1287"}}},{"type":"object","name":"TableColumn","id":"p1288","attributes":{"field":"cycle","title":"cycle","formatter":{"type":"object","name":"StringFormatter","id":"p1289"},"editor":{"type":"object","name":"StringEditor","id":"p1290"}}},{"type":"object","name":"TableColumn","id":"p1291","attributes":{"field":"distance_km","title":"distance_km","formatter":{"type":"object","name":"StringFormatter","id":"p1292"},"editor":{"type":"object","name":"StringEditor","id":"p1293"}}},{"type":"object","name":"TableColumn","id":"p1294","attributes":{"field":"dtime_hours","title":"dtime_hours","formatter":{"type":"object","name":"StringFormatter","id":"p1295"},"editor":{"type":"object","name":"StringEditor","id":"p1296"}}},{"type":"object","name":"TableColumn","id":"p1297","attributes":{"field":"n_spectra","title":"n_spectra","formatter":{"type":"object","name":"StringFormatter","id":"p1298"},"editor":{"type":"object","name":"StringEditor","id":"p1299"}}}]}}]}}';
           const render_items = [{"docid":"3fe65316-552c-4454-9b23-a7b1dc3e0d14","roots":{"p1300":"d80821ff-d905-4e25-989b-5ef2e5f5e400"},"root_ids":["p1300"]}];
           root.Bokeh.embed.embed_items(docs_json, render_items);
           }
           if (root.Bokeh !== undefined) {
             embed_document(root);
           } else {
             let attempts = 0;
             const timer = setInterval(function(root) {
               if (root.Bokeh !== undefined) {
                 clearInterval(timer);
                 embed_document(root);
               } else {
                 attempts++;
                 if (attempts > 100) {
                   clearInterval(timer);
                   console.log("Bokeh: ERROR: Unable to run BokehJS code because BokehJS library is missing");
                 }
               }
             }, 10, root)
           }
         })(window);
       });
     };
     if (document.readyState != "loading") fn();
     else document.addEventListener("DOMContentLoaded", fn);
   })();
       </script>

Aggregate results
=================


Population statistics binned by region and season, and an equal-area HEALPix spatial aggregation. Per-matchup detail is available through the interactive figures, not as individual pages.

By region
---------

.. raw:: html

   <div id="d8066a2e-c7c2-4e88-913c-3ef387053117" data-root-id="p1240" style="display: contents;"></div>
       <script type="text/javascript">
           (function() {
     const fn = function() {
       Bokeh.safely(function() {
         (function(root) {
           function embed_document(root) {
           const docs_json = '{"a8dfa746-6c2b-4442-845a-4cdaf82099bd":{"version":"3.7.2","title":"Bokeh Application","roots":[{"type":"object","name":"DataTable","id":"p1240","attributes":{"width":760,"height":280,"source":{"type":"object","name":"ColumnDataSource","id":"p1210","attributes":{"selected":{"type":"object","name":"Selection","id":"p1211","attributes":{"indices":[],"line_indices":[]}},"selection_policy":{"type":"object","name":"UnionRenderers","id":"p1212"},"data":{"type":"map","entries":[["region",["subtropics"]],["n",[4]],["median_ratio",[2.2220254810242346]],["ratio_iqr_lo",[2.074380715670541]],["ratio_iqr_hi",[2.4606836889176313]],["spearman",[0.39999999999999997]],["log_bias",[0.3572270942058813]],["log_rms",[0.36541947956193765]],["log_mad",[0.04911063057789028]]]}}},"view":{"type":"object","name":"CDSView","id":"p1244","attributes":{"filter":{"type":"object","name":"AllIndices","id":"p1245"}}},"columns":[{"type":"object","name":"TableColumn","id":"p1213","attributes":{"field":"region","title":"region","formatter":{"type":"object","name":"StringFormatter","id":"p1214"},"editor":{"type":"object","name":"StringEditor","id":"p1215"}}},{"type":"object","name":"TableColumn","id":"p1216","attributes":{"field":"n","title":"n","formatter":{"type":"object","name":"StringFormatter","id":"p1217"},"editor":{"type":"object","name":"StringEditor","id":"p1218"}}},{"type":"object","name":"TableColumn","id":"p1219","attributes":{"field":"median_ratio","title":"median_ratio","formatter":{"type":"object","name":"StringFormatter","id":"p1220"},"editor":{"type":"object","name":"StringEditor","id":"p1221"}}},{"type":"object","name":"TableColumn","id":"p1222","attributes":{"field":"ratio_iqr_lo","title":"ratio_iqr_lo","formatter":{"type":"object","name":"StringFormatter","id":"p1223"},"editor":{"type":"object","name":"StringEditor","id":"p1224"}}},{"type":"object","name":"TableColumn","id":"p1225","attributes":{"field":"ratio_iqr_hi","title":"ratio_iqr_hi","formatter":{"type":"object","name":"StringFormatter","id":"p1226"},"editor":{"type":"object","name":"StringEditor","id":"p1227"}}},{"type":"object","name":"TableColumn","id":"p1228","attributes":{"field":"spearman","title":"spearman","formatter":{"type":"object","name":"StringFormatter","id":"p1229"},"editor":{"type":"object","name":"StringEditor","id":"p1230"}}},{"type":"object","name":"TableColumn","id":"p1231","attributes":{"field":"log_bias","title":"log_bias","formatter":{"type":"object","name":"StringFormatter","id":"p1232"},"editor":{"type":"object","name":"StringEditor","id":"p1233"}}},{"type":"object","name":"TableColumn","id":"p1234","attributes":{"field":"log_rms","title":"log_rms","formatter":{"type":"object","name":"StringFormatter","id":"p1235"},"editor":{"type":"object","name":"StringEditor","id":"p1236"}}},{"type":"object","name":"TableColumn","id":"p1237","attributes":{"field":"log_mad","title":"log_mad","formatter":{"type":"object","name":"StringFormatter","id":"p1238"},"editor":{"type":"object","name":"StringEditor","id":"p1239"}}}]}}]}}';
           const render_items = [{"docid":"a8dfa746-6c2b-4442-845a-4cdaf82099bd","roots":{"p1240":"d8066a2e-c7c2-4e88-913c-3ef387053117"},"root_ids":["p1240"]}];
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

   <div id="cc27a3a3-2522-4983-8ae5-a93eb2618b0c" data-root-id="p1276" style="display: contents;"></div>
       <script type="text/javascript">
           (function() {
     const fn = function() {
       Bokeh.safely(function() {
         (function(root) {
           function embed_document(root) {
           const docs_json = '{"1880322f-804b-4f82-888a-876912fe580e":{"version":"3.7.2","title":"Bokeh Application","roots":[{"type":"object","name":"DataTable","id":"p1276","attributes":{"width":760,"height":280,"source":{"type":"object","name":"ColumnDataSource","id":"p1246","attributes":{"selected":{"type":"object","name":"Selection","id":"p1247","attributes":{"indices":[],"line_indices":[]}},"selection_policy":{"type":"object","name":"UnionRenderers","id":"p1248"},"data":{"type":"map","entries":[["season",["DJF","JJA","SON"]],["n",[2,1,1]],["median_ratio",[2.571468478505644,2.2859621901769267,1.823256547067537]],["ratio_iqr_lo",[2.364778625188593,2.2859621901769267,1.823256547067537]],["ratio_iqr_hi",[2.7781583318226946,2.2859621901769267,1.823256547067537]],["spearman",[{"type":"number","value":"nan"},{"type":"number","value":"nan"},{"type":"number","value":"nan"}]],["log_bias",[0.4044957761033208,0.359069042886332,0.26084778173055145]],["log_rms",[0.41058095509912146,0.359069042886332,0.26084778173055145]],["log_mad",[0.07042647090887727,0.0,0.0]]]}}},"view":{"type":"object","name":"CDSView","id":"p1280","attributes":{"filter":{"type":"object","name":"AllIndices","id":"p1281"}}},"columns":[{"type":"object","name":"TableColumn","id":"p1249","attributes":{"field":"season","title":"season","formatter":{"type":"object","name":"StringFormatter","id":"p1250"},"editor":{"type":"object","name":"StringEditor","id":"p1251"}}},{"type":"object","name":"TableColumn","id":"p1252","attributes":{"field":"n","title":"n","formatter":{"type":"object","name":"StringFormatter","id":"p1253"},"editor":{"type":"object","name":"StringEditor","id":"p1254"}}},{"type":"object","name":"TableColumn","id":"p1255","attributes":{"field":"median_ratio","title":"median_ratio","formatter":{"type":"object","name":"StringFormatter","id":"p1256"},"editor":{"type":"object","name":"StringEditor","id":"p1257"}}},{"type":"object","name":"TableColumn","id":"p1258","attributes":{"field":"ratio_iqr_lo","title":"ratio_iqr_lo","formatter":{"type":"object","name":"StringFormatter","id":"p1259"},"editor":{"type":"object","name":"StringEditor","id":"p1260"}}},{"type":"object","name":"TableColumn","id":"p1261","attributes":{"field":"ratio_iqr_hi","title":"ratio_iqr_hi","formatter":{"type":"object","name":"StringFormatter","id":"p1262"},"editor":{"type":"object","name":"StringEditor","id":"p1263"}}},{"type":"object","name":"TableColumn","id":"p1264","attributes":{"field":"spearman","title":"spearman","formatter":{"type":"object","name":"StringFormatter","id":"p1265"},"editor":{"type":"object","name":"StringEditor","id":"p1266"}}},{"type":"object","name":"TableColumn","id":"p1267","attributes":{"field":"log_bias","title":"log_bias","formatter":{"type":"object","name":"StringFormatter","id":"p1268"},"editor":{"type":"object","name":"StringEditor","id":"p1269"}}},{"type":"object","name":"TableColumn","id":"p1270","attributes":{"field":"log_rms","title":"log_rms","formatter":{"type":"object","name":"StringFormatter","id":"p1271"},"editor":{"type":"object","name":"StringEditor","id":"p1272"}}},{"type":"object","name":"TableColumn","id":"p1273","attributes":{"field":"log_mad","title":"log_mad","formatter":{"type":"object","name":"StringFormatter","id":"p1274"},"editor":{"type":"object","name":"StringEditor","id":"p1275"}}}]}}]}}';
           const render_items = [{"docid":"1880322f-804b-4f82-888a-876912fe580e","roots":{"p1276":"cc27a3a3-2522-4983-8ae5-a93eb2618b0c"},"root_ids":["p1276"]}];
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

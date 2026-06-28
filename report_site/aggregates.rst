Aggregate results
=================


Population statistics binned by region and season, and an equal-area HEALPix spatial aggregation. Per-matchup detail is available through the interactive figures, not as individual pages.

By region
---------

.. raw:: html

   <div id="beafa624-1129-4f70-bfcf-ddb1795ea7be" data-root-id="p1167" style="display: contents;"></div>
       <script type="text/javascript">
           (function() {
     const fn = function() {
       Bokeh.safely(function() {
         (function(root) {
           function embed_document(root) {
           const docs_json = '{"4d765586-63a8-47c5-bcc2-566387075d7f":{"version":"3.7.2","title":"Bokeh Application","roots":[{"type":"object","name":"DataTable","id":"p1167","attributes":{"width":760,"height":280,"source":{"type":"object","name":"ColumnDataSource","id":"p1137","attributes":{"selected":{"type":"object","name":"Selection","id":"p1138","attributes":{"indices":[],"line_indices":[]}},"selection_policy":{"type":"object","name":"UnionRenderers","id":"p1139"},"data":{"type":"map","entries":[["region",["subtropics"]],["n",[4]],["median_ratio",[2.2220254810242346]],["ratio_iqr_lo",[2.074380715670541]],["ratio_iqr_hi",[2.4606836889176313]],["spearman",[0.39999999999999997]],["log_bias",[0.3572270942058813]],["log_rms",[0.36541947956193765]],["log_mad",[0.04911063057789028]]]}}},"view":{"type":"object","name":"CDSView","id":"p1171","attributes":{"filter":{"type":"object","name":"AllIndices","id":"p1172"}}},"columns":[{"type":"object","name":"TableColumn","id":"p1140","attributes":{"field":"region","title":"region","formatter":{"type":"object","name":"StringFormatter","id":"p1141"},"editor":{"type":"object","name":"StringEditor","id":"p1142"}}},{"type":"object","name":"TableColumn","id":"p1143","attributes":{"field":"n","title":"n","formatter":{"type":"object","name":"StringFormatter","id":"p1144"},"editor":{"type":"object","name":"StringEditor","id":"p1145"}}},{"type":"object","name":"TableColumn","id":"p1146","attributes":{"field":"median_ratio","title":"median_ratio","formatter":{"type":"object","name":"StringFormatter","id":"p1147"},"editor":{"type":"object","name":"StringEditor","id":"p1148"}}},{"type":"object","name":"TableColumn","id":"p1149","attributes":{"field":"ratio_iqr_lo","title":"ratio_iqr_lo","formatter":{"type":"object","name":"StringFormatter","id":"p1150"},"editor":{"type":"object","name":"StringEditor","id":"p1151"}}},{"type":"object","name":"TableColumn","id":"p1152","attributes":{"field":"ratio_iqr_hi","title":"ratio_iqr_hi","formatter":{"type":"object","name":"StringFormatter","id":"p1153"},"editor":{"type":"object","name":"StringEditor","id":"p1154"}}},{"type":"object","name":"TableColumn","id":"p1155","attributes":{"field":"spearman","title":"spearman","formatter":{"type":"object","name":"StringFormatter","id":"p1156"},"editor":{"type":"object","name":"StringEditor","id":"p1157"}}},{"type":"object","name":"TableColumn","id":"p1158","attributes":{"field":"log_bias","title":"log_bias","formatter":{"type":"object","name":"StringFormatter","id":"p1159"},"editor":{"type":"object","name":"StringEditor","id":"p1160"}}},{"type":"object","name":"TableColumn","id":"p1161","attributes":{"field":"log_rms","title":"log_rms","formatter":{"type":"object","name":"StringFormatter","id":"p1162"},"editor":{"type":"object","name":"StringEditor","id":"p1163"}}},{"type":"object","name":"TableColumn","id":"p1164","attributes":{"field":"log_mad","title":"log_mad","formatter":{"type":"object","name":"StringFormatter","id":"p1165"},"editor":{"type":"object","name":"StringEditor","id":"p1166"}}}]}}]}}';
           const render_items = [{"docid":"4d765586-63a8-47c5-bcc2-566387075d7f","roots":{"p1167":"beafa624-1129-4f70-bfcf-ddb1795ea7be"},"root_ids":["p1167"]}];
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

   <div id="cbc11679-0bac-47c0-9d47-32a82779243c" data-root-id="p1203" style="display: contents;"></div>
       <script type="text/javascript">
           (function() {
     const fn = function() {
       Bokeh.safely(function() {
         (function(root) {
           function embed_document(root) {
           const docs_json = '{"4ddfaf4c-ffb3-4aa5-b3a3-b86fb0dec507":{"version":"3.7.2","title":"Bokeh Application","roots":[{"type":"object","name":"DataTable","id":"p1203","attributes":{"width":760,"height":280,"source":{"type":"object","name":"ColumnDataSource","id":"p1173","attributes":{"selected":{"type":"object","name":"Selection","id":"p1174","attributes":{"indices":[],"line_indices":[]}},"selection_policy":{"type":"object","name":"UnionRenderers","id":"p1175"},"data":{"type":"map","entries":[["season",["DJF","JJA","SON"]],["n",[2,1,1]],["median_ratio",[2.571468478505644,2.2859621901769267,1.823256547067537]],["ratio_iqr_lo",[2.364778625188593,2.2859621901769267,1.823256547067537]],["ratio_iqr_hi",[2.7781583318226946,2.2859621901769267,1.823256547067537]],["spearman",[{"type":"number","value":"nan"},{"type":"number","value":"nan"},{"type":"number","value":"nan"}]],["log_bias",[0.4044957761033208,0.359069042886332,0.26084778173055145]],["log_rms",[0.41058095509912146,0.359069042886332,0.26084778173055145]],["log_mad",[0.07042647090887727,0.0,0.0]]]}}},"view":{"type":"object","name":"CDSView","id":"p1207","attributes":{"filter":{"type":"object","name":"AllIndices","id":"p1208"}}},"columns":[{"type":"object","name":"TableColumn","id":"p1176","attributes":{"field":"season","title":"season","formatter":{"type":"object","name":"StringFormatter","id":"p1177"},"editor":{"type":"object","name":"StringEditor","id":"p1178"}}},{"type":"object","name":"TableColumn","id":"p1179","attributes":{"field":"n","title":"n","formatter":{"type":"object","name":"StringFormatter","id":"p1180"},"editor":{"type":"object","name":"StringEditor","id":"p1181"}}},{"type":"object","name":"TableColumn","id":"p1182","attributes":{"field":"median_ratio","title":"median_ratio","formatter":{"type":"object","name":"StringFormatter","id":"p1183"},"editor":{"type":"object","name":"StringEditor","id":"p1184"}}},{"type":"object","name":"TableColumn","id":"p1185","attributes":{"field":"ratio_iqr_lo","title":"ratio_iqr_lo","formatter":{"type":"object","name":"StringFormatter","id":"p1186"},"editor":{"type":"object","name":"StringEditor","id":"p1187"}}},{"type":"object","name":"TableColumn","id":"p1188","attributes":{"field":"ratio_iqr_hi","title":"ratio_iqr_hi","formatter":{"type":"object","name":"StringFormatter","id":"p1189"},"editor":{"type":"object","name":"StringEditor","id":"p1190"}}},{"type":"object","name":"TableColumn","id":"p1191","attributes":{"field":"spearman","title":"spearman","formatter":{"type":"object","name":"StringFormatter","id":"p1192"},"editor":{"type":"object","name":"StringEditor","id":"p1193"}}},{"type":"object","name":"TableColumn","id":"p1194","attributes":{"field":"log_bias","title":"log_bias","formatter":{"type":"object","name":"StringFormatter","id":"p1195"},"editor":{"type":"object","name":"StringEditor","id":"p1196"}}},{"type":"object","name":"TableColumn","id":"p1197","attributes":{"field":"log_rms","title":"log_rms","formatter":{"type":"object","name":"StringFormatter","id":"p1198"},"editor":{"type":"object","name":"StringEditor","id":"p1199"}}},{"type":"object","name":"TableColumn","id":"p1200","attributes":{"field":"log_mad","title":"log_mad","formatter":{"type":"object","name":"StringFormatter","id":"p1201"},"editor":{"type":"object","name":"StringEditor","id":"p1202"}}}]}}]}}';
           const render_items = [{"docid":"4ddfaf4c-ffb3-4aa5-b3a3-b86fb0dec507","roots":{"p1203":"cbc11679-0bac-47c0-9d47-32a82779243c"},"root_ids":["p1203"]}];
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

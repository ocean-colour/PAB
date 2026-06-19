% fig_architecture.m
% Figure 3 for the PAB design document: the storage / reporting architecture.
%
% Draws the flow of PAB outputs from the analysis layer through storage to the
% community-facing reporting channels:
%
%   BING fits ->  SQLite DB (extracted values)         ->  Reporting (readthedocs + Bokeh)
%             ->  Nautilus/NSF S3 (chains + figures)   ->  Reporting + downloads
%             ->  Zenodo snapshot (DOI, pab_version)
%
% Usage (MATLAB):
%   >> run('docs/scripts/fig_architecture.m')
% Writes docs/figures/fig_architecture.png
%
% NOTE: This script was authored on a workstation without MATLAB installed, so
% it has NOT been executed/verified here. Run it in MATLAB to produce the PNG.

function fig_architecture()
    fig = figure('Color', 'w', 'Position', [100 100 900 460]);
    ax = axes('Position', [0 0 1 1]); axis(ax, [0 100 0 100]); axis off; hold on;

    % --- helper for a labelled box ---
    function h = box(x, y, w, h_, label, face)
        rectangle('Position', [x y w h_], 'Curvature', 0.12, ...
            'FaceColor', face, 'EdgeColor', [0.2 0.2 0.2], 'LineWidth', 1.2);
        text(x + w/2, y + h_/2, label, 'HorizontalAlignment', 'center', ...
            'VerticalAlignment', 'middle', 'FontSize', 11, 'Interpreter', 'none');
        h = [x y w h_];
    end

    % --- helper for an arrow between box edges ---
    function arrow(x1, y1, x2, y2)
        annotation('arrow', 'Units', 'normalized', ...
            'Position', normpos(x1, y1, x2 - x1, y2 - y1), ...
            'HeadStyle', 'vback2', 'LineWidth', 1.2, 'Color', [0.3 0.3 0.3]);
    end
    function p = normpos(x, y, dx, dy)
        % data (0..100) -> normalized figure coords for annotation()
        p = [x/100, y/100, dx/100, dy/100];
    end

    blue   = [0.85 0.92 1.00];
    green  = [0.85 0.97 0.86];
    orange = [1.00 0.93 0.80];
    grey   = [0.92 0.92 0.92];

    % Source
    box( 4, 60, 22, 16, sprintf('BING fits\n(per matchup)'), grey);

    % Storage tier
    box(38, 74, 26, 16, sprintf('SQLite DB\nextracted values'), blue);
    box(38, 52, 26, 16, sprintf('Nautilus/NSF S3\nchains + figures'), green);
    box(38, 30, 26, 16, sprintf('Zenodo snapshot\nDOI, pab_version'), orange);

    % Reporting tier
    box(74, 52, 22, 24, sprintf('Reporting\nreadthedocs\n+ Bokeh\n+ downloads'), grey);

    % Arrows: source -> storage
    arrow(26, 70, 38, 82);   % fits -> SQLite
    arrow(26, 66, 38, 60);   % fits -> S3
    arrow(51, 52, 51, 46);   % SQLite/S3 -> Zenodo (downward)

    % storage -> reporting
    arrow(64, 82, 74, 70);   % SQLite -> reporting
    arrow(64, 60, 74, 62);   % S3 -> reporting

    title('PAB storage & reporting architecture', 'FontSize', 13);

    outdir = fullfile(fileparts(mfilename('fullpath')), '..', 'figures');
    if ~exist(outdir, 'dir'); mkdir(outdir); end
    out = fullfile(outdir, 'fig_architecture.png');
    exportgraphics(fig, out, 'Resolution', 110);
    fprintf('Wrote %s\n', out);
end

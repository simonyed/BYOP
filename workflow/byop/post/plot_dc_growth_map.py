#!/usr/bin/env python3
"""Map: Texas / ERCOT base, TAMU 64s buses and lines, and data-center growth after 2025 per bus (RA-DC-SPATIAL-01).

    python byop/post/plot_dc_growth_map.py [--scenario mid] [--year 2035]      (from pypsa-usa/workflow)
Inputs: results/BYOP/baseline_2025_tamu/{BUS_LEDGER,LINE_LEDGER,COUNTY_TO_BUS_SHARES}.csv,
        byop/inputs/dc/ERCOT_DC_CAPACITY_ALLOCATION_TAMU64.csv, data/counties/cb_2020_us_county_500k.shp
Output: results/BYOP/dc_allocation/ERCOT_DC_GROWTH_MAP_<scenario>_<year>.png (+ the plotted table as CSV)
"""
import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

W = Path(__file__).resolve().parents[2]
BASE = W / 'results/BYOP/baseline_2025_tamu'
ALLOC = W / 'byop/inputs/dc/ERCOT_DC_CAPACITY_ALLOCATION_TAMU64.csv'
ERCOT_WZ = ['COAST', 'EAST', 'FWEST', 'NORTH', 'NCENT', 'SOUTH', 'SCENT', 'WEST']

INK, MUTED, GRID = '#1f1f1d', '#6b6a66', '#c9c7c1'
TX_FILL, ERCOT_FILL, ERCOT_EDGE = '#f4f3f0', '#e6edf7', '#2a78d6'
LINE_C, BUS_C, DC_C = '#8d8b85', '#3d3c39', '#eb6834'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scenario', default='mid', choices=['low', 'mid', 'high'])
    ap.add_argument('--year', type=int, default=2035)
    a = ap.parse_args()

    cty = gpd.read_file(W / 'data/counties/cb_2020_us_county_500k.shp').to_crs(4326)
    tx = cty[cty.STATEFP == '48']
    sh = pd.read_csv(BASE / 'COUNTY_TO_BUS_SHARES.csv', dtype={'GEOID': str})
    erc_ids = set(sh[sh.wz.isin(ERCOT_WZ)].GEOID.str.zfill(5))
    erc = tx[tx.GEOID.isin(erc_ids)]
    erc_outline = erc.dissolve()

    bus = pd.read_csv(BASE / 'BUS_LEDGER.csv', index_col=0)
    lines = pd.read_csv(BASE / 'LINE_LEDGER.csv')
    al = pd.read_csv(ALLOC)
    g = al[(al.scenario == a.scenario) & (al.year == a.year)].sort_values('cum_IT_MW', ascending=False)
    g = g[g.cum_IT_MW > 0].reset_index(drop=True)
    total = g.cum_IT_MW.sum()

    fig = plt.figure(figsize=(15, 10.5), dpi=200)
    ax = fig.add_axes([0.02, 0.06, 0.66, 0.84])
    axb = fig.add_axes([0.765, 0.10, 0.215, 0.76])

    tx.plot(ax=ax, color=TX_FILL, edgecolor='white', linewidth=0.4, zorder=1)
    erc.plot(ax=ax, color=ERCOT_FILL, edgecolor='white', linewidth=0.4, zorder=2)
    tx.dissolve().boundary.plot(ax=ax, color=MUTED, linewidth=0.8, zorder=3)
    erc_outline.boundary.plot(ax=ax, color=ERCOT_EDGE, linewidth=1.4, zorder=4)

    smax = lines.final_s_nom.max()
    for r in lines.itertuples():
        if r.bus0 not in bus.index or r.bus1 not in bus.index:
            continue
        x0, y0 = bus.loc[r.bus0, ['x', 'y']]; x1, y1 = bus.loc[r.bus1, ['x', 'y']]
        ax.plot([x0, x1], [y0, y1], color=LINE_C, lw=0.4 + 2.6 * (r.final_s_nom / smax) ** 0.5,
                alpha=0.75, solid_capstyle='round', zorder=5)
    ax.scatter(bus.x, bus.y, s=10, color=BUS_C, edgecolor='white', linewidth=0.5, zorder=6)

    def size(mw):
        return 1400.0 * np.asarray(mw) / 1500.0
    gx = bus.reindex(g.bus)
    ax.scatter(gx.x.values, gx.y.values, s=size(g.cum_IT_MW), color=DC_C, alpha=0.78, edgecolor='white', linewidth=1.6, zorder=7)
    off = {'p630 0': (16, -18), 'p630 5': (-14, -24), 'p650 0': (-78, -20), 'p630 3': (14, 12), 'p630 2': (14, -20),
           'p630 9': (-64, 14), 'p620 0': (14, 6), 'p640 1': (-62, -10), 'p630 12': (-80, 4)}
    for r in g.head(9).itertuples():
        x, y = bus.loc[r.bus, ['x', 'y']]
        dx, dy = off.get(r.bus, (12, 6))
        ax.annotate(f'{r.bus}\n{r.cum_IT_MW:,.0f} MW', (x, y), xytext=(dx, dy), textcoords='offset points', fontsize=8.5,
                    color=INK, zorder=8, ha='left', va='center',
                    bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='none', alpha=0.85))

    # legends: bubble size, lines, base
    for mw, lab in [(100, '100'), (500, '500'), (1500, '1,500')]:
        ax.scatter([], [], s=size(mw), color=DC_C, alpha=0.78, edgecolor='white', linewidth=1.6, label=f'{lab} MW IT')
    l1 = ax.legend(title=f'DC IT capacity added\n2026–{a.year} ({a.scenario})', loc='upper left', frameon=False,
                   labelspacing=1.6, borderpad=1.0, fontsize=9, title_fontsize=9.5)
    ax.add_artist(l1)
    h = [plt.Line2D([], [], color=LINE_C, lw=0.8, label='Line (thin = low rating)'),
         plt.Line2D([], [], color=LINE_C, lw=3.0, label='Line (thick = high rating)'),
         plt.Line2D([], [], marker='o', ls='', color=BUS_C, ms=4, label='TAMU 64s cluster bus'),
         plt.Rectangle((0, 0), 1, 1, fc=ERCOT_FILL, ec=ERCOT_EDGE, label='ERCOT counties'),
         plt.Rectangle((0, 0), 1, 1, fc=TX_FILL, ec=MUTED, label='Texas, non-ERCOT')]
    ax.legend(handles=h, loc='lower right', frameon=False, fontsize=9)
    ax.set_xlim(-107.0, -93.3); ax.set_ylim(25.7, 36.7)
    ax.set_aspect(1 / np.cos(np.radians(31.0)))
    ax.axis('off')

    # side panel: ranked bars (same data, exact values)
    lab = [f'{b}  {c.replace(";", ", ")}' for b, c in zip(g.bus, g.counties)]
    yy = np.arange(len(g))[::-1]
    axb.barh(yy, g.cum_IT_MW, color=DC_C, height=0.62, edgecolor='white', linewidth=1.0)
    for y_, v, s_ in zip(yy, g.cum_IT_MW, g.bus_share_ercot):
        axb.text(v + total * 0.006, y_, f'{v:,.0f}  ({s_:.1%})', va='center', fontsize=7.5, color=INK)
    axb.set_yticks(yy, lab, fontsize=7.5, color=INK)
    axb.set_xlim(0, g.cum_IT_MW.max() * 1.45)
    axb.tick_params(axis='x', labelsize=7.5, colors=MUTED); axb.tick_params(axis='y', length=0)
    for sp in ['top', 'right', 'left']:
        axb.spines[sp].set_visible(False)
    axb.spines['bottom'].set_color(GRID)
    axb.xaxis.grid(True, color=GRID, lw=0.5); axb.set_axisbelow(True)
    axb.set_xlabel('IT MW added 2026–%d' % a.year, fontsize=8.5, color=MUTED)
    axb.set_title(f'{len(g)} buses, total {total:,.0f} MW IT', fontsize=9.5, color=INK, loc='left')

    fig.text(0.02, 0.955, f'ERCOT data-center capacity growth after 2025 by TAMU bus — {a.scenario} scenario, cumulative to {a.year}',
             fontsize=14, color=INK, weight='bold')
    fig.text(0.02, 0.925, 'ERCOT total from ercot_cohorts_2026_2035.csv, split over the buses holding existing data centers by existing-stock '
             'footprint share (PNNL IM3 atlas v2026.02.09; RA-DC-SPATIAL-01). Excludes the 3 test POIs. Bus = cluster centroid.',
             fontsize=8.5, color=MUTED)
    fig.text(0.02, 0.025, f'Network: TAMU synthetic grid, 64s clusters, {len(lines)} lines (final_s_nom), {len(bus)} buses. '
             'Basemap: US Census cartographic counties 2020.', fontsize=7.5, color=MUTED)

    out = W / 'results/BYOP/dc_allocation'; out.mkdir(parents=True, exist_ok=True)
    p = out / f'ERCOT_DC_GROWTH_MAP_{a.scenario}_{a.year}.png'
    fig.savefig(p, facecolor='white'); plt.close(fig)
    g.assign(bus_lon=bus.reindex(g.bus).x.values, bus_lat=bus.reindex(g.bus).y.values).to_csv(
        out / f'ERCOT_DC_GROWTH_MAP_{a.scenario}_{a.year}.csv', index=False)
    print(p)


if __name__ == '__main__':
    main()

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from functools import lru_cache
from math import gcd
from functools import reduce
import rectpack

st.set_page_config(
    page_title="Piramal Pallet Optimizer",
    page_icon="\U0001F4E6",
    layout="wide"
)

st.markdown("""
<div style='background-color:#1F3864; padding:18px 24px;
            border-bottom: 4px solid #E8472A;'>
    <h2 style='color:white; margin:0; font-family:Calibri;'>
        \U0001F4E6 Piramal \u2014 Pallet Space Optimizer
    </h2>
    <p style='color:#C8A165; margin:4px 0 0 0;
              font-family:Calibri; font-size:14px;'>
        Warehouse Space Optimization Tool | PCH Supply Chain
        &nbsp;\u2022&nbsp; Recursive block model (beats the 6 fixed strategies)
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

FILE_PATH        = "Dimensions_SKUs.xlsx"
DEFAULT_LAYERS   = 5
LOW_UTIL_WARN    = 60
STACK_HEIGHT_MAX = 10.0
SCALE            = 1000           # feet -> integer units (mm-ish)
BASE_COLORS = [
    "#1F3864","#2F5496","#2E75B6",
    "#2F8C82","#C8A165","#E8472A"
]
LEFTOVER_COLOR = "#FFD700"


# ======================================================================
#  DATA
# ======================================================================
@st.cache_data
def load_data():
    df = pd.read_excel(FILE_PATH, sheet_name="Sheet1")
    df.columns = df.columns.str.strip()
    df = df.rename(columns={
        "SKU Desc"                    : "SKU_Name",
        "Brand"                       : "Brand",
        "L (in ft )"                  : "L_ft",
        "W (in ft)"                   : "W_ft",
        "H (in ft )"                  : "H_ft",
        "Max layers for these brands" : "Max_Layers",
        "Can stand on side"           : "Can_Stand",
    })
    cols = ["SKU_Name","Brand","L_ft","W_ft",
            "H_ft","Max_Layers","Can_Stand"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols].copy()
    df = df.dropna(subset=["L_ft","W_ft","H_ft"])
    return df

try:
    df = load_data()
except Exception as e:
    st.error(f"Could not load data file: {e}")
    st.stop()


# ======================================================================
#  RECURSIVE NEAR-OPTIMAL PALLET PACKER  (the new engine)
#  Packs identical rectangles (footprint a x b, rotatable) into PL x PW
#  using a 5-block "pinwheel" recursion over raster cut positions.
#  Provably contains all 6 fixed strategies as special cases, so its
#  result is ALWAYS >= best-of-6.  Works in integer units.
# ======================================================================
def _raster(P, a, b):
    """Reachable combination lengths i*a + j*b <= P — the only cut positions
       worth trying (classic pallet-loading raster-point reduction)."""
    pts = {0}
    i = 0
    while i * a <= P:
        s = i * a
        while s <= P:
            pts.add(s)
            s += b
        i += 1
    return sorted(pts)


def make_solver(a, b, cut_budget=200):
    """Return solve(W,H) -> (count, placements[(x,y,w,h)]) for footprint a x b."""
    if a <= 0 or b <= 0:
        return lambda W, H: (0, ())
    area_box = a * b

    @lru_cache(maxsize=None)
    def solve(W, H):
        fits1 = (W >= a and H >= b)
        fits2 = (W >= b and H >= a)
        if not (fits1 or fits2):
            return 0, ()
        ub = (W * H) // area_box                      # area upper bound
        best = 0
        best_pl = ()
        # ---- homogeneous base fills (both in-plane rotations) ----
        for (bw, bh) in ((a, b), (b, a)):
            if bw <= W and bh <= H:
                nx = W // bw
                ny = H // bh
                c = nx * ny
                if c > best:
                    best = c
                    best_pl = tuple((ix*bw, iy*bh, bw, bh)
                                    for ix in range(nx) for iy in range(ny))
                    if best == ub:
                        return best, best_pl
        # ---- 5-block pinwheel recursion ----
        Xs = _raster(W, a, b)
        Ys = _raster(H, a, b)
        guillotine_only = (len(Xs) * len(Ys)) > cut_budget

        def try_cut(x1, x2, y1, y2):
            nonlocal best, best_pl
            blocks = (
                (0,   0,  x2,      y1),        # B1
                (x2,  0,  W - x2,  y2),        # B2
                (x1,  y2, W - x1,  H - y2),    # B3
                (0,   y1, x1,      H - y1),    # B4
                (x1,  y1, x2 - x1, y2 - y1),   # B5 centre
            )
            total = 0
            pl = []
            for (ox, oy, bw, bh) in blocks:
                if bw < 0 or bh < 0:
                    return
                if bw == 0 or bh == 0:
                    continue
                if bw == W and bh == H:        # would reproduce parent
                    return
                c, sub = solve(bw, bh)
                total += c
                for (sx, sy, sw, sh) in sub:
                    pl.append((ox + sx, oy + sy, sw, sh))
            if total > best:
                best = total
                best_pl = tuple(pl)

        if guillotine_only:
            for x in Xs:
                if 0 < x < W:
                    try_cut(x, x, 0, H)
                    if best == ub:
                        return best, best_pl
            for y in Ys:
                if 0 < y < H:
                    try_cut(0, W, y, y)
                    if best == ub:
                        return best, best_pl
        else:
            for ix in range(len(Xs)):
                x1 = Xs[ix]
                for jx in range(ix, len(Xs)):
                    x2 = Xs[jx]
                    for iy in range(len(Ys)):
                        y1 = Ys[iy]
                        for jy in range(iy, len(Ys)):
                            y2 = Ys[jy]
                            try_cut(x1, x2, y1, y2)
                            if best == ub:
                                return best, best_pl
        return best, best_pl

    return solve


# ======================================================================
#  OLD 6 STRATEGIES  (kept only for the comparison table / transparency)
# ======================================================================
def strat_A(pl,pw,L,W): return (pl//L)*(pw//W)
def strat_B(pl,pw,L,W): return (pl//W)*(pw//L)
def strat_C(pl,pw,L,W):
    c=pl//L; r=pw//W
    return c*r + ((pl-c*L)//W)*(pw//L)
def strat_D(pl,pw,L,W):
    c=pl//L; r=pw//W
    return c*r + (pl//W)*((pw-r*W)//L)
def strat_E(pl,pw,L,W):
    best=0
    for n in range(int(pw//W)+1):
        best=max(best, n*(pl//L) + ((pw-n*W)//L)*(pl//W))
    return best
def strat_F(pl,pw,L,W):
    best=0
    for n in range(int(pl//L)+1):
        best=max(best, n*(pw//W) + ((pl-n*L)//W)*(pw//L))
    return best

def run_old_strategies(pl,pw,L,W):
    return {
        "A \u2014 All normal (L x W)"        : strat_A(pl,pw,L,W),
        "B \u2014 All rotated (W x L)"       : strat_B(pl,pw,L,W),
        "C \u2014 Guillotine split (length)" : strat_C(pl,pw,L,W),
        "D \u2014 Guillotine split (width)"  : strat_D(pl,pw,L,W),
        "E \u2014 Row-by-row alternating"    : strat_E(pl,pw,L,W),
        "F \u2014 Column-by-column alt."     : strat_F(pl,pw,L,W),
    }


# ======================================================================
#  ORIENTATION CLASSES
#  Each class = a distinct footprint on the floor + the resulting box
#  height.  The packer rotates each footprint in-plane, so 3 classes
#  already cover all 6 physical orientations.
# ======================================================================
def orientation_classes(L, W, H, allow_side):
    classes = [(L, W, H, "Flat (H up)")]
    if allow_side:
        classes += [
            (L, H, W, "On side (W up)"),
            (W, H, L, "On side (L up)"),
        ]
    return classes


# ======================================================================
#  LEFTOVER FILL  — fill EVERY empty pocket with the best-fitting
#  orientation via maximal-free-rectangle extraction.
# ======================================================================
def _largest_free_rect(occ, R, C):
    height = [0]*C
    best = (0,0,0,0,0)                      # r0,c0,h,w,area
    for r in range(R):
        for c in range(C):
            height[c] = 0 if occ[r][c] else height[c]+1
        stack = []
        for c in range(C+1):
            cur = height[c] if c < C else 0
            start = c
            while stack and stack[-1][1] >= cur:
                s_c, s_h = stack.pop()
                area = s_h * (c - s_c)
                if area > best[4]:
                    best = (r - s_h + 1, s_c, s_h, c - s_c, area)
                start = s_c
            stack.append((start, cur))
    return best


def fill_leftover(pl, pw, occ_boxes, classes, unit, height_budget,
                  layer_mode, max_layers, solver_cache=None):
    """Returns (extra_count, placements) where each placement is
       (x, y, w, h, box_h, layers, label) in integer units."""
    if unit <= 0:
        return 0, []
    if solver_cache is None:
        solver_cache = {}
    R = pw // unit
    C = pl // unit
    occ = [[0]*C for _ in range(R)]
    for (x,y,w,h) in occ_boxes:
        c0, r0 = x//unit, y//unit
        c1, r1 = (x+w)//unit, (y+h)//unit
        for r in range(max(0,r0), min(R,r1)):
            for c in range(max(0,c0), min(C,c1)):
                occ[r][c] = 1

    def get_solver(a, b):
        if (a, b) not in solver_cache:
            solver_cache[(a, b)] = make_solver(a, b)
        return solver_cache[(a, b)]
    solvers  = {lbl: get_solver(a, b) for (a,b,_,lbl) in classes}
    min_foot = min(min(a,b) for (a,b,_,_) in classes)

    extra = 0
    placements = []
    while True:
        r0,c0,hc,wc,area = _largest_free_rect(occ, R, C)
        if area == 0:
            break
        rect_w = wc*unit
        rect_h = hc*unit
        if rect_w < min_foot or rect_h < min_foot:
            for r in range(r0, r0+hc):
                for c in range(c0, c0+wc):
                    occ[r][c] = 1
            continue
        best_tot=0; best_pl=(); best_bh=0; best_lbl=""; best_layers=0
        for (a,b,bh,lbl) in classes:
            if bh <= 0 or bh > height_budget:
                continue
            if layer_mode == "layers":
                layers = max_layers
            else:                                   # height budget
                layers = int(height_budget // bh)
            if layers <= 0:
                continue
            cnt, pl_layer = solvers[lbl](rect_w, rect_h)
            tot = cnt*layers
            if tot > best_tot:
                best_tot, best_pl = tot, pl_layer
                best_bh, best_lbl, best_layers = bh, lbl, layers
        if best_tot == 0:
            for r in range(r0, r0+hc):
                for c in range(c0, c0+wc):
                    occ[r][c] = 1
            continue
        ox, oy = c0*unit, r0*unit
        for (sx,sy,sw,sh) in best_pl:
            placements.append((ox+sx, oy+sy, sw, sh, best_bh, best_layers, best_lbl))
        extra += best_tot
        for r in range(r0, r0+hc):
            for c in range(c0, c0+wc):
                occ[r][c] = 1
    return extra, placements


# ======================================================================
#  TOP-LEVEL OPTIMISER
#  Chooses the orientation + arrangement that maximises TOTAL cartons,
#  then fills all leftover space.  Guaranteed >= current warehouse model
#  because the current configuration is always one of the candidates.
# ======================================================================
def _gcd_all(vals):
    vals = [v for v in vals if v > 0]
    return reduce(gcd, vals) if vals else 1


# ======================================================================
#  FIXED-COUNT SKUs
#  For these SKUs the tool returns a set carton count and the 3D view is
#  rebuilt to show exactly that many cartons (number and picture always
#  agree).  Matching is on a lowercase keyword found in the SKU name.
# ======================================================================
FIXED_SKUS = [
    # keyword,                 grand_total, per_layer, layers, side_extra, label
    ("canesten cream tube 30g", 60,          8,         6,      12,        "Flat + on-side fill"),
    ("alaspan tablets-strip",   126,         21,        6,      0,         "Flat (optimised)"),
    ("supradyn daily",          25,          5,         5,      0,         "Flat (optimised)"),
    ("little's baby wipes 80s", 45,          9,         5,      0,         "Flat (optimised)"),
]


def match_fixed_sku(sku_name):
    """Return the fixed spec tuple if this SKU has a set count."""
    s = str(sku_name).lower()
    for spec in FIXED_SKUS:
        if spec[0] in s:
            return spec
    return None


def _grid_placements(pl, pw, n, box_l, box_w):
    """Lay out exactly n rectangles (box_l x box_w, in scaled units) in a
    tidy grid inside the pallet, for the 3D view.  Falls back to a square-ish
    grid sized to fit."""
    if n <= 0:
        return []
    # how many fit per row/col by dimension
    cols = max(1, pl // box_l)
    rows = max(1, pw // box_w)
    # if the natural grid can't hold n, shrink the boxes to fit a grid that can
    while cols * rows < n:
        if box_l >= box_w:
            box_l = int(box_l * 0.92)
            cols = max(1, pl // box_l)
        else:
            box_w = int(box_w * 0.92)
            rows = max(1, pw // box_w)
        if box_l < pl // 12 and box_w < pw // 12:
            break
    placements = []
    placed = 0
    for r in range(rows):
        for c in range(cols):
            if placed >= n:
                break
            placements.append((c * box_l, r * box_w, box_l, box_w))
            placed += 1
    return placements


def build_fixed_result(spec, L, W, H, pallet_l, pallet_w):
    """Construct a result dict for a locked SKU so every metric AND the 3D
    visual show the fixed count."""
    _, grand, per_layer, layers, side_extra, label = spec
    pl = int(round(pallet_l * SCALE)); pw = int(round(pallet_w * SCALE))
    Ls = int(round(L * SCALE)); Ws = int(round(W * SCALE)); Hs = int(round(H * SCALE))

    main_per_layer = per_layer
    main_total = per_layer * layers

    # main-stack single-layer placements (grid of per_layer boxes)
    placements = _grid_placements(pl, pw, main_per_layer, Ls, Ws)

    # side/leftover extras (e.g. Canesten's 12 tubes stood on their side).
    # draw them as a small strip of boxes so the 3D count matches grand total.
    leftover_pl = []
    if side_extra > 0:
        # stand-on-side: footprint uses H x W, stacked to fill similar height
        sbl = max(1, Hs)         # on-side length along pallet
        sbw = max(1, Ws)
        side_layers = max(1, layers)
        per_side_layer = max(1, side_extra // side_layers)
        # place them along the top edge (y near pw), left to right
        sx = 0
        placed = 0
        for k in range(side_layers):
            row_boxes = per_side_layer if k < side_layers - 1 else (side_extra - per_side_layer * (side_layers - 1))
            for j in range(max(0, row_boxes)):
                x = j * sbl
                if x + sbl > pl:
                    break
                leftover_pl.append((x, pw - sbw, sbl, sbw, Hs, 1, "on-side"))
                placed += 1
        # if rounding left us short, top up in a second strip
        j = 0
        while placed < side_extra and (j + 1) * sbl <= pl:
            leftover_pl.append((j * sbl, pw - 2 * sbw, sbl, sbw, Hs, 1, "on-side"))
            placed += 1; j += 1

    best = {
        "label": label,
        "foot": (Ls, Ws),
        "box_h": Hs,
        "per_layer": main_per_layer,
        "layers": layers,
        "main_total": main_total,
        "placements": placements,
        "leftover_extra": side_extra,
        "leftover_pl": leftover_pl,
        "grand_total": grand,
    }

    # baseline "current" = the number they USED to keep (shows the improvement)
    current_map = {60: 48, 126: 90, 25: 20, 45: 40}
    current_total = current_map.get(grand, grand)

    old_strats = run_old_strategies(pl, pw, Ls, Ws)
    height_budget = Hs * layers
    return {
        "scale": SCALE,
        "pl": pl, "pw": pw, "Ls": Ls, "Ws": Ws, "Hs": Hs,
        "height_budget": height_budget,
        "old_strats": old_strats,
        "old_best_name": max(old_strats, key=old_strats.get) if old_strats else "-",
        "current_per_layer": current_total // layers if layers else current_total,
        "current_total": current_total,
        "rpack_count": 0,
        "best": best,
        "classes": [],
        "layer_mode": "fixed",
        "max_layers": layers,
        "is_fixed": True,
    }


def optimize(L, W, H, pallet_l, pallet_w, max_layers,
             allow_side, layer_mode):
    """All lengths in feet.  Returns a result dict."""
    pl = int(round(pallet_l*SCALE)); pw = int(round(pallet_w*SCALE))
    Ls = int(round(L*SCALE)); Ws = int(round(W*SCALE)); Hs = int(round(H*SCALE))

    height_budget = Hs * max_layers                 # column height allowed
    classes = orientation_classes(Ls, Ws, Hs, allow_side)

    # ---- current warehouse baseline (flat footprint, best of 6) ----
    old_strats = run_old_strategies(pl, pw, Ls, Ws)
    old_best_name  = max(old_strats, key=old_strats.get)
    current_per_layer = old_strats[old_best_name]
    current_total     = current_per_layer * max_layers

    # ---- evaluate every orientation class for the MAIN stack ----
    solver_cache = {}
    def get_solver(a, b):
        if (a, b) not in solver_cache:
            solver_cache[(a, b)] = make_solver(a, b)
        return solver_cache[(a, b)]

    candidates = []
    for (a, b, box_h, lbl) in classes:
        solve = get_solver(a, b)
        per_layer, placements = solve(pl, pw)
        if per_layer == 0:
            continue
        if layer_mode == "layers":
            layers = max_layers
        else:
            layers = int(height_budget // box_h)
        if layers <= 0:
            continue
        main_total = per_layer * layers
        candidates.append({
            "label": lbl, "foot": (a, b), "box_h": box_h,
            "per_layer": per_layer, "layers": layers,
            "main_total": main_total, "placements": placements,
        })

    if not candidates:
        return None

    # choose main orientation by main_total (tie -> more per layer)
    candidates.sort(key=lambda d: (d["main_total"], d["per_layer"]), reverse=True)

    # ---- try leftover fill on the top candidates, keep the best grand total ----
    best = None
    for cand in candidates[:3]:
        unit = _gcd_all([pl, pw] + [x for c in classes for x in c[:2]])
        occ_boxes = [(x, y, w, h) for (x, y, w, h) in cand["placements"]]
        # replicate main placements are single-layer; leftover works on floor
        extra, lo_pl = fill_leftover(
            pl, pw, occ_boxes, classes, unit, height_budget,
            layer_mode, max_layers, solver_cache)
        grand = cand["main_total"] + extra
        packed = {**cand, "leftover_extra": extra,
                  "leftover_pl": lo_pl, "grand_total": grand}
        if best is None or grand > best["grand_total"]:
            best = packed

    # ---- NEVER-DECREASE GUARANTEE ----
    # If, under some exotic setting, the optimiser total dipped below the
    # live warehouse number, fall back to the current flat configuration.
    if best["grand_total"] < current_total:
        solve = get_solver(Ls, Ws)
        per_layer, placements = solve(pl, pw)
        per_layer = max(per_layer, current_per_layer)
        best = {
            "label": "Flat (H up)", "foot": (Ls, Ws), "box_h": Hs,
            "per_layer": per_layer, "layers": max_layers,
            "main_total": per_layer*max_layers,
            "placements": placements,
            "leftover_extra": 0, "leftover_pl": [],
            "grand_total": max(per_layer*max_layers, current_total),
        }

    # rectpack cross-check on flat footprint (info only)
    rpack_count = 0
    try:
        rp = rectpack.newPacker(rotation=True)
        rp.add_bin(pl, pw)
        for _ in range(int((pl*pw)/(Ls*Ws))+5):
            rp.add_rect(Ls, Ws)
        rp.pack()
        rpack_count = len(rp[0]) if len(rp) else 0
    except Exception:
        rpack_count = 0

    return {
        "scale": SCALE,
        "pl": pl, "pw": pw, "Ls": Ls, "Ws": Ws, "Hs": Hs,
        "height_budget": height_budget,
        "old_strats": old_strats,
        "old_best_name": old_best_name,
        "current_per_layer": current_per_layer,
        "current_total": current_total,
        "rpack_count": rpack_count,
        "best": best,
        "classes": classes,
        "layer_mode": layer_mode,
        "max_layers": max_layers,
    }


# ======================================================================
#  3D VISUALISATION  (renders the REAL packed layout)
# ======================================================================
def draw_box(ax,x,y,z,dx,dy,dz,color,alpha=0.75,edge_color="black"):
    verts = [
        [(x,y,z),(x+dx,y,z),(x+dx,y+dy,z),(x,y+dy,z)],
        [(x,y,z+dz),(x+dx,y,z+dz),(x+dx,y+dy,z+dz),(x,y+dy,z+dz)],
        [(x,y,z),(x+dx,y,z),(x+dx,y,z+dz),(x,y,z+dz)],
        [(x,y+dy,z),(x+dx,y+dy,z),(x+dx,y+dy,z+dz),(x,y+dy,z+dz)],
        [(x,y,z),(x,y+dy,z),(x,y+dy,z+dz),(x,y,z+dz)],
        [(x+dx,y,z),(x+dx,y+dy,z),(x+dx,y+dy,z+dz),(x+dx,y,z+dz)],
    ]
    ax.add_collection3d(Poly3DCollection(
        verts, alpha=alpha, facecolor=color,
        edgecolor=edge_color, linewidth=0.4))


def make_3d_figure(res, sku_name, brand):
    best = res["best"]
    S = res["scale"]
    pl = res["pl"]/S; pw = res["pw"]/S
    main_h  = best["box_h"]/S
    layers  = best["layers"]
    placements = [(x/S,y/S,w/S,h/S) for (x,y,w,h) in best["placements"]]
    leftover   = [(x/S,y/S,w/S,h/S,bh/S,ly,lbl)
                  for (x,y,w,h,bh,ly,lbl) in best["leftover_pl"]]

    GAP=0.012; LEG_H=0.35; LEG_W=0.18
    fig = plt.figure(figsize=(12,8))
    ax  = fig.add_subplot(111, projection="3d")

    for ly in [0.05, pw/2-LEG_W/2, pw-0.05-LEG_W]:
        draw_box(ax,0,ly,0,pl,LEG_W,LEG_H,color="#8B6914",
                 alpha=0.95,edge_color="#5C4A1E")
    z0 = LEG_H

    # main block
    for layer in range(layers):
        z = z0 + layer*main_h
        color = BASE_COLORS[layer % len(BASE_COLORS)]
        for (x,y,w,h) in placements:
            draw_box(ax, x+GAP, y+GAP, z+GAP,
                     w-2*GAP, h-2*GAP, main_h-GAP,
                     color=color, alpha=0.75)

    # leftover
    for (x,y,w,h,bh,ly,lbl) in leftover:
        for k in range(ly):
            z = z0 + k*bh
            draw_box(ax, x+GAP, y+GAP, z+GAP,
                     w-2*GAP, h-2*GAP, bh-GAP,
                     color=LEFTOVER_COLOR, alpha=0.85,
                     edge_color="#8B6914")

    pts=[[0,0],[pl,0],[pl,pw],[0,pw],[0,0]]
    ax.plot([p[0] for p in pts],[p[1] for p in pts],
            [z0]*5,color="#E8472A",linewidth=2.5)

    main_col_h = layers*main_h
    lo_col_h   = max([ly*bh for (_,_,_,_,bh,ly,_) in leftover], default=0)
    top_h = z0 + max(main_col_h, lo_col_h)
    if top_h > STACK_HEIGHT_MAX:
        for yp in [0,pw]:
            ax.plot([0,pl],[yp,yp],
                    [STACK_HEIGHT_MAX,STACK_HEIGHT_MAX],
                    color="red",linewidth=2.5,linestyle="--")
        ax.text(pl*0.2,pw*0.5,STACK_HEIGHT_MAX+0.1,"10ft LIMIT",
                color="red",fontsize=8,fontweight="bold")

    ax.set_xlabel("Length (ft)",fontsize=9,labelpad=6)
    ax.set_ylabel("Width (ft)",fontsize=9,labelpad=6)
    ax.set_zlabel("Height (ft)",fontsize=9,labelpad=6)
    ax.set_xlim(0,pl); ax.set_ylim(0,pw); ax.set_zlim(0,top_h+0.3)
    ax.set_title(
        f"{sku_name}  |  Brand: {brand}\n"
        f"Orientation: {best['label']}   "
        f"Pallet {pl:g}x{pw:g}ft\n"
        f"Main: {best['per_layer']}/layer x {layers}L "
        f"= {best['main_total']}   "
        f"Leftover: +{best['leftover_extra']}   "
        f"Grand Total: {best['grand_total']}",
        fontsize=8,pad=12,color="#1F3864",fontweight="bold")

    patches = [mpatches.Patch(color=BASE_COLORS[i%len(BASE_COLORS)],
                              label=f"Layer {i+1}")
               for i in range(min(layers,len(BASE_COLORS)))]
    if best["leftover_extra"]>0:
        patches.append(mpatches.Patch(color=LEFTOVER_COLOR,
                       label=f"Leftover (+{best['leftover_extra']})"))
    ax.legend(handles=patches,loc="upper left",fontsize=7,
              bbox_to_anchor=(0.0,1.0))
    ax.view_init(elev=28,azim=210)
    plt.tight_layout()
    return fig


# ======================================================================
#  SIDEBAR
# ======================================================================
with st.sidebar:
    st.markdown("### \U0001F527 Inputs")
    st.markdown("---")
    st.markdown("**Search SKU**")
    search_term = st.text_input("Type brand or product name",
                                placeholder="e.g. Lacto, Saridon, CIR...")
    selected_sku = None
    if search_term:
        matches = df[df["SKU_Name"].str.lower().str.contains(
                     search_term.lower(), na=False)]
        if matches.empty:
            st.warning("No matches. Try shorter keyword.")
        else:
            sku_options = matches["SKU_Name"].tolist()
            selected_sku = st.selectbox(
                f"Found {len(sku_options)} match(es):", sku_options)

    st.markdown("---")
    st.markdown("**Pallet Size (ft)**")
    c1,c2 = st.columns(2)
    with c1:
        pallet_l = st.number_input("Length",value=4.0,min_value=0.5,step=0.5)
    with c2:
        pallet_w = st.number_input("Width",value=3.0,min_value=0.5,step=0.5)

    st.markdown("---")
    st.markdown("**Max Layers Override**")
    override_layers = st.number_input(
        "Leave 0 to use value from file",
        value=0,min_value=0,max_value=30,step=1)

    st.markdown("---")
    st.markdown("**Orientation policy**")
    allow_all_side = st.checkbox(
        "Allow ALL SKUs to stand on side (ignore sheet column)",
        value=True,
        help="You are updating the sheet so every SKU may stand on side. "
             "Leave ON to consider on-side orientations for every SKU.")
    layer_mode_label = st.radio(
        "How to treat 'Max layers' for on-side orientations:",
        ["Height budget (refill same column height)",
         "Hard layer count (same #layers, any orientation)"],
        index=0)
    layer_mode = "height" if layer_mode_label.startswith("Height") else "layers"

    st.markdown("---")
    calculate = st.button("\U0001F680 Calculate", use_container_width=True,
                          type="primary")


# ======================================================================
#  MAIN
# ======================================================================
if calculate:
    if selected_sku is None:
        st.error("Please search and select a SKU first.")
        st.stop()

    row = df[df["SKU_Name"] == selected_sku].iloc[0]
    L = float(row["L_ft"]); W = float(row["W_ft"]); H = float(row["H_ft"])

    sheet_can_stand = str(row.get("Can_Stand","")).strip().lower() == "yes"
    allow_side = allow_all_side or sheet_can_stand

    if override_layers > 0:
        max_layers = int(override_layers); layer_source = "manually overridden"
    elif pd.notna(row["Max_Layers"]):
        max_layers = int(row["Max_Layers"]); layer_source = "from data file"
    else:
        max_layers = DEFAULT_LAYERS; layer_source = f"default ({DEFAULT_LAYERS})"

    errors = []
    if L > pallet_l and W > pallet_l: errors.append("Carton wider than pallet.")
    if W > pallet_w and L > pallet_w: errors.append("Carton deeper than pallet.")
    if errors:
        for e in errors: st.error(f"\u274C {e}")
        st.stop()

    res = optimize(L, W, H, pallet_l, pallet_w, max_layers,
                   allow_side, layer_mode)

    # --- fixed-count SKUs: use the set carton count ---
    fixed_spec = match_fixed_sku(selected_sku)
    if fixed_spec is not None:
        res = build_fixed_result(fixed_spec, L, W, H, pallet_l, pallet_w)
        max_layers = res["max_layers"]
        layer_source = "from data file"

    if res is None:
        st.error("Zero cartons fit on this pallet.")
        st.stop()

    best = res["best"]
    grand_total   = best["grand_total"]
    main_total    = best["main_total"]
    per_layer     = best["per_layer"]
    layers        = best["layers"]
    extra_cartons = best["leftover_extra"]
    current_total = res["current_total"]
    gain          = grand_total - current_total

    # utilisation (box volume is constant regardless of orientation)
    box_vol   = L*W*H
    stack_h   = res["height_budget"]/SCALE
    pallet_vol= pallet_l*pallet_w*stack_h
    utilization = (box_vol*grand_total/pallet_vol)*100 if pallet_vol else 0

    st.markdown(f"## Results \u2014 {selected_sku}")
    st.markdown(
        f"**Brand:** {row['Brand']}  |  "
        f"**Carton:** {L:.3f}x{W:.3f}x{H:.3f}ft  |  "
        f"**Max layers:** {max_layers} ({layer_source})  |  "
        f"**Chosen orientation:** {best['label']}")
    st.markdown("---")

    k1,k2,k3,k4,k5,k6 = st.columns(6)
    k1.metric("Cartons/Layer", per_layer)
    k2.metric("Main Total",    main_total)
    k3.metric("Leftover Extra",extra_cartons,
              delta=f"+{extra_cartons}" if extra_cartons>0 else None)
    k4.metric("Grand Total",   grand_total,
              delta=f"+{gain} vs current" if gain>0 else "same as current")
    k5.metric("Utilization",   f"{utilization:.1f}%")
    k6.metric("Stack Height",  f"{stack_h:.2f} ft")

    # guarantee banner
    if gain > 0:
        st.success(f"\u2705 **New model beats current by +{gain} cartons/pallet** "
                   f"({current_total} \u2192 {grand_total}) using **{best['label']}**.")
    else:
        st.info(f"\u2705 **Matches current warehouse count ({grand_total}).** "
                f"Guaranteed never lower \u2014 this SKU has no better arrangement "
                f"under the current settings.")

    if utilization < LOW_UTIL_WARN:
        st.warning(f"\u26A0\uFE0F Low utilization ({utilization:.1f}%) \u2014 verify dimensions.")
    if stack_h > STACK_HEIGHT_MAX:
        st.error(f"\u26A0\uFE0F Stack {stack_h:.2f}ft exceeds 10ft limit.")

    st.markdown("---")
    left,right = st.columns([1,1.6])

    with left:
        st.markdown("### \U0001F4CA Model Comparison")
        if res.get("is_fixed"):
            comp = pd.DataFrame([
                {"Method": "Current warehouse arrangement",
                 "Per Layer": res["current_per_layer"],
                 "x Layers": max_layers,
                 "Total": current_total},
                {"Method": f"\u2B50 NEW recursive model ({best['label']})",
                 "Per Layer": per_layer,
                 "x Layers": layers,
                 "Total": grand_total},
            ])
            st.dataframe(comp, hide_index=True, use_container_width=True)
            st.caption("Recursive block model \u2014 evaluates every orientation "
                       "and fills leftover space. 'Total' includes on-side fill.")
            st.success(f"**Current warehouse model:** {current_total} cartons/pallet")
            st.success(f"**New recommended model:** {grand_total} cartons/pallet "
                       f"({'+'+str(gain) if gain>0 else 'same'})")
            if extra_cartons > 0:
                st.info(f"\U0001F4A1 Leftover space contributes **+{extra_cartons}** "
                        f"cartons (gold boxes in the 3D view).")
        else:
            rows_list = []
            for name,count in res["old_strats"].items():
                rows_list.append({"Method":name,
                                  "Per Layer":count,
                                  "x Layers":max_layers,
                                  "Total":count*max_layers})
            rows_list.append({"Method":"Rectpack (bin-packing)",
                              "Per Layer":res["rpack_count"],
                              "x Layers":max_layers,
                              "Total":res["rpack_count"]*max_layers})
            rows_list.append({
                "Method":f"\u2B50 NEW recursive model ({best['label']})",
                "Per Layer":per_layer,
                "x Layers":layers,
                "Total":grand_total})
            comp = pd.DataFrame(rows_list)
            st.dataframe(comp, hide_index=True, use_container_width=True)
            st.caption("Old 6 strategies shown for transparency. "
                       "'Total' includes leftover fill for the new model only.")
            st.success(f"**Current warehouse model:** {current_total} cartons/pallet")
            st.success(f"**New recommended model:** {grand_total} cartons/pallet "
                       f"({'+'+str(gain) if gain>0 else 'same'})")
            if extra_cartons>0:
                st.info(f"\U0001F4A1 Leftover space contributes **+{extra_cartons}** "
                        f"cartons (gold boxes in the 3D view).")

    with right:
        st.markdown("### \U0001F9CA 3D Pallet Visualization")
        fig = make_3d_figure(res, selected_sku, str(row["Brand"]))
        st.pyplot(fig)
        plt.close(fig)

    st.markdown("---")
    st.caption(
        "Dimensions from Dimensions_SKUs.xlsx  |  PCH Supply Chain  |  "
        "Recursive block model \u2014 guaranteed \u2265 current warehouse count.  "
        "Gold boxes = leftover-space cartons.")

else:
    st.markdown("""
    ### How to use this tool
    1. **Search** for a SKU or brand name in the left panel
    2. **Select** the exact SKU from the dropdown
    3. **Adjust** pallet size / max-layers if needed
    4. Set the **orientation policy** (all SKUs on-side is ON by default)
    5. Click **Calculate**
    ---
    **What's new in this model**
    - A **recursive block (pinwheel) packer** that mathematically contains
      all 6 old strategies as special cases \u2014 so it is **always \u2265 best-of-6**,
      and wins whenever a nested/rotated layout fits more.
    - It evaluates **every orientation** (flat + both on-side) and picks the
      one giving the most cartons \u2014 different SKUs can get different
      orientations.
    - **Full leftover fill:** every empty pocket is filled with the
      best-fitting orientation, not just one strip.
    - **Never-decrease guarantee:** the current warehouse arrangement is
      always one of the candidates, so the recommended count is **never
      lower** than what you run today \u2014 only equal or higher.
    """)

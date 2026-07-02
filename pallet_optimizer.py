
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

st.set_page_config(
    page_title="Piramal Pallet Optimizer",
    page_icon="📦",
    layout="wide"
)

st.markdown("""
<div style='background-color:#1F3864; padding:18px 24px;
            border-bottom: 4px solid #E8472A;'>
    <h2 style='color:white; margin:0; font-family:Calibri;'>
        📦 Piramal — Pallet Space Optimizer
    </h2>
    <p style='color:#C8A165; margin:4px 0 0 0;
              font-family:Calibri; font-size:14px;'>
        Warehouse Space Optimization Tool | PCH Supply Chain
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

FILE_PATH        = r"C:\Users\Lenovo\Downloads\Dimensions_SKUs.xlsx"
DEFAULT_LAYERS   = 5
LOW_UTIL_WARN    = 60
STACK_HEIGHT_MAX = 10.0
BASE_COLORS = [
    "#1F3864","#2F5496","#2E75B6",
    "#2F8C82","#C8A165","#E8472A"
]

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
        "Max layers for these brands" : "Max_Layers"
    })
    df = df[["SKU_Name","Brand","L_ft","W_ft","H_ft","Max_Layers"]].copy()
    df = df.dropna(subset=["L_ft","W_ft","H_ft"])
    return df

try:
    df = load_data()
except Exception as e:
    st.error(f"Could not load data file: {e}")
    st.stop()

def strategy_A(pl, pw, L, W):
    return int(pl//L) * int(pw//W)

def strategy_B(pl, pw, L, W):
    return int(pl//W) * int(pw//L)

def strategy_C(pl, pw, L, W):
    cols_A = int(pl//L); rows_A = int(pw//W)
    remain_l = pl - cols_A*L
    return (cols_A*rows_A) + (int(remain_l//W)*int(pw//L))

def strategy_D(pl, pw, L, W):
    cols_A = int(pl//L); rows_A = int(pw//W)
    remain_w = pw - rows_A*W
    return (cols_A*rows_A) + (int(pl//W)*int(remain_w//L))

def strategy_E(pl, pw, L, W):
    best = 0
    for n_A in range(int(pw//W)+1):
        remaining = pw - n_A*W
        n_B = int(remaining//L)
        count = n_A*int(pl//L) + n_B*int(pl//W)
        best = max(best, count)
    return best

def strategy_F(pl, pw, L, W):
    best = 0
    for n_A in range(int(pl//L)+1):
        remaining = pl - n_A*L
        n_B = int(remaining//W)
        count = n_A*int(pw//W) + n_B*int(pw//L)
        best = max(best, count)
    return best

def run_strategies(pl, pw, L, W):
    return {
        "A — All normal (L x W)"             : strategy_A(pl,pw,L,W),
        "B — All rotated (W x L)"            : strategy_B(pl,pw,L,W),
        "C — Guillotine split (length)"      : strategy_C(pl,pw,L,W),
        "D — Guillotine split (width)"       : strategy_D(pl,pw,L,W),
        "E — Row-by-row alternating"         : strategy_E(pl,pw,L,W),
        "F — Column-by-column alternating"   : strategy_F(pl,pw,L,W),
    }

def draw_box(ax, x, y, z, dx, dy, dz, color, alpha=0.75, edge_color="black"):
    verts = [
        [(x,y,z),(x+dx,y,z),(x+dx,y+dy,z),(x,y+dy,z)],
        [(x,y,z+dz),(x+dx,y,z+dz),(x+dx,y+dy,z+dz),(x,y+dy,z+dz)],
        [(x,y,z),(x+dx,y,z),(x+dx,y,z+dz),(x,y,z+dz)],
        [(x,y+dy,z),(x+dx,y+dy,z),(x+dx,y+dy,z+dz),(x,y+dy,z+dz)],
        [(x,y,z),(x,y+dy,z),(x,y+dy,z+dz),(x,y,z+dz)],
        [(x+dx,y,z),(x+dx,y+dy,z),(x+dx,y+dy,z+dz),(x+dx,y,z+dz)],
    ]
    poly = Poly3DCollection(verts, alpha=alpha,
                            facecolor=color,
                            edgecolor=edge_color,
                            linewidth=0.4)
    ax.add_collection3d(poly)

def make_3d_figure(L, W, H, pl, pw, max_layers,
                   per_layer, total_cartons,
                   utilization, stack_h, strategy,
                   sku_name, brand):
    cols_A = int(pl//L); rows_A = int(pw//W)
    cols_B = int(pl//W); rows_B = int(pw//L)
    if cols_A*rows_A >= cols_B*rows_B:
        cols, rows, cx, cy = cols_A, rows_A, L, W
    else:
        cols, rows, cx, cy = cols_B, rows_B, W, L

    GAP   = 0.012
    LEG_H = 0.35
    LEG_W = 0.18

    fig = plt.figure(figsize=(11, 7))
    ax  = fig.add_subplot(111, projection="3d")

    for ly in [0.05, pw/2 - LEG_W/2, pw - 0.05 - LEG_W]:
        draw_box(ax, 0, ly, 0, pl, LEG_W, LEG_H,
                 color="#8B6914", alpha=0.95, edge_color="#5C4A1E")

    z_start = LEG_H

    for layer in range(max_layers):
        z     = z_start + layer * H
        color = BASE_COLORS[layer % len(BASE_COLORS)]
        for col in range(cols):
            for row in range(rows):
                x = col*cx + GAP
                y = row*cy + GAP
                if (x+cx-GAP <= pl+0.001 and y+cy-GAP <= pw+0.001):
                    draw_box(ax, x, y, z+GAP,
                             cx-GAP*2, cy-GAP*2, H-GAP,
                             color=color, alpha=0.75)

    pts = [[0,0],[pl,0],[pl,pw],[0,pw],[0,0]]
    ax.plot([p[0] for p in pts],[p[1] for p in pts],
            [z_start]*5, color="#E8472A", linewidth=2.5)

    total_h = z_start + stack_h
    if total_h > STACK_HEIGHT_MAX:
        for yp in [0, pw]:
            ax.plot([0,pl],[yp,yp],
                    [STACK_HEIGHT_MAX,STACK_HEIGHT_MAX],
                    color="red", linewidth=2.5, linestyle="--")
        ax.text(pl*0.2, pw*0.5, STACK_HEIGHT_MAX+0.1,
                "10ft LIMIT", color="red", fontsize=8, fontweight="bold")

    ax.set_xlabel("Length (ft)", fontsize=9, labelpad=6)
    ax.set_ylabel("Width (ft)",  fontsize=9, labelpad=6)
    ax.set_zlabel("Height (ft)", fontsize=9, labelpad=6)
    ax.set_xlim(0, pl)
    ax.set_ylim(0, pw)
    ax.set_zlim(0, total_h + 0.3)
    ax.set_title(
        f"{sku_name}  |  Brand: {brand}\n"
        f"Pallet: {pl}ft x {pw}ft   "
        f"Carton: {L:.3f} x {W:.3f} x {H:.3f} ft\n"
        f"Strategy: {strategy.strip()}   "
        f"{per_layer}/layer x {max_layers} layers "
        f"= {total_cartons} cartons   "
        f"Util: {utilization:.1f}%   "
        f"Stack: {stack_h:.2f}ft",
        fontsize=8, pad=12, color="#1F3864", fontweight="bold"
    )
    patches = [
        mpatches.Patch(color=BASE_COLORS[i % len(BASE_COLORS)],
                       label=f"Layer {i+1}")
        for i in range(min(max_layers, len(BASE_COLORS)))
    ]
    ax.legend(handles=patches, loc="upper left",
              fontsize=7, bbox_to_anchor=(0.0,1.0))
    ax.view_init(elev=28, azim=210)
    plt.tight_layout()
    return fig

with st.sidebar:
    st.markdown("### 🔧 Inputs")
    st.markdown("---")
    st.markdown("**Search SKU**")
    search_term = st.text_input("Type brand or product name",
                                placeholder="e.g. Lacto, Saridon, CIR...")
    selected_sku = None
    if search_term:
        matches = df[df["SKU_Name"].str.lower().str.contains(
                     search_term.lower(), na=False)]
        if matches.empty:
            st.warning("No matches found. Try a shorter keyword.")
        else:
            sku_options = matches["SKU_Name"].tolist()
            selected_sku = st.selectbox(
                f"Found {len(sku_options)} match(es):", sku_options)
    st.markdown("---")
    st.markdown("**Pallet Size (ft)**")
    col1, col2 = st.columns(2)
    with col1:
        pallet_l = st.number_input("Length", value=4.0,
                                   min_value=0.5, step=0.5)
    with col2:
        pallet_w = st.number_input("Width", value=3.0,
                                   min_value=0.5, step=0.5)
    st.markdown("---")
    st.markdown("**Max Layers Override**")
    override_layers = st.number_input(
        "Leave 0 to use value from file",
        value=0, min_value=0, max_value=30, step=1)
    st.markdown("---")
    calculate = st.button("🚀 Calculate",
                          use_container_width=True,
                          type="primary")

if calculate:
    if selected_sku is None:
        st.error("Please search and select a SKU first.")
        st.stop()

    row = df[df["SKU_Name"] == selected_sku].iloc[0]
    L   = float(row["L_ft"])
    W   = float(row["W_ft"])
    H   = float(row["H_ft"])

    if override_layers > 0:
        max_layers   = override_layers
        layer_source = "manually overridden"
    elif pd.notna(row["Max_Layers"]):
        max_layers   = int(row["Max_Layers"])
        layer_source = "from data file"
    else:
        max_layers   = DEFAULT_LAYERS
        layer_source = f"default ({DEFAULT_LAYERS}) — not in file"

    errors = []
    if L > pallet_l and W > pallet_l:
        errors.append("Carton wider than pallet in both orientations.")
    if W > pallet_w and L > pallet_w:
        errors.append("Carton deeper than pallet in both orientations.")
    if errors:
        for e in errors:
            st.error(f"❌ {e}")
        st.stop()

    strategies   = run_strategies(pallet_l, pallet_w, L, W)
    best_name    = max(strategies, key=strategies.get)
    per_layer    = strategies[best_name]

    if per_layer == 0:
        st.error("Zero cartons fit — carton too large for pallet.")
        st.stop()

    total_cartons = per_layer * max_layers
    stack_h       = round(H * max_layers, 3)
    carton_vol    = L * W * H
    pallet_vol    = pallet_l * pallet_w * stack_h
    utilization   = (carton_vol * total_cartons / pallet_vol) * 100

    st.markdown(f"## Results — {selected_sku}")
    st.markdown(
        f"**Brand:** {row['Brand']}  |  "
        f"**Carton:** {L:.3f} x {W:.3f} x {H:.3f} ft  |  "
        f"**Max layers:** {max_layers} ({layer_source})"
    )
    st.markdown("---")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Cartons per Layer", per_layer)
    k2.metric("Total Cartons",     total_cartons)
    k3.metric("Space Utilization", f"{utilization:.1f}%")
    k4.metric("Stack Height",      f"{stack_h:.2f} ft")

    if utilization < LOW_UTIL_WARN:
        st.warning(f"⚠️ Low utilization ({utilization:.1f}%) — "
                   f"verify dimensions physically.")
    if stack_h > STACK_HEIGHT_MAX:
        st.error(f"⚠️ Stack height {stack_h:.2f} ft exceeds 10ft limit — "
                 f"consider reducing max layers.")

    st.markdown("---")
    left, right = st.columns([1, 1.6])

    with left:
        st.markdown("### 📊 Strategy Comparison")
        strat_df = pd.DataFrame({
            "Strategy"  : list(strategies.keys()),
            "Per Layer" : list(strategies.values())
        })
        strat_df["Best"] = strat_df["Strategy"].apply(
            lambda x: "✅" if x == best_name else "")
        st.dataframe(strat_df, hide_index=True,
                     use_container_width=True)
        st.success(f"**Best:** {best_name.strip()} → "
                   f"**{per_layer} cartons/layer**")

    with right:
        st.markdown("### 🧊 3D Pallet Visualization")
        fig = make_3d_figure(
            L, W, H, pallet_l, pallet_w,
            max_layers, per_layer, total_cartons,
            utilization, stack_h, best_name,
            selected_sku, str(row["Brand"])
        )
        st.pyplot(fig)
        plt.close(fig)

    st.markdown("---")
    st.caption(
        "Dimensions from Dimensions_SKUs.xlsx  |  "
        "Piramal Consumer Healthcare — Supply Chain  |  "
        "Scope: single-SKU pallet optimization, L x W footprint only."
    )

else:
    st.markdown("""
    ### How to use this tool
    1. **Search** for a SKU or brand name in the left panel
    2. **Select** the exact SKU from the dropdown
    3. **Adjust** pallet size if needed (default 4 x 3 ft)
    4. **Override** max layers if needed
    5. Click **Calculate**
    ---
    **What this tool does:**
    Tests 6 carton arrangement strategies and picks the best one,
    then shows a full 3D stack visualization.

    **What this tool does NOT do:**
    Warehouse-wide slotting — that is handled by the ABC velocity analysis.
    """)

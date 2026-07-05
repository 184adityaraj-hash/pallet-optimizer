
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import rectpack

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

FILE_PATH        = "Dimensions_SKUs.xlsx"
DEFAULT_LAYERS   = 5
LOW_UTIL_WARN    = 60
STACK_HEIGHT_MAX = 10.0
BASE_COLORS = [
    "#1F3864","#2F5496","#2E75B6",
    "#2F8C82","#C8A165","#E8472A"
]

# ── Hidden toggle — change to True to show leftover details ──
SHOW_LEFTOVER_DETAILS = False

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
    cols = ["SKU_Name","Brand","L_ft","W_ft","H_ft","Max_Layers","Can_Stand"]
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

# ── 6 GRID STRATEGIES ────────────────────────────────────
def strategy_A(pl,pw,L,W): return int(pl//L)*int(pw//W)
def strategy_B(pl,pw,L,W): return int(pl//W)*int(pw//L)
def strategy_C(pl,pw,L,W):
    c=int(pl//L);r=int(pw//W)
    return c*r+int((pl-c*L)//W)*int(pw//L)
def strategy_D(pl,pw,L,W):
    c=int(pl//L);r=int(pw//W)
    return c*r+int(pl//W)*int((pw-r*W)//L)
def strategy_E(pl,pw,L,W):
    best=0
    for n in range(int(pw//W)+1):
        best=max(best,n*int(pl//L)+int((pw-n*W)//L)*int(pl//W))
    return best
def strategy_F(pl,pw,L,W):
    best=0
    for n in range(int(pl//L)+1):
        best=max(best,n*int(pw//W)+int((pl-n*L)//W)*int(pw//L))
    return best

def run_strategies(pl,pw,L,W):
    return {
        "A — All normal (L x W)"          : strategy_A(pl,pw,L,W),
        "B — All rotated (W x L)"         : strategy_B(pl,pw,L,W),
        "C — Guillotine split (length)"   : strategy_C(pl,pw,L,W),
        "D — Guillotine split (width)"    : strategy_D(pl,pw,L,W),
        "E — Row-by-row alternating"      : strategy_E(pl,pw,L,W),
        "F — Column-by-column alternate"  : strategy_F(pl,pw,L,W),
    }

# ── RECTPACK ─────────────────────────────────────────────
def run_rectpack(L,W,pl,pw):
    max_possible = int((pl*pw)/(L*W)) + 10
    packer = rectpack.newPacker(rotation=True)
    packer.add_bin(pl,pw)
    for _ in range(max_possible):
        packer.add_rect(L,W)
    packer.pack()
    try:
        placements = []
        for rect in packer[0]:
            placements.append({
                "x":float(rect.x),"y":float(rect.y),
                "w":float(rect.width),"h":float(rect.height),
                "rotated": abs(rect.width-W)<0.001
            })
        return len(placements), placements
    except:
        return 0, []

# ── LEFTOVER ANALYSIS (runs silently) ────────────────────
def get_orientations(L,W,H,can_stand):
    flat = [
        (L,W,H,"O1: Flat normal"),
        (W,L,H,"O2: Flat rotated"),
    ]
    side = [
        (L,H,W,"O3: Side long (L x H)"),
        (H,L,W,"O4: Side long (H x L)"),
        (W,H,L,"O5: Side short (W x H)"),
        (H,W,L,"O6: Side short (H x W)"),
    ]
    return flat + side if can_stand else flat

def analyze_leftover(L,W,H,pl,pw,per_layer,master_height,can_stand):
    cols_A=int(pl//L);rows_A=int(pw//W)
    cols_B=int(pl//W);rows_B=int(pw//L)
    if cols_A*rows_A >= cols_B*rows_B:
        cols,rows,cx,cy = cols_A,rows_A,L,W
    else:
        cols,rows,cx,cy = cols_B,rows_B,W,L
    rem_L = round(pl - cols*cx, 4)
    rem_W = round(pw - rows*cy, 4)
    orientations = get_orientations(L,W,H,can_stand)
    results = []
    for (base_l,base_w,carton_h,label) in orientations:
        if carton_h > master_height:
            results.append({"label":label,"total":0})
            continue
        stacks = int(master_height // carton_h)
        count_L = 0
        if rem_L > 0:
            for bl,bw in [(base_l,base_w),(base_w,base_l)]:
                if rem_L>=bl and pw>=bw:
                    count_L = max(count_L, int(rem_L//bl)*int(pw//bw)*stacks)
        count_W = 0
        if rem_W > 0:
            for bl,bw in [(base_l,base_w),(base_w,base_l)]:
                if pl>=bl and rem_W>=bw:
                    count_W = max(count_W, int(pl//bl)*int(rem_W//bw)*stacks)
        results.append({"label":label,"total":max(count_L,count_W)})
    results.sort(key=lambda x: x["total"], reverse=True)
    best_extra = results[0]["total"] if results else 0
    return best_extra, rem_L, rem_W, results

# ── 3D VISUALIZATION ─────────────────────────────────────
def draw_box(ax,x,y,z,dx,dy,dz,color,alpha=0.75,edge_color="black"):
    verts = [
        [(x,y,z),(x+dx,y,z),(x+dx,y+dy,z),(x,y+dy,z)],
        [(x,y,z+dz),(x+dx,y,z+dz),(x+dx,y+dy,z+dz),(x,y+dy,z+dz)],
        [(x,y,z),(x+dx,y,z),(x+dx,y,z+dz),(x,y,z+dz)],
        [(x,y+dy,z),(x+dx,y+dy,z),(x+dx,y+dy,z+dz),(x,y+dy,z+dz)],
        [(x,y,z),(x,y+dy,z),(x,y+dy,z+dz),(x,y,z+dz)],
        [(x+dx,y,z),(x+dx,y+dy,z),(x+dx,y+dy,z+dz),(x+dx,y,z+dz)],
    ]
    poly = Poly3DCollection(verts,alpha=alpha,
                            facecolor=color,
                            edgecolor=edge_color,
                            linewidth=0.4)
    ax.add_collection3d(poly)

def make_3d_figure(L,W,H,pl,pw,max_layers,per_layer,
                   total_cartons,utilization,stack_h,
                   strategy,sku_name,brand):
    cols_A=int(pl//L);rows_A=int(pw//W)
    cols_B=int(pl//W);rows_B=int(pw//L)
    if cols_A*rows_A >= cols_B*rows_B:
        cols,rows,cx,cy = cols_A,rows_A,L,W
    else:
        cols,rows,cx,cy = cols_B,rows_B,W,L
    GAP=0.012
    LEG_H=0.35
    LEG_W=0.18
    fig = plt.figure(figsize=(11,7))
    ax  = fig.add_subplot(111,projection="3d")
    for ly in [0.05, pw/2-LEG_W/2, pw-0.05-LEG_W]:
        draw_box(ax,0,ly,0,pl,LEG_W,LEG_H,
                 color="#8B6914",alpha=0.95,edge_color="#5C4A1E")
    z_start = LEG_H
    for layer in range(max_layers):
        z     = z_start + layer*H
        color = BASE_COLORS[layer % len(BASE_COLORS)]
        for col in range(cols):
            for row in range(rows):
                x = col*cx+GAP
                y = row*cy+GAP
                if x+cx-GAP<=pl+0.001 and y+cy-GAP<=pw+0.001:
                    draw_box(ax,x,y,z+GAP,
                             cx-GAP*2,cy-GAP*2,H-GAP,
                             color=color,alpha=0.75)
    pts=[[0,0],[pl,0],[pl,pw],[0,pw],[0,0]]
    ax.plot([p[0] for p in pts],[p[1] for p in pts],
            [z_start]*5,color="#E8472A",linewidth=2.5)
    total_h = z_start+stack_h
    if total_h > STACK_HEIGHT_MAX:
        for yp in [0,pw]:
            ax.plot([0,pl],[yp,yp],
                    [STACK_HEIGHT_MAX,STACK_HEIGHT_MAX],
                    color="red",linewidth=2.5,linestyle="--")
        ax.text(pl*0.2,pw*0.5,STACK_HEIGHT_MAX+0.1,
                "10ft LIMIT",color="red",fontsize=8,fontweight="bold")
    ax.set_xlabel("Length (ft)",fontsize=9,labelpad=6)
    ax.set_ylabel("Width (ft)",fontsize=9,labelpad=6)
    ax.set_zlabel("Height (ft)",fontsize=9,labelpad=6)
    ax.set_xlim(0,pl); ax.set_ylim(0,pw)
    ax.set_zlim(0,total_h+0.3)
    ax.set_title(
        f"{sku_name}  |  Brand: {brand}\n"
        f"Pallet: {pl}ft x {pw}ft   "
        f"Carton: {L:.3f} x {W:.3f} x {H:.3f} ft\n"
        f"Strategy: {strategy.strip()}   "
        f"{per_layer}/layer x {max_layers} layers "
        f"= {total_cartons} cartons   "
        f"Util: {utilization:.1f}%   "
        f"Stack: {stack_h:.2f}ft",
        fontsize=8,pad=12,color="#1F3864",fontweight="bold"
    )
    patches = [
        mpatches.Patch(color=BASE_COLORS[i%len(BASE_COLORS)],
                       label=f"Layer {i+1}")
        for i in range(min(max_layers,len(BASE_COLORS)))
    ]
    ax.legend(handles=patches,loc="upper left",
              fontsize=7,bbox_to_anchor=(0.0,1.0))
    ax.view_init(elev=28,azim=210)
    plt.tight_layout()
    return fig

# ── SIDEBAR ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔧 Inputs")
    st.markdown("---")
    st.markdown("**Search SKU**")
    search_term = st.text_input(
        "Type brand or product name",
        placeholder="e.g. Lacto, Saridon, CIR..."
    )
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
    col1,col2 = st.columns(2)
    with col1:
        pallet_l = st.number_input("Length",value=4.0,
                                   min_value=0.5,step=0.5)
    with col2:
        pallet_w = st.number_input("Width",value=3.0,
                                   min_value=0.5,step=0.5)
    st.markdown("---")
    st.markdown("**Max Layers Override**")
    override_layers = st.number_input(
        "Leave 0 to use value from file",
        value=0,min_value=0,max_value=30,step=1)
    st.markdown("---")
    calculate = st.button("🚀 Calculate",
                          use_container_width=True,
                          type="primary")

# ── MAIN AREA ────────────────────────────────────────────
if calculate:
    if selected_sku is None:
        st.error("Please search and select a SKU first.")
        st.stop()

    row = df[df["SKU_Name"] == selected_sku].iloc[0]
    L   = float(row["L_ft"])
    W   = float(row["W_ft"])
    H   = float(row["H_ft"])

    # Can stand on side — from file, silent
    raw_val = str(row.get("Can_Stand","")).strip().lower()
    can_stand = (raw_val == "yes")

    # Max layers
    if override_layers > 0:
        max_layers   = override_layers
        layer_source = "manually overridden"
    elif pd.notna(row["Max_Layers"]):
        max_layers   = int(row["Max_Layers"])
        layer_source = "from data file"
    else:
        max_layers   = DEFAULT_LAYERS
        layer_source = f"default ({DEFAULT_LAYERS})"

    # Validate
    errors = []
    if L > pallet_l and W > pallet_l:
        errors.append("Carton wider than pallet in both orientations.")
    if W > pallet_w and L > pallet_w:
        errors.append("Carton deeper than pallet in both orientations.")
    if errors:
        for e in errors:
            st.error(f"❌ {e}")
        st.stop()

    # ── RUN MODEL ────────────────────────────────────────
    # 1. Grid strategies
    strategies   = run_strategies(pallet_l, pallet_w, L, W)
    best_name    = max(strategies, key=strategies.get)
    best_grid    = strategies[best_name]

    # 2. Rectpack
    rpack_count, rpack_placements = run_rectpack(L, W, pallet_l, pallet_w)

    # 3. Best main block
    if rpack_count > best_grid:
        per_layer   = rpack_count
        method_used = f"Rectpack (+{rpack_count-best_grid} vs grid)"
    else:
        per_layer   = best_grid
        method_used = best_name.strip()

    if per_layer == 0:
        st.error("Zero cartons fit — carton may be too large for pallet.")
        st.stop()

    # 4. Totals
    master_height = round(H * max_layers, 4)
    total_cartons = per_layer * max_layers
    stack_h       = master_height

    # 5. Leftover (silent — just get extra count)
    extra_cartons, rem_L, rem_W, leftover_details = analyze_leftover(
        L, W, H, pallet_l, pallet_w,
        per_layer, master_height, can_stand
    )
    grand_total = total_cartons + extra_cartons

    # Utilization
    carton_vol  = L * W * H
    pallet_vol  = pallet_l * pallet_w * stack_h
    utilization = (carton_vol * total_cartons / pallet_vol) * 100

    # ── DISPLAY ──────────────────────────────────────────
    st.markdown(f"## Results — {selected_sku}")
    st.markdown(
        f"**Brand:** {row['Brand']}  |  "
        f"**Carton:** {L:.3f} x {W:.3f} x {H:.3f} ft  |  "
        f"**Max layers:** {max_layers} ({layer_source})"
    )
    st.markdown("---")

    # 6 KPI cards
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    k1.metric("Cartons per Layer", per_layer)
    k2.metric("Main Block Total",  total_cartons)
    k3.metric("Leftover Extra",    extra_cartons,
              delta=f"+{extra_cartons}" if extra_cartons > 0 else None)
    k4.metric("Grand Total",       grand_total,
              delta=f"+{extra_cartons} vs main" if extra_cartons > 0 else None)
    k5.metric("Space Utilization", f"{utilization:.1f}%")
    k6.metric("Stack Height",      f"{stack_h:.2f} ft")

    # Warnings
    if utilization < LOW_UTIL_WARN:
        st.warning(f"⚠️ Low utilization ({utilization:.1f}%) — "
                   f"verify dimensions physically.")
    if stack_h > STACK_HEIGHT_MAX:
        st.error(f"⚠️ Stack {stack_h:.2f}ft exceeds 10ft limit — "
                 f"reduce max layers.")

    st.markdown("---")

    # Strategy table + 3D side by side
    left, right = st.columns([1, 1.6])

    with left:
        st.markdown("### 📊 Strategy Comparison")
        strat_rows = []
        for name, count in strategies.items():
            strat_rows.append({
                "Strategy"  : name,
                "Per Layer" : count,
                "Best"      : "✅" if name == best_name and
                              rpack_count <= best_grid else ""
            })
        # Add rectpack row
        strat_rows.append({
            "Strategy"  : "Rectpack (bin-packing)",
            "Per Layer" : rpack_count,
            "Best"      : "✅" if rpack_count > best_grid else ""
        })
        strat_df = pd.DataFrame(strat_rows)
        st.dataframe(strat_df, hide_index=True,
                     use_container_width=True)
        st.success(f"**Best method:** {method_used}  →  "
                   f"**{per_layer} cartons/layer**")
        if extra_cartons > 0:
            st.info(f"💡 **+{extra_cartons} extra cartons** found "
                    f"in leftover pallet space  →  "
                    f"**Grand Total: {grand_total}**")

    with right:
        st.markdown("### 🧊 3D Pallet Visualization")
        fig = make_3d_figure(
            L,W,H,pallet_l,pallet_w,
            max_layers,per_layer,total_cartons,
            utilization,stack_h,method_used,
            selected_sku,str(row["Brand"])
        )
        st.pyplot(fig)
        plt.close(fig)

    # Leftover details — hidden by default
    if SHOW_LEFTOVER_DETAILS:
        st.markdown("---")
        st.markdown("### 📐 Leftover Space Analysis")
        st.write(f"Length strip: {rem_L:.3f} ft | "
                 f"Width strip: {rem_W:.3f} ft")
        ldf = pd.DataFrame(leftover_details)
        st.dataframe(ldf, hide_index=True)

    st.markdown("---")
    st.caption(
        "Dimensions from Dimensions_SKUs.xlsx  |  "
        "Piramal Consumer Healthcare — Supply Chain  |  "
        "Scope: single-SKU pallet optimization, L x W footprint. "
        "Leftover space optimization runs silently."
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
    Tests 6 carton arrangement strategies + rectpack bin-packing
    algorithm, picks the best one, then silently optimizes leftover
    pallet space using all possible orientations.
    Shows a full 3D stack visualization.

    **What this tool does NOT do:**
    Warehouse-wide slotting — handled separately by ABC velocity analysis.
    """)

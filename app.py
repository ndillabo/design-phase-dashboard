import streamlit as st
import pandas as pd
import plotly.express as px
import datetime as dt
import smartsheet

# --- Streamlit page config ---
st.set_page_config(layout="wide")
st.title("📊 Design Phase Dashboard")
st.caption("Use the sidebar to search, sort, and toggle various features.")

# --- Smartsheet Setup ---
SMartsheet_TOKEN = st.secrets["SMartsheet_TOKEN"]
SHEET_ID = st.secrets["SHEET_ID"]

def fetch_smartsheet_data():
    client = smartsheet.Smartsheet(SMartsheet_TOKEN)
    sheet = client.Sheets.get_sheet(SHEET_ID)
    col_map = {col.title: col.id for col in sheet.columns}
    rows = []
    for row in sheet.rows:
        d = {}
        for cell in row.cells:
            if cell.column_id in col_map.values():
                title = next(k for k, v in col_map.items() if v == cell.column_id)
                d[title] = cell.value
        rows.append(d)
    return pd.DataFrame(rows)

# --- Fetch & preprocess ---
df = fetch_smartsheet_data()
date_cols = [
    "Programming Start Date","Schematic Design Start Date",
    "Design Development Start Date","Construction Document Start Date",
    "Permit Set Delivery Date"
]
for c in date_cols:
    df[c] = pd.to_datetime(df[c], errors="coerce")

# Must have these columns
if "Design Manager Name" not in df.columns or "Project #" not in df.columns:
    st.error("Missing column 'Design Manager Name' or 'Project #' in Smartsheet.")
    st.stop()

# --- Sidebar controls ---
st.sidebar.header("🔍 Search & Sort")
search_name = st.sidebar.text_input("Search Project Name")
search_num  = st.sidebar.text_input("Search Project Number")
search_mgr  = st.sidebar.text_input("Search Design Manager")

sort_by = st.sidebar.selectbox("Sort Projects By", [
    "Design Manager","Project Name","Programming Start Date","Project Number"
])

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Options")
show_active  = st.sidebar.checkbox("Show Only Active Today", value=False)
color_theme  = st.sidebar.selectbox("Color Theme", ["ASU Brand","High Contrast"])
jump_to      = "-- None --"  # placeholder

# --- Filter df ---
df_f = df.copy()
if search_name:
    df_f = df_f[df_f["Project Name"].str.contains(search_name, case=False, na=False)]
if search_num:
    df_f = df_f[df_f["Project #"].astype(str).str.contains(search_num, na=False)]
if search_mgr:
    df_f = df_f[df_f["Design Manager Name"].str.contains(search_mgr, case=False, na=False)]

# mark “Active Today”
today = pd.to_datetime(dt.date.today())
df_f["Active Today"] = False
for i, r in df_f.iterrows():
    for start, end in [
        (r["Programming Start Date"], r["Schematic Design Start Date"]),
        (r["Schematic Design Start Date"], r["Design Development Start Date"]),
        (r["Design Development Start Date"], r["Construction Document Start Date"]),
        (r["Construction Document Start Date"], r["Permit Set Delivery Date"])
    ]:
        if pd.notnull(start) and pd.notnull(end) and start <= today < end:
            df_f.at[i, "Active Today"] = True
            break
if show_active:
    df_f = df_f[df_f["Active Today"]]

# --- Sort df_f ---
if sort_by == "Design Manager":
    df_f = df_f.sort_values(["Design Manager Name","Project Name"])
elif sort_by == "Project Name":
    df_f = df_f.sort_values("Project Name")
elif sort_by == "Programming Start Date":
    df_f = df_f.sort_values("Programming Start Date")
else:
    df_f["Num"] = pd.to_numeric(df_f["Project #"], errors="coerce")
    df_f = df_f.sort_values("Num").drop(columns="Num")

# --- Build long DataFrame for timeline ---
records = []
for _, r in df_f.iterrows():
    num = r["Project #"]
    if pd.notnull(num) and str(num).replace(".","",1).isdigit():
        label = f"{r['Project Name']} ({int(num)}) — {r['Design Manager Name']}"
    else:
        label = f"{r['Project Name']} ({num}) — {r['Design Manager Name']}"
    for phase, s_col, e_col in [
        ("Programming","Programming Start Date","Schematic Design Start Date"),
        ("Schematic Design","Schematic Design Start Date","Design Development Start Date"),
        ("Design Development","Design Development Start Date","Construction Document Start Date"),
        ("Construction Documents","Construction Document Start Date","Permit Set Delivery Date")
    ]:
        s = r[s_col]; e = r[e_col]
        if pd.notnull(s) and pd.notnull(e):
            records.append({"Project": label, "Phase": phase, "Start": s, "Finish": e})
long_df = pd.DataFrame(records)
if long_df.empty:
    st.info("No matching data after filters.")
    st.stop()

# ```` Jump to Project
projects = long_df["Project"].unique().tolist()
jump_to = st.sidebar.selectbox("Jump to Project", ["-- None --"] + projects)
if jump_to != "-- None --":
    ordered = [jump_to] + [p for p in projects if p != jump_to]
    long_df["Project"] = pd.Categorical(long_df["Project"], categories=ordered, ordered=True)
    long_df = long_df.sort_values("Project")

# --- Summary metrics ---
active_count = df_f[df_f["Active Today"]]["Project Name"].nunique()
phase_ct = {ph:0 for ph in ["Programming","Schematic Design","Design Development","Construction Documents"]}
for _, r in df_f[df_f["Active Today"]].iterrows():
    for ph, s_col, e_col in [
        ("Programming","Programming Start Date","Schematic Design Start Date"),
        ("Schematic Design","Schematic Design Start Date","Design Development Start Date"),
        ("Design Development","Design Development Start Date","Construction Document Start Date"),
        ("Construction Documents","Construction Document Start Date","Permit Set Delivery Date")
    ]:
        s = r[s_col]; e = r[e_col]
        if pd.notnull(s) and pd.notnull(e) and s <= today < e:
            phase_ct[ph] += 1
            break

st.markdown("### 📈 Summary")
c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Total Projects", df_f["Project Name"].nunique())
c2.metric("Active Today", active_count)
c3.metric("In Programming", phase_ct["Programming"])
c4.metric("In Schematic", phase_ct["Schematic Design"])
c5.metric("In Design Development", phase_ct["Design Development"])
c6.metric("In CD Phase", phase_ct["Construction Documents"])

# --- Timeline plot ---
sy = long_df["Start"].min().year
ey = long_df["Finish"].max().year

pal = {
    "ASU Brand":{"Programming":"#8C1D40","Schematic Design":"#FFC627","Design Development":"#5C6670","Construction Documents":"#78BE20"},
    "High Contrast":{"Programming":"#004D40","Schematic Design":"#F57F17","Design Development":"#283593","Construction Documents":"#D32F2F"}
}[color_theme]

fig = px.timeline(long_df, x_start="Start", x_end="Finish", y="Project",
                  color="Phase", color_discrete_map=pal,
                  hover_data={"Start":"|%b %d, %Y","Finish":"|%b %d, %Y"})
fig.update_yaxes(autorange="reversed")

# alternating shading
shapes = []
for yr in range(sy, ey + 1):
    if yr % 2 == 0:
        shapes.append(
            dict(
                type="rect",
                xref="x",
                yref="paper",
                x0=dt.datetime(yr, 1, 1),
                x1=dt.datetime(yr + 1, 1, 1),
                y0=0,
                y1=1,
                fillcolor="#d3d3d3",   # soft medium-light gray
                opacity=0.25,          # slightly lighter than before
                layer="below",
                line_width=0,
            )
        )
fig.update_layout(shapes=shapes)

# today line
fig.add_vline(x=today, line_color=pal["Programming"], line_width=3)
fig.update_layout(dragmode="pan")

# layout
n = len(projects)
fig.update_layout(
    height=40*n+200,
    title_text="Project Design Phases Timeline", title_font_size=26,
    xaxis=dict(tickformat="%b %Y", dtick="M1", tickangle=45, tickfont_size=14,
               showgrid=True, gridcolor="lightgray"),
    margin=dict(l=300, r=50, t=80, b=80),
    legend=dict(font_size=16, orientation="h", y=1.02, x=1, xanchor="right")
)

# --- Config: default buttons + fullscreen, always visible ---
config = {
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["select2d", "lasso2d"],
    "modeBarButtonsToAdd": ["toggleFullScreen"],
    "modeBarButtonSize": 26
}

st.plotly_chart(fig, use_container_width=True, config=config)

# --- Add New Project link ---
st.markdown("---")
st.markdown("### Want to add a new project to the dashboard?")
st.markdown(
    "[📝 Add New Project](https://app.smartsheet.com/b/form/a441de84912b4f27a5f2c59512d70897)",
    unsafe_allow_html=True
)

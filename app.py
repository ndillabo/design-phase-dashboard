import streamlit as st
import pandas as pd
import plotly.express as px
import datetime as dt
import smartsheet

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
                title = next(k for k,v in col_map.items() if v==cell.column_id)
                d[title] = cell.value
        rows.append(d)
    return pd.DataFrame(rows)

# --- Fetch & Preprocess Data ---
df = fetch_smartsheet_data()

# Convert date fields
for fld in ["Programming Start Date","Schematic Design Start Date",
            "Design Development Start Date","Construction Document Start Date",
            "Permit Set Delivery Date"]:
    df[fld] = pd.to_datetime(df[fld], errors="coerce")

if "Design Manager Name" not in df.columns or "Project #" not in df.columns:
    st.error("Required columns missing.")
    st.stop()

# --- Sidebar: Search & Sort ---
st.sidebar.header("🔍 Search & Sort")
sn = st.sidebar.text_input("Search Project Name","")
snum = st.sidebar.text_input("Search Project Number","")
sdm = st.sidebar.text_input("Search Design Manager","")
sort_by = st.sidebar.selectbox("Sort Projects By",
    ["Design Manager","Project Name","Programming Start Date","Project Number"])
st.sidebar.markdown("---")
st.sidebar.header("⚙️ Options")
show_active = st.sidebar.checkbox("Show Only Active Today", False)
color_theme = st.sidebar.selectbox("Color Theme",["ASU Brand","High Contrast"])

# --- Filtering ---
df_f = df.copy()
if sn: df_f = df_f[df_f["Project Name"].str.contains(sn, case=False, na=False)]
if snum: df_f = df_f[df_f["Project #"].astype(str).str.contains(snum, na=False)]
if sdm: df_f = df_f[df_f["Design Manager Name"].str.contains(sdm, case=False, na=False)]

# Active-today helper
today = pd.to_datetime(dt.date.today())
df_f["Active Today"] = False
for i,row in df_f.iterrows():
    for s,e in [
        (row["Programming Start Date"], row["Schematic Design Start Date"]),
        (row["Schematic Design Start Date"], row["Design Development Start Date"]),
        (row["Design Development Start Date"], row["Construction Document Start Date"]),
        (row["Construction Document Start Date"], row["Permit Set Delivery Date"])
    ]:
        if pd.notnull(s) and pd.notnull(e) and s<=today<e:
            df_f.at[i,"Active Today"] = True
            break
if show_active:
    df_f = df_f[df_f["Active Today"]]

# Sort
if sort_by=="Design Manager":
    df_f = df_f.sort_values(["Design Manager Name","Project Name"])
elif sort_by=="Project Name":
    df_f = df_f.sort_values("Project Name")
elif sort_by=="Programming Start Date":
    df_f = df_f.sort_values("Programming Start Date")
else:
    df_f["Num"] = pd.to_numeric(df_f["Project #"], errors="coerce")
    df_f = df_f.sort_values("Num").drop(columns="Num")

# --- Build long DataFrame ---
records=[]
for _,r in df_f.iterrows():
    num=r["Project #"]
    lbl=f"{r['Project Name']} ({int(num) if pd.notnull(num) and str(num).replace('.','',1).isdigit() else num}) — {r['Design Manager Name']}"
    for phase,s,e in [
        ("Programming", r["Programming Start Date"], r["Schematic Design Start Date"]),
        ("Schematic Design", r["Schematic Design Start Date"], r["Design Development Start Date"]),
        ("Design Development", r["Design Development Start Date"], r["Construction Document Start Date"]),
        ("Construction Documents", r["Construction Document Start Date"], r["Permit Set Delivery Date"])
    ]:
        if pd.notnull(s) and pd.notnull(e):
            records.append(dict(Project=lbl, Phase=phase, Start=s, Finish=e))
long_df = pd.DataFrame(records)
if long_df.empty:
    st.info("No matching data.")
    st.stop()

# Jump-to
projects = long_df["Project"].unique().tolist()
jump = st.sidebar.selectbox("Jump to Project", ["-- None --"]+projects)
if jump!="-- None --":
    order=[jump]+[p for p in projects if p!=jump]
    long_df["Project"]=pd.Categorical(long_df["Project"],categories=order,ordered=True)
    long_df=long_df.sort_values("Project")

# --- Summary ---
active_cnt=df_f[df_f["Active Today"]]["Project Name"].nunique()
phases={"Programming":0,"Schematic Design":0,"Design Development":0,"Construction Documents":0}
for _,r in df_f[df_f["Active Today"]].iterrows():
    for phase,s,e in [
        ("Programming", r["Programming Start Date"], r["Schematic Design Start Date"]),
        ("Schematic Design", r["Schematic Design Start Date"], r["Design Development Start Date"]),
        ("Design Development", r["Design Development Start Date"], r["Construction Document Start Date"]),
        ("Construction Documents", r["Construction Document Start Date"], r["Permit Set Delivery Date"])
    ]:
        if pd.notnull(s) and pd.notnull(e) and s<=today<e:
            phases[phase]+=1
            break

st.markdown("### 📈 Summary")
c1,c2,c3,c4,c5,c6=st.columns(6)
c1.metric("Total Projects",df_f["Project Name"].nunique())
c2.metric("Active Today",active_cnt)
c3.metric("In Programming",phases["Programming"])
c4.metric("In Schematic",phases["Schematic Design"])
c5.metric("In Design Development",phases["Design Development"])
c6.metric("In CD Phase",phases["Construction Documents"])

# --- Plot ---
start=min(long_df["Start"])
end=max(long_df["Finish"])
sy,ey=start.year,end.year
theme_colors = {
    "ASU Brand":{"Programming":"#8C1D40","Schematic Design":"#FFC627","Design Development":"#5C6670","Construction Documents":"#78BE20"},
    "High Contrast":{"Programming":"#004D40","Schematic Design":"#F57F17","Design Development":"#283593","Construction Documents":"#D32F2F"}
}[color_theme]

fig = px.timeline(long_df, x_start="Start", x_end="Finish", y="Project",
                  color="Phase", color_discrete_map=theme_colors,
                  hover_data={"Start":"|%b %d, %Y","Finish":"|%b %d, %Y"})
fig.update_yaxes(autorange="reversed")

# Alternating shading
shapes=[]
for yr in range(sy, ey+1):
    if yr%2==0:
        shapes.append(dict(type="rect",xref="x",yref="paper",
                           x0=dt.datetime(yr,1,1),x1=dt.datetime(yr+1,1,1),
                           y0=0,y1=1,fillcolor="lightgray",opacity=0.2,layer="below",line_width=0))
fig.update_layout(shapes=shapes)

# Today line
fig.add_vline(x=today, line_color=theme_colors["Programming"], line_width=3)

# Layout tweaks
n=len(projects)
fig.update_layout(
    height=40*n+200,
    title_text="Project Design Phases Timeline", title_font_size=26,
    xaxis=dict(tickformat="%b %Y",dtick="M1",tickangle=45,tickfont_size=14,showgrid=True,gridcolor="lightgray"),
    margin=dict(l=300,r=50,t=80,b=80),
    legend=dict(font_size=16,orientation="h",y=1.02,x=1,xanchor="right"),
    dragmode="pan"
)

# Modebar: default buttons + fullscreen, always visible
config = {
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtons": [["toggleFullScreen","pan2d","zoom2d","zoomIn2d","zoomOut2d","resetScale2d","hoverClosestCartesian"]],
    "modeBarButtonSize": 26,
    "watermark": False
}

st.plotly_chart(fig, use_container_width=True, config=config)

# Add new project link
st.markdown("---")
st.markdown("### Want to add a new project to the dashboard?")
st.markdown("[📝 Add New Project](https://app.smartsheet.com/b/form/a441de84912b4f27a5f2c59512d70897)", unsafe_allow_html=True)

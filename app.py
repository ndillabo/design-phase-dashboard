import streamlit as st
import pandas as pd
import datetime as dt
import smartsheet
import plotly.graph_objects as go

# --- Smartsheet Setup ---
SMartsheet_TOKEN = st.secrets["SMartsheet_TOKEN"]
SHEET_ID = st.secrets["SHEET_ID"]

@st.cache_data(ttl=3600)
def fetch_smartsheet_data():
    client = smartsheet.Smartsheet(SMartsheet_TOKEN)
    sheet = client.Sheets.get_sheet(SHEET_ID)

    col_map = {col.title: col.id for col in sheet.columns}
    data = []
    for row in sheet.rows:
        row_dict = {}
        for cell in row.cells:
            for key, val in col_map.items():
                if cell.column_id == val:
                    row_dict[key] = cell.value
        data.append(row_dict)
    return pd.DataFrame(data)

# --- App UI ---
st.set_page_config(layout="wide")
st.title("📊 Design Phase Dashboard")
st.caption("Filter, hover, and download data. Auto-refreshes every hour.")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()

df = fetch_smartsheet_data()

# --- Preprocessing ---
date_fields = [
    "Programming Start Date", "Schematic Design Start Date",
    "Design Development Start Date", "Construction Document Start Date",
    "Permit Set Delivery Date"
]
for field in date_fields:
    df[field] = pd.to_datetime(df[field], errors='coerce')

df['Programming End'] = df["Schematic Design Start Date"]
df['Schematic Design End'] = df["Design Development Start Date"]
df['Design Development End'] = df["Construction Document Start Date"]
df['Construction Document End'] = df["Permit Set Delivery Date"]

# --- Phase Setup ---
phases = ['Programming', 'Schematic Design', 'Design Development', 'Construction Documents']
colors = {
    'Programming': '#d62728',              # Red
    'Schematic Design': '#1f77b4',         # Blue
    'Design Development': '#ff7f0e',       # Orange
    'Construction Documents': '#2ca02c'    # Green
}

# --- Filters ---
with st.sidebar:
    st.header("🔍 Filter Projects")
    managers = df["Design Manager"].dropna().unique().tolist()
    selected_managers = st.multiselect("Design Manager", options=managers, default=managers)

    project_names = df["Project Name"].dropna().unique().tolist()
    selected_projects = st.multiselect("Project Name", options=project_names, default=project_names)

# Apply filters
df = df[df["Design Manager"].isin(selected_managers) & df["Project Name"].isin(selected_projects)].reset_index(drop=True)

# --- Plotly Gantt-style Chart ---
fig = go.Figure()
today = dt.datetime.today()
asu_maroon = '#891D40'

for i, row in df.iterrows():
    y = row["Project Name"] or f"Project {i+1}"
    phases_data = [
        ("Programming", row["Programming Start Date"], row["Programming End"]),
        ("Schematic Design", row["Schematic Design Start Date"], row["Schematic Design End"]),
        ("Design Development", row["Design Development Start Date"], row["Design Development End"]),
        ("Construction Documents", row["Construction Document Start Date"], row["Construction Document End"])
    ]
    for phase_name, start, end in phases_data:
        if pd.notnull(start) and pd.notnull(end):
            fig.add_trace(go.Bar(
                x=[(end - start).days],
                y=[y],
                base=start,
                orientation='h',
                marker=dict(color=colors[phase_name]),
                name=phase_name,
                hovertemplate=f"<b>{phase_name}</b><br>Start: {start.date()}<br>End: {end.date()}<br>Duration: {(end - start).days} days<br>Project: {y}<extra></extra>"
            ))

# --- Add Today Line ---
fig.add_shape(
    type="line",
    x0=today, x1=today,
    y0=-0.5, y1=len(df)-0.5,
    line=dict(color=asu_maroon, width=2),
    name="Today"
)

# --- Layout ---
fig.update_layout(
    barmode='stack',
    title="Project Design Phases Timeline",
    xaxis_title="Date",
    yaxis=dict(autorange="reversed"),
    legend_title="Phase",
    height=40 + len(df) * 40,
    shapes=[dict(
        type="line", x0=today, x1=today, y0=-0.5, y1=len(df)-0.5,
        line=dict(color=asu_maroon, width=2)
    )],
    margin=dict(l=150, r=50, t=50, b=50)
)

st.plotly_chart(fig, use_container_width=True)

# --- Export Button ---
st.markdown("### 📤 Export Filtered Data")
csv = df.to_csv(index=False)
st.download_button(
    label="Download CSV",
    data=csv,
    file_name="filtered_projects.csv",
    mime="text/csv"
)

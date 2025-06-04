import streamlit as st
import pandas as pd
import plotly.express as px
import smartsheet

# 1) Fetch your Smartsheet data (same as before)
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
            for title, cid in col_map.items():
                if cell.column_id == cid:
                    d[title] = cell.value
        rows.append(d)
    return pd.DataFrame(rows)

df = fetch_smartsheet_data()

# 2) Convert date fields to datetime
for fld in [
    "Programming Start Date",
    "Schematic Design Start Date",
    "Design Development Start Date",
    "Construction Document Start Date",
    "Permit Set Delivery Date",
]:
    df[fld] = pd.to_datetime(df[fld], errors="coerce")

# 3) Build a “long” DataFrame for Plotly:
#    Each row = one phase of one project. Contains: Project Name, Phase, Start, End
records = []
for _, row in df.iterrows():
    pname = f"{row['Project Name']} ({int(row['Project #'])})"
    phases = [
        ("Programming", row["Programming Start Date"], row["Schematic Design Start Date"]),
        ("Schematic Design", row["Schematic Design Start Date"], row["Design Development Start Date"]),
        ("Design Development", row["Design Development Start Date"], row["Construction Document Start Date"]),
        ("Construction Documents", row["Construction Document Start Date"], row["Permit Set Delivery Date"]),
    ]
    for phase_name, start_dt, end_dt in phases:
        if pd.notnull(start_dt) and pd.notnull(end_dt):
            records.append({
                "Project": pname,
                "Phase": phase_name,
                "Start": start_dt,
                "Finish": end_dt
            })

long_df = pd.DataFrame.from_records(records)

# 4) Use Plotly Express timeline() – it’s interactive by default
colors = {
    "Programming": "#8C1D40", 
    "Schematic Design": "#FFC627", 
    "Design Development": "#5C6670", 
    "Construction Documents": "#78BE20"
}

fig = px.timeline(
    long_df,
    x_start="Start",
    x_end="Finish",
    y="Project",
    color="Phase",
    color_discrete_map=colors,
)

# In Plotly Express, the y-axis is sorted descending by default; invert if you want earliest on top
fig.update_yaxes(autorange="reversed")

# Add “Today” line
today = pd.to_datetime(dt.date.today())
fig.add_vline(
    x=today, 
    line_color="#8C1D40", 
    line_width=3, 
    annotation_text="Today", 
    annotation_position="top right",
)

# Format X-axis to show month/year, and alternate shading if desired
fig.update_layout(
    height=ROW_HEIGHT_PX * len(df) + 200,   # same per‐row pixel height approach
    title_text="Project Design Phases Timeline",
    title_font_size=26,
    legend_title_text="Phase",
    xaxis=dict(
        tickformat="%b %Y",
        dtick="M1",            # one‐month tick interval
        tickangle=45,
    ),
    margin=dict(l=300, r=50, t=80, b=80),  # left margin to see entire y labels
)

# 5) Simply show it in Streamlit – it’s scrollable/pannable by default
st.plotly_chart(fig, use_container_width=True)

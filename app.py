import streamlit as st
import pandas as pd
import plotly.express as px
import datetime as dt
import smartsheet

# --- Smartsheet Setup ---
SMartsheet_TOKEN = st.secrets["SMartsheet_TOKEN"]
SHEET_ID = st.secrets["SHEET_ID"]

def fetch_smartsheet_data():
    client = smartsheet.Smartsheet(SMartsheet_TOKEN)
    sheet = client.Sheets.get_sheet(SHEET_ID)
    col_map = {col.title: col.id for col in sheet.columns}
    data = []
    for row in sheet.rows:
        row_dict = {}
        for cell in row.cells:
            if cell.column_id in col_map.values():
                title = next(k for k, v in col_map.items() if v == cell.column_id)
                row_dict[title] = cell.value
        data.append(row_dict)
    return pd.DataFrame(data)

st.set_page_config(layout="wide")
st.title("📊 Design Phase Dashboard")
st.caption("Use the sidebar to search and sort projects.")

# --- Fetch & Preprocess Data ---
df = fetch_smartsheet_data()

# Convert Smartsheet date fields to datetime
for fld in [
    "Programming Start Date",
    "Schematic Design Start Date",
    "Design Development Start Date",
    "Construction Document Start Date",
    "Permit Set Delivery Date",
]:
    df[fld] = pd.to_datetime(df[fld], errors="coerce")

# Ensure “Design Manager Name” exists
if "Design Manager Name" not in df.columns:
    st.error("Column 'Design Manager Name' not found in your Smartsheet data.")
    st.stop()

# Sidebar: Search & Sort Controls
st.sidebar.header("🔍 Search & Sort")

# 1) Search by Project Name (substring, case-insensitive)
search_project_name = st.sidebar.text_input("Search Project Name", value="")

# 2) Search by Project Number (substring)
search_project_number = st.sidebar.text_input("Search Project Number", value="")

# 3) Search by Design Manager (substring, case-insensitive)
search_design_manager = st.sidebar.text_input("Search Design Manager", value="")

# 4) Sort Order
sort_option = st.sidebar.selectbox(
    "Sort Projects By",
    options=["Design Manager", "Project Name", "Programming Start Date"]
)

# --- Apply Filters ---
df_filtered = df.copy()

# Filter: Project Name
if search_project_name.strip():
    df_filtered = df_filtered[df_filtered["Project Name"].str.contains(
        search_project_name.strip(), case=False, na=False
    )]

# Filter: Project Number
if search_project_number.strip():
    df_filtered = df_filtered[df_filtered["Project #"].astype(str).str.contains(
        search_project_number.strip(), na=False
    )]

# Filter: Design Manager Name
if search_design_manager.strip():
    df_filtered = df_filtered[df_filtered["Design Manager Name"].str.contains(
        search_design_manager.strip(), case=False, na=False
    )]

# --- Apply Sort Order ---
if sort_option == "Design Manager":
    df_filtered["Project # Sort"] = df_filtered["Project #"].astype(str)
    df_filtered = df_filtered.sort_values(
        by=["Design Manager Name", "Project # Sort"], ascending=[True, True]
    ).reset_index(drop=True)
elif sort_option == "Project Name":
    df_filtered = df_filtered.sort_values(
        by=["Project Name", "Project #"], ascending=[True, True]
    ).reset_index(drop=True)
else:  # "Programming Start Date"
    df_filtered = df_filtered.sort_values(
        by=["Programming Start Date"], ascending=True
    ).reset_index(drop=True)

# Build a “long” DataFrame for Plotly’s timeline: one row per Project‐Phase
records = []
for _, row in df_filtered.iterrows():
    # Construct "Project Name (Project #)" label
    if pd.notnull(row.get("Project #")) and str(row["Project #"]).replace(".", "", 1).isdigit():
        pname = f"{row['Project Name']} ({int(row['Project #'])})"
    elif pd.notnull(row.get("Project #")):
        pname = f"{row['Project Name']} ({row['Project #']})"
    else:
        pname = row["Project Name"]

    # Append the Design Manager name
    full_label = f"{pname} — {row['Design Manager Name']}"

    # Define each of the four phases with start & end
    phases = [
        ("Programming", row["Programming Start Date"], row["Schematic Design Start Date"]),
        ("Schematic Design", row["Schematic Design Start Date"], row["Design Development Start Date"]),
        ("Design Development", row["Design Development Start Date"], row["Construction Document Start Date"]),
        ("Construction Documents", row["Construction Document Start Date"], row["Permit Set Delivery Date"]),
    ]
    for phase_name, start_dt, end_dt in phases:
        if pd.notnull(start_dt) and pd.notnull(end_dt):
            records.append({
                "Project": full_label,
                "Phase": phase_name,
                "Start": start_dt,
                "Finish": end_dt
            })

long_df = pd.DataFrame.from_records(records)

# If no data after applying filters, show a message and exit
if long_df.empty:
    st.info("No data matches your search criteria.")
    st.stop()

# ASU brand colors
colors = {
    "Programming": "#8C1D40",
    "Schematic Design": "#FFC627",
    "Design Development": "#5C6670",
    "Construction Documents": "#78BE20"
}

distinct_projects = long_df["Project"].unique().tolist()
n_projects = len(distinct_projects)

overall_min = long_df["Start"].min()
overall_max = long_df["Finish"].max()
start_year = overall_min.year
end_year = overall_max.year

# Build Plotly timeline
fig = px.timeline(
    long_df,
    x_start="Start",
    x_end="Finish",
    y="Project",
    color="Phase",
    color_discrete_map=colors,
)

# Reverse y-axis so earliest project is at the top
fig.update_yaxes(autorange="reversed")

# Add alternating even-year shading
shapes = []
for year in range(start_year, end_year + 1):
    if year % 2 == 0:
        x0 = dt.datetime(year, 1, 1)
        x1 = dt.datetime(year + 1, 1, 1)
        shapes.append(
            dict(
                type="rect",
                xref="x",
                yref="paper",
                x0=x0,
                x1=x1,
                y0=0,
                y1=1,
                fillcolor="lightgray",
                opacity=0.2,
                layer="below",
                line_width=0,
            )
        )
fig.update_layout(shapes=shapes)

# Add “Today” vertical line (ASU maroon)
today = pd.to_datetime(dt.date.today())
fig.add_vline(
    x=today,
    line_color="#8C1D40",
    line_width=3
)

# Layout: X-axis at bottom with monthly gridlines, vertical panning allowed
fig.update_layout(
    height=40 * n_projects + 200,        # 40px per project row + padding
    title_text="Project Design Phases Timeline",
    title_font_size=26,
    legend_title_text="Phase",
    xaxis=dict(
        side="bottom",                   # place X-axis below
        tickformat="%b %Y",
        dtick="M1",                      # monthly ticks
        tickangle=45,
        tickfont=dict(size=14),
        showgrid=True,
        gridcolor="lightgrey",
        gridwidth=1,
    ),
    yaxis=dict(autorange=True),          # vertical panning/zooming enabled
    margin=dict(l=300, r=50, t=80, b=80), # leave 300px for long Y-axis labels
)

# Enlarge legend font and place at top
fig.update_traces(marker_line_width=1)
fig.update_layout(
    legend=dict(
        font=dict(size=16),
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    )
)

# Display the Plotly chart
st.plotly_chart(fig, use_container_width=True)

# “Add New Project” Button Below
st.markdown("---")
st.markdown("### Want to add a new project to the dashboard?")
st.markdown(
    "[📝 Add New Project](https://app.smartsheet.com/b/form/a441de84912b4f27a5f2c59512d70897)",
    unsafe_allow_html=True,
)

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
                title = next(k for k, v in col_map.items() if v == cell.column_id)
                d[title] = cell.value
        rows.append(d)
    return pd.DataFrame(rows)

# --- Fetch & Preprocess Data ---
df = fetch_smartsheet_data()

# Convert date fields to datetime
for fld in [
    "Programming Start Date",
    "Schematic Design Start Date",
    "Design Development Start Date",
    "Construction Document Start Date",
    "Permit Set Delivery Date",
]:
    df[fld] = pd.to_datetime(df[fld], errors="coerce")

# Verify necessary columns
if "Design Manager Name" not in df.columns or "Project #" not in df.columns:
    st.error("Columns 'Design Manager Name' and/or 'Project #' not found in your Smartsheet data.")
    st.stop()

# --- Sidebar: Search, Sort, and Options ---
st.sidebar.header("🔍 Search & Sort")

search_project_name = st.sidebar.text_input("Search Project Name", value="")
search_project_number = st.sidebar.text_input("Search Project Number", value="")
search_design_manager = st.sidebar.text_input("Search Design Manager", value="")

sort_option = st.sidebar.selectbox(
    "Sort Projects By",
    options=[
        "Design Manager",
        "Project Name",
        "Programming Start Date",
        "Project Number"
    ]
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Additional Options")

# Show Only Active Today
show_active = st.sidebar.checkbox("Show Only Active Today", value=False)

# Color Theme
color_theme = st.sidebar.selectbox(
    "Color Theme",
    options=["ASU Brand", "High Contrast"]
)

# Jump to Project
jump_to = "-- None --"  # placeholder, will update after filtering

# --- Apply Filters to df ---
df_filtered = df.copy()

if search_project_name.strip():
    df_filtered = df_filtered[df_filtered["Project Name"]
                              .str.contains(search_project_name.strip(), case=False, na=False)]

if search_project_number.strip():
    df_filtered = df_filtered[df_filtered["Project #"]
                              .astype(str)
                              .str.contains(search_project_number.strip(), na=False)]

if search_design_manager.strip():
    df_filtered = df_filtered[df_filtered["Design Manager Name"]
                              .str.contains(search_design_manager.strip(), case=False, na=False)]

# Build a helper column for “active today” detection
today = pd.to_datetime(dt.date.today())
df_filtered["Active Today"] = False
for idx, row in df_filtered.iterrows():
    phases = [
        ("Programming", row["Programming Start Date"], row["Schematic Design Start Date"]),
        ("Schematic Design", row["Schematic Design Start Date"], row["Design Development Start Date"]),
        ("Design Development", row["Design Development Start Date"], row["Construction Document Start Date"]),
        ("Construction Documents", row["Construction Document Start Date"], row["Permit Set Delivery Date"]),
    ]
    for _, start_dt, end_dt in phases:
        if pd.notnull(start_dt) and pd.notnull(end_dt) and start_dt <= today < end_dt:
            df_filtered.at[idx, "Active Today"] = True
            break

if show_active:
    df_filtered = df_filtered[df_filtered["Active Today"]]

# --- Apply Sort Order ---
if sort_option == "Design Manager":
    df_filtered = df_filtered.sort_values(
        by=["Design Manager Name", "Project Name"],
        ascending=[True, True]
    ).reset_index(drop=True)

elif sort_option == "Project Name":
    df_filtered = df_filtered.sort_values(
        by=["Project Name"],
        ascending=True
    ).reset_index(drop=True)

elif sort_option == "Programming Start Date":
    df_filtered = df_filtered.sort_values(
        by=["Programming Start Date"], ascending=True
    ).reset_index(drop=True)

else:  # "Project Number"
    df_filtered["Project # Numeric"] = pd.to_numeric(df_filtered["Project #"], errors="coerce")
    df_filtered = df_filtered.sort_values(
        by=["Project # Numeric"], ascending=True
    ).reset_index(drop=True)
    df_filtered.drop(columns=["Project # Numeric"], inplace=True)

# --- Build “Long” DataFrame for Plotly Timeline ---
records = []
for _, row in df_filtered.iterrows():
    if pd.notnull(row["Project #"]) and str(row["Project #"]).replace(".", "", 1).isdigit():
        pname = f"{row['Project Name']} ({int(row['Project #'])})"
    elif pd.notnull(row["Project #"]):
        pname = f"{row['Project Name']} ({row['Project #']})"
    else:
        pname = row["Project Name"]
    full_label = f"{pname} — {row['Design Manager Name']}"

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

if long_df.empty:
    st.info("No data matches your search or filter criteria.")
    st.stop()

# Now that long_df exists, build the jump-to-project list
distinct_projects = long_df["Project"].unique().tolist()
jump_to = st.sidebar.selectbox("Jump to Project", options=["-- None --"] + distinct_projects)

# If user selected a specific project to “jump” to, reorder so that project’s bars come first
if jump_to != "-- None --":
    remaining = [p for p in distinct_projects if p != jump_to]
    ordered = [jump_to] + remaining
    long_df["Project"] = pd.Categorical(long_df["Project"], categories=ordered, ordered=True)
    long_df = long_df.sort_values(by="Project").reset_index(drop=True)

# --- Summary / Reporting Section ---
active_projects = df_filtered[df_filtered["Active Today"]]["Project Name"].nunique()
phase_counts = {
    "Programming": 0,
    "Schematic Design": 0,
    "Design Development": 0,
    "Construction Documents": 0
}
for _, row in df_filtered[df_filtered["Active Today"]].iterrows():
    for phase_name, start_dt, end_dt in [
        ("Programming", row["Programming Start Date"], row["Schematic Design Start Date"]),
        ("Schematic Design", row["Schematic Design Start Date"], row["Design Development Start Date"]),
        ("Design Development", row["Design Development Start Date"], row["Construction Document Start Date"]),
        ("Construction Documents", row["Construction Document Start Date"], row["Permit Set Delivery Date"]),
    ]:
        if pd.notnull(start_dt) and pd.notnull(end_dt) and start_dt <= today < end_dt:
            phase_counts[phase_name] += 1
            break

st.markdown("### 📈 Summary")
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Total Projects", df_filtered["Project Name"].nunique())
col2.metric("Active Today", active_projects)
col3.metric("In Programming", phase_counts["Programming"])
col4.metric("In Schematic", phase_counts["Schematic Design"])
col5.metric("In Design Development", phase_counts["Design Development"])
col6.metric("In CD Phase", phase_counts["Construction Documents"])

# --- Determine plot dimensions and shading ---
distinct_projects = long_df["Project"].unique().tolist()
n_projects = len(distinct_projects)
overall_min = long_df["Start"].min()
overall_max = long_df["Finish"].max()
start_year = overall_min.year
end_year = overall_max.year

# Color palette selection
if color_theme == "High Contrast":
    colors = {
        "Programming": "#004D40",
        "Schematic Design": "#F57F17",
        "Design Development": "#283593",
        "Construction Documents": "#D32F2F"
    }
else:  # ASU Brand
    colors = {
        "Programming": "#8C1D40",
        "Schematic Design": "#FFC627",
        "Design Development": "#5C6670",
        "Construction Documents": "#78BE20"
    }

# --- Build Plotly Timeline ---
hover_fmt = {"Start": "|%b %d, %Y", "Finish": "|%b %d, %Y"}  # tooltip date formatting
fig = px.timeline(
    long_df,
    x_start="Start",
    x_end="Finish",
    y="Project",
    color="Phase",
    color_discrete_map=colors,
    hover_data=hover_fmt
)

# Reverse y-axis so earliest project is at the top
fig.update_yaxes(autorange="reversed")

# Alternating even-year shading behind bars
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

# “Today” vertical line
today = pd.to_datetime(dt.date.today())
fig.add_vline(
    x=today,
    line_color=colors["Programming"],  # ASU maroon or high-contrast
    line_width=3
)

# Force initial dragmode = pan
fig.update_layout(dragmode="pan")

# Layout adjustments
row_height = 40
title_font = 26
tick_font = 14
legend_font = 16
margin_l = 300

fig.update_layout(
    height=row_height * n_projects + 200,
    title_text="Project Design Phases Timeline",
    title_font_size=title_font,
    legend_title_text="Phase",
    xaxis=dict(
        side="bottom",
        tickformat="%b %Y",
        dtick="M1",
        tickangle=45,
        tickfont=dict(size=tick_font),
        showgrid=True,
        gridcolor="lightgrey",
        gridwidth=1,
    ),
    yaxis=dict(autorange=True),
    margin=dict(l=margin_l, r=50, t=80, b=80),
)

# Enlarge legend font
fig.update_traces(marker_line_width=1)
fig.update_layout(
    legend=dict(
        font=dict(size=legend_font),
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    )
)

# Render the interactive chart
st.plotly_chart(fig, use_container_width=True)

# “Add New Project” Button
st.markdown("---")
st.markdown("### Want to add a new project to the dashboard?")
st.markdown(
    "[📝 Add New Project](https://app.smartsheet.com/b/form/a441de84912b4f27a5f2c59512d70897)",
    unsafe_allow_html=True,
)

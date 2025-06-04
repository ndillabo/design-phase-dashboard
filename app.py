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

# Build a “long” DataFrame for Plotly’s timeline
records = []
for _, row in df.iterrows():
    if pd.notnull(row.get("Project #")) and str(row["Project #"]).replace(".", "", 1).isdigit():
        pname = f"{row['Project Name']} ({int(row['Project #'])})"
    elif pd.notnull(row.get("Project #")):
        pname = f"{row['Project Name']} ({row['Project #']})"
    else:
        pname = row["Project Name"]

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

# ASU brand colors
colors = {
    "Programming": "#8C1D40",
    "Schematic Design": "#FFC627",
    "Design Development": "#5C6670",
    "Construction Documents": "#78BE20"
}

if long_df.empty:
    st.write("No valid phase dates to display.")
else:
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

    # Reverse y-axis so earliest project is at top
    fig.update_yaxes(autorange="reversed")

    # Alternating even-year shading behind the bars
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

    # “Today” vertical line (ASU maroon)
    today = pd.to_datetime(dt.date.today())
    fig.add_vline(
        x=today,
        line_color="#8C1D40",
        line_width=3
    )

    # Layout tweaks: move X-axis to top, lock vertical range
    fig.update_layout(
        height=40 * n_projects + 200,   # 40px per row + padding
        title_text="Project Design Phases Timeline",
        title_font_size=26,
        legend_title_text="Phase",
        xaxis=dict(
            side="top",                # ← pin X-axis at the top of the plotting area
            tickformat="%b %Y",
            dtick="M1",
            tickangle=45,
            tickfont=dict(size=14),
            showgrid=True,
            gridcolor="lightgrey",
            gridwidth=1,
        ),
        yaxis=dict(
            range=[-0.5, n_projects - 0.5],  # exactly cover all rows
            fixedrange=True                 # disables vertical panning/zooming
        ),
        margin=dict(l=300, r=50, t=80, b=80),  # 300px left margin for project names
    )

    # Enlarge legend font, place at top
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

    # Render in Streamlit
    st.plotly_chart(fig, use_container_width=True)

# Add “Add New Project” button
st.markdown("---")
st.markdown("### Want to add a new project to the dashboard?")
st.markdown(
    "[📝 Add New Project](https://app.smartsheet.com/b/form/a441de84912b4f27a5f2c59512d70897)",
    unsafe_allow_html=True,
)

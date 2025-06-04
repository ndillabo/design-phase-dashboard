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

# Convert Smartsheet date fields to pandas datetime
for fld in [
    "Programming Start Date",
    "Schematic Design Start Date",
    "Design Development Start Date",
    "Construction Document Start Date",
    "Permit Set Delivery Date",
]:
    df[fld] = pd.to_datetime(df[fld], errors="coerce")

# If the column is named "Design Manager Name" in Smartsheet, ensure it's present
# Otherwise, you may need to rename it to match exactly.
if "Design Manager Name" not in df.columns:
    raise RuntimeError("Column 'Design Manager Name' not found in your Smartsheet data.")

# Sort by Design Manager Name (alphabetically), then by Project # as string
df["Project # Sort"] = df["Project #"].astype(str)
df = df.sort_values(
    by=["Design Manager Name", "Project # Sort"],
    ascending=[True, True]
).reset_index(drop=True)

# Build a “long” DataFrame for Plotly’s timeline:
records = []
for _, row in df.iterrows():
    # Construct "Project Name (Project #) — Design Manager Name"
    if pd.notnull(row.get("Project #")) and str(row["Project #"]).replace(".", "", 1).isdigit():
        proj_label = f"{row['Project Name']} ({int(row['Project #'])})"
    elif pd.notnull(row.get("Project #")):
        proj_label = f"{row['Project Name']} ({row['Project #']})"
    else:
        proj_label = row["Project Name"]

    # Now append the Design Manager name:
    proj_label = f"{proj_label} — {row['Design Manager Name']}"

    # Define each of the four phases with start & end:
    phases = [
        ("Programming", row["Programming Start Date"], row["Schematic Design Start Date"]),
        ("Schematic Design", row["Schematic Design Start Date"], row["Design Development Start Date"]),
        ("Design Development", row["Design Development Start Date"], row["Construction Document Start Date"]),
        ("Construction Documents", row["Construction Document Start Date"], row["Permit Set Delivery Date"]),
    ]
    for phase_name, start_dt, end_dt in phases:
        if pd.notnull(start_dt) and pd.notnull(end_dt):
            records.append({
                "Project": proj_label,
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
    # Determine how many distinct “Project — Manager” rows we have:
    distinct_projects = long_df["Project"].unique().tolist()
    n_projects = len(distinct_projects)

    # Compute the overall date range to know which years to shade
    overall_min = long_df["Start"].min()
    overall_max = long_df["Finish"].max()
    start_year = overall_min.year
    end_year = overall_max.year

    # Build the Plotly timeline figure
    fig = px.timeline(
        long_df,
        x_start="Start",
        x_end="Finish",
        y="Project",
        color="Phase",
        color_discrete_map=colors,
    )

    # Invert Y-axis so earliest project appears at the top
    fig.update_yaxes(autorange="reversed")

    # Add alternating even‐year shading behind the bars:
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

    # Draw a “Today” vertical line in ASU maroon
    today = pd.to_datetime(dt.date.today())
    fig.add_vline(
        x=today,
        line_color="#8C1D40",
        line_width=3
    )

    # Lock vertical panning/zoom so you cannot scroll above/below the bars.
    # Pin X-axis to the top so it never disappears when panning vertically.
    fig.update_layout(
        height=40 * n_projects + 200,   # 40px per row + padding
        title_text="Project Design Phases Timeline",
        title_font_size=26,
        legend_title_text="Phase",
        xaxis=dict(
            side="top",                # pin at top
            tickformat="%b %Y",
            dtick="M1",                # monthly ticks
            tickangle=45,
            tickfont=dict(size=14),
            showgrid=True,
            gridcolor="lightgrey",
            gridwidth=1,
        ),
        yaxis=dict(
            range=[-0.5, n_projects - 0.5],  # exactly cover all rows
            fixedrange=True                 # disable vertical panning/zooming
        ),
        margin=dict(l=300, r=50, t=80, b=80),  # 300px left margin for long labels
    )

    # Enlarge the legend font and place it above the plot
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

    # Display the Plotly chart in Streamlit
    st.plotly_chart(fig, use_container_width=True)

# “Add New Project” Button
st.markdown("---")
st.markdown("### Want to add a new project to the dashboard?")
st.markdown(
    "[📝 Add New Project](https://app.smartsheet.com/b/form/a441de84912b4f27a5f2c59512d70897)",
    unsafe_allow_html=True,
)

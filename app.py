import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import matplotlib.dates as mdates
import datetime as dt
import io
import base64
from dateutil.relativedelta import relativedelta
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
                row_dict[
                    next(k for k, v in col_map.items() if v == cell.column_id)
                ] = cell.value
        data.append(row_dict)
    return pd.DataFrame(data)

# --- App Layout ---
st.set_page_config(layout="wide")
st.title("📊 Design Phase Dashboard")
st.caption("Fixed Y-axis on the left, horizontally scrollable timeline on the right.")

df = fetch_smartsheet_data()

# --- Preprocessing ---
date_fields = [
    "Programming Start Date",
    "Schematic Design Start Date",
    "Design Development Start Date",
    "Construction Document Start Date",
    "Permit Set Delivery Date",
]
for field in date_fields:
    df[field] = pd.to_datetime(df[field], errors="coerce")

df["Programming End"] = df["Schematic Design Start Date"]
df["Schematic Design End"] = df["Design Development Start Date"]
df["Design Development End"] = df["Construction Document Start Date"]
df["Construction Document End"] = df["Permit Set Delivery Date"]

df["Y Label"] = df.apply(
    lambda row: f"{row['Project Name']} ({int(row['Project #'])})"
    if pd.notnull(row["Project #"])
    and str(row["Project #"]).replace(".", "", 1).isdigit()
    else f"{row['Project Name']} ({row['Project #']})"
    if pd.notnull(row["Project #"])
    else row["Project Name"],
    axis=1,
)

df["Project # Sort"] = df["Project #"].astype(str)
df = df.sort_values(by="Project # Sort", ascending=True).reset_index(drop=True)

phases = [
    "Programming",
    "Schematic Design",
    "Design Development",
    "Construction Documents",
]
# ASU brand colors:
colors = ["#8C1D40", "#FFC627", "#5C6670", "#78BE20"]
phase_colors = dict(zip(phases, colors))

earliest = df[
    [
        "Programming Start Date",
        "Schematic Design Start Date",
        "Design Development Start Date",
        "Construction Document Start Date",
    ]
].min().min()
latest = df[["Permit Set Delivery Date"]].max().max()
x_min = earliest - relativedelta(months=1)
x_max = latest + relativedelta(months=5)
today = dt.datetime.today().date()

num_projects = len(df)

# --- CONSTANTS for Pixel-Perfect Alignment ---
ROW_HEIGHT_PX = 40       # Each project row = 40 pixels tall
LEFT_COLUMN_WIDTH_PX = 300  # Y-axis column width in px
TIMELINE_WIDTH_PX = 5000    # Timeline wide image width in px
DPI = 100                   # Dots per inch for both figures

# Compute figure heights/widths in inches:
fig_height_inches = (num_projects * ROW_HEIGHT_PX) / DPI
fig_left_width_inches = LEFT_COLUMN_WIDTH_PX / DPI
fig_right_width_inches = TIMELINE_WIDTH_PX / DPI

# --- LEFT COLUMN: Y-Axis Labels as PNG (fixed) ---
fig_left, ax_left = plt.subplots(
    figsize=(fig_left_width_inches, fig_height_inches), dpi=DPI
)
# Remove any margins
fig_left.subplots_adjust(left=0, right=1, top=1, bottom=0)

# Y-axis vertical span
ax_left.set_ylim(-0.5, num_projects - 0.5)
ax_left.set_xlim(0, 1)
ax_left.axis("off")  # No axis box, ticks, etc.

# Draw each label exactly at its row center
for i, label in enumerate(df["Y Label"]):
    ax_left.text(
        0.99,
        i,
        label,
        ha="right",
        va="center",
        fontsize=18,
        color="black",
    )

buf_left = io.BytesIO()
plt.savefig(buf_left, format="png", bbox_inches="tight", pad_inches=0)
buf_left.seek(0)
img_left_base64 = base64.b64encode(buf_left.getvalue()).decode()
plt.close(fig_left)

# --- RIGHT COLUMN: Full Timeline Chart as PNG (scrollable) ---
fig_right, ax_right = plt.subplots(
    figsize=(fig_right_width_inches, fig_height_inches), dpi=DPI
)
# Remove margins
fig_right.subplots_adjust(left=0, right=1, top=1, bottom=0)

# Horizontal grid lines behind bars
for y in range(num_projects):
    ax_right.axhline(
        y=y, color="lightgrey", linestyle="--", linewidth=0.5, alpha=0.2, zorder=0
    )

# Plot each phase as a horizontal bar
for i, row in df.iterrows():
    y_pos = i
    starts = [
        row["Programming Start Date"],
        row["Schematic Design Start Date"],
        row["Design Development Start Date"],
        row["Construction Document Start Date"],
    ]
    ends = [
        row["Programming End"],
        row["Schematic Design End"],
        row["Design Development End"],
        row["Construction Document End"],
    ]
    for j in range(4):
        if pd.notnull(starts[j]) and pd.notnull(ends[j]):
            ax_right.barh(
                y=y_pos,
                width=(ends[j] - starts[j]).days,
                left=starts[j],
                color=colors[j],
                edgecolor="black",
                zorder=3,
                height=0.6,
            )

# Alternate-year background shading
for year in range(x_min.year - 1, x_max.year + 2):
    if year % 2 == 1:
        ax_right.axvspan(
            dt.datetime(year, 1, 1),
            dt.datetime(year + 1, 1, 1),
            color="grey",
            alpha=0.1,
            zorder=0,
        )

# "Today" line
asu_maroon = "#8C1D40"
ax_right.axvline(
    dt.datetime.combine(today, dt.datetime.min.time()), color=asu_maroon, linewidth=2, zorder=4
)

# Axes formatting
ax_right.set_xlim(x_min, x_max)
ax_right.set_ylim(-0.5, num_projects - 0.5)
ax_right.set_yticks(range(num_projects))
ax_right.set_yticklabels([])  # Labels live on the left image
ax_right.invert_yaxis()
ax_right.tick_params(labelsize=16)

ax_right.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
ax_right.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
fig_right.autofmt_xdate(rotation=45)

ax_right.set_xlabel("Date", fontsize=18)
ax_right.set_title(
    "Project Design Phases Timeline", fontsize=26, color=asu_maroon, pad=20
)
ax_right.grid(True, axis="x", linestyle="--", alpha=0.5)

legend_elements = [
    Patch(facecolor=phase_colors[phase], label=phase) for phase in phases
]
legend_elements.append(Line2D([0], [0], color=asu_maroon, lw=2, label="Today"))
ax_right.legend(handles=legend_elements, loc="upper right", fontsize=16)

buf_right = io.BytesIO()
plt.savefig(buf_right, format="png", bbox_inches="tight", pad_inches=0)
buf_right.seek(0)
img_right_base64 = base64.b64encode(buf_right.getvalue()).decode()
plt.close(fig_right)

# --- RENDER SIDE BY SIDE WITH CSS (Fixed + Scrollable) ---
st.markdown(
    f"""
<style>
.fixed-left {{
    display: inline-block;
    vertical-align: top;
    width: {LEFT_COLUMN_WIDTH_PX}px;
}}
.scroll-right {{
    display: inline-block;
    vertical-align: top;
    overflow-x: auto;
    width: calc(100% - {LEFT_COLUMN_WIDTH_PX + 10}px);
}}
</style>
<div class="fixed-left">
    <img src="data:image/png;base64,{img_left_base64}" />
</div>
<div class="scroll-right">
    <img src="data:image/png;base64,{img_right_base64}" />
</div>
<br style="clear: both;" />
""",
    unsafe_allow_html=True,
)

# --- Button to Add New Project ---
st.markdown("---")
st.markdown("### Want to add a new project to the dashboard?")
st.markdown(
    "[📝 Add New Project](https://app.smartsheet.com/b/form/a441de84912b4f27a5f2c59512d70897)",
    unsafe_allow_html=True,
)

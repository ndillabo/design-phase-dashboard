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

# --- LEFT COLUMN: Y-Axis Labels as Fixed Image ---
fig_left, ax_left = plt.subplots(
    figsize=(4, num_projects * 0.8), dpi=150
)
ax_left.set_ylim(-0.5, num_projects - 0.5)
ax_left.set_xlim(0, 1)
ax_left.axis("off")
for i, label in enumerate(df["Y Label"]):
    ax_left.text(0.95, i, label, ha="right", va="center", fontsize=18)

buf_left = io.BytesIO()
plt.tight_layout()
plt.savefig(buf_left, format="png", bbox_inches="tight", pad_inches=0.1)
buf_left.seek(0)
img_left_base64 = base64.b64encode(buf_left.getvalue()).decode()

plt.close(fig_left)  # close to free memory

# --- RIGHT COLUMN: Timeline Chart as Scrollable Image ---
fig_right, ax_right = plt.subplots(
    figsize=(100, num_projects * 0.8), dpi=150  # very wide to force scroll
)

# Horizontal grid lines behind bars
for y in range(num_projects):
    ax_right.axhline(
        y=y, color="lightgrey", linestyle="--", linewidth=0.5, alpha=0.2, zorder=0
    )

# Plot each phase as horizontal bar
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

# "Today" vertical line in ASU maroon
asu_maroon = "#8C1D40"
ax_right.axvline(
    dt.datetime.combine(today, dt.datetime.min.time()), color=asu_maroon, linewidth=2, zorder=4
)

# Axes formatting
ax_right.set_xlim(x_min, x_max)
ax_right.set_ylim(-0.5, num_projects - 0.5)
ax_right.set_yticks(range(num_projects))
ax_right.set_yticklabels([])  # left side handles labels
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
plt.tight_layout()
plt.savefig(buf_right, format="png", bbox_inches="tight", pad_inches=0.1)
buf_right.seek(0)
img_right_base64 = base64.b64encode(buf_right.getvalue()).decode()

plt.close(fig_right)

# --- RENDER SIDE-BY-SIDE IN STREAMLIT ---
st.markdown(
    """
<style>
.fixed-left {
    display: inline-block;
    vertical-align: top;
    width: 300px;
}
.scroll-right {
    display: inline-block;
    vertical-align: top;
    overflow-x: auto;
    width: calc(100% - 325px);
}
</style>
<div class="fixed-left">
    <img src="data:image/png;base64,""" + img_left_base64 + """" />
</div>
<div class="scroll-right">
    <img src="data:image/png;base64,""" + img_right_base64 + """" />
</div>
<br style="clear: both;">
""",
    unsafe_allow_html=True,
)

# --- Add Project Button Below ---
st.markdown("---")
st.markdown("### Want to add a new project to the dashboard?")
st.markdown(
    "Use the form below — updates will appear immediately after submission."
)
st.markdown(
    "[📝 Add New Project](https://app.smartsheet.com/b/form/a441de84912b4f27a5f2c59512d70897)",
    unsafe_allow_html=True,
)

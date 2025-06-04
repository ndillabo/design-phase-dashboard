import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import datetime as dt
import smartsheet
import matplotlib.dates as mdates
from dateutil.relativedelta import relativedelta

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
            for key, val in col_map.items():
                if cell.column_id == val:
                    row_dict[key] = cell.value
        data.append(row_dict)
    return pd.DataFrame(data)

# --- App UI ---
st.set_page_config(layout="wide")
st.title("📊 Design Phase Dashboard")
st.caption("Full visual zoom retained with actual horizontal scrolling.")

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

df["Y Label"] = df.apply(
    lambda row: f"{row['Project Name']} ({int(row['Project #'])})"
    if pd.notnull(row["Project #"]) and str(row["Project #"]).replace('.', '', 1).isdigit()
    else f"{row['Project Name']} ({row['Project #']})"
    if pd.notnull(row["Project #"]) else row["Project Name"],
    axis=1
)

df["Project # Sort"] = df["Project #"].astype(str)
df = df.sort_values(by="Project # Sort", ascending=True).reset_index(drop=True)

# --- Colors ---
phases = ['Programming', 'Schematic Design', 'Design Development', 'Construction Documents']
colors = ['#8C1D40', '#FFC627', '#5C6670', '#78BE20']
phase_colors = dict(zip(phases, colors))

# --- Time Window ---
earliest = df[["Programming Start Date", "Schematic Design Start Date", "Design Development Start Date", "Construction Document Start Date"]].min().min()
latest = df[["Permit Set Delivery Date"]].max().max()
x_min = earliest - relativedelta(months=1)
x_max = latest + relativedelta(months=5)

# --- Plot ---
fig, ax = plt.subplots(figsize=(80, len(df) * 0.8), dpi=100)
today = dt.datetime.today().date()

for y in range(len(df)):
    ax.axhline(y=y, color='lightgrey', linestyle='--', linewidth=0.5, zorder=0, alpha=0.2)

for i, row in df.iterrows():
    y_pos = i
    starts = [
        row['Programming Start Date'], row['Schematic Design Start Date'],
        row['Design Development Start Date'], row['Construction Document Start Date']
    ]
    ends = [
        row['Programming End'], row['Schematic Design End'],
        row['Design Development End'], row['Construction Document End']
    ]
    for j in range(4):
        if pd.notnull(starts[j]) and pd.notnull(ends[j]):
            ax.barh(
                y=y_pos,
                width=(ends[j] - starts[j]).days,
                left=starts[j],
                color=colors[j],
                edgecolor='black',
                zorder=3,
                height=0.6
            )

years = range(x_min.year - 1, x_max.year + 1)
for year in years:
    if year % 2 == 1:
        ax.axvspan(dt.datetime(year, 1, 1), dt.datetime(year + 1, 1, 1), color='grey', alpha=0.1, zorder=0)

asu_maroon = '#8C1D40'
ax.axvline(dt.datetime.combine(today, dt.datetime.min.time()), color=asu_maroon, linewidth=2, zorder=4)

ax.set_xlim(x_min, x_max)
ax.set_yticks(range(len(df)))
ax.set_yticklabels(df["Y Label"].fillna("Unnamed Project"), ha='right', fontsize=16)
ax.invert_yaxis()
ax.tick_params(labelsize=14)

ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
fig.autofmt_xdate(rotation=45)

ax.set_xlabel("Date", fontsize=14)
ax.set_title("Project Design Phases Timeline", fontsize=20, color=asu_maroon)
ax.grid(True, axis='x', linestyle='--', alpha=0.5)

legend_elements = [Patch(facecolor=phase_colors[phase], label=phase) for phase in phases]
legend_elements.append(Line2D([0], [0], color=asu_maroon, lw=2, label='Today'))
ax.legend(handles=legend_elements, loc="upper right", fontsize=12)

plt.tight_layout()

# --- Scrollable container (no scale down)
with st.container():
    st.markdown("""
        <div style='overflow-x: auto; width: 100%;'>
            <div style='width: 5000px;'>
    """, unsafe_allow_html=True)
    st.pyplot(fig, use_container_width=False)
    st.markdown("</div></div>", unsafe_allow_html=True)

# --- Add Project Button ---
st.markdown("---")
st.markdown("### Want to add a new project to the dashboard?")
st.markdown("Use the form below — updates will appear immediately after submission.")
st.markdown(
    "[📝 Add New Project](https://app.smartsheet.com/b/form/a441de84912b4f27a5f2c59512d70897)",
    unsafe_allow_html=True
)

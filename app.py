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
st.caption("Trimmed view: 1 month before first project, 5 months after latest. Includes alternating year bands.")

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

# --- Combine labels: "Project Name (Project #)" without decimals ---
df["Y Label"] = df.apply(
    lambda row: f"{row['Project Name']} ({int(row['Project #'])})"
    if pd.notnull(row["Project #"]) and str(row["Project #"]).replace('.', '', 1).isdigit()
    else f"{row['Project Name']} ({row['Project #']})"
    if pd.notnull(row["Project #"]) else row["Project Name"],
    axis=1
)

# --- Sort by Project # as string ---
df["Project # Sort"] = df["Project #"].astype(str)
df = df.sort_values(by="Project # Sort", ascending=True).reset_index(drop=True)

# --- ASU Brand Colors ---
phases = ['Programming', 'Schematic Design', 'Design Development', 'Construction Documents']
colors = ['#8C1D40', '#FFC627', '#5C6670', '#78BE20']
phase_colors = dict(zip(phases, colors))

# --- Timeline window ---
earliest = df[["Programming Start Date", "Schematic Design Start Date", "Design Development Start Date", "Construction Document Start Date"]].min().min()
latest = df[["Permit Set Delivery Date"]].max().max()
x_min = earliest - relativedelta(months=1)
x_max = latest + relativedelta(months=5)

# --- Plotting ---
fig, ax = plt.subplots(figsize=(18, len(df) * 0.6))
today = dt.datetime.today().date()

# --- Bars ---
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
                edgecolor='black'
            )

# --- Alternating Year Backgrounds ---
years = range(x_min.year - 1, x_max.year + 1)
for year in years:
    if year % 2 == 1:
        start = dt.datetime(year, 1, 1)
        end = dt.datetime(year + 1, 1, 1)
        ax.axvspan(start, end, color='grey', alpha=0.1, zorder=0)

# --- Today Line ---
asu_maroon = '#8C1D40'
ax.axvline(dt.datetime.combine(today, dt.datetime.min.time()), color=asu_maroon, linewidth=2)

# --- Configure Axes ---
ax.set_xlim(x_min, x_max)
ax.set_yticks(range(len(df)))
ax.set_yticklabels(df["Y Label"].fillna("Unnamed Project"), ha='right')
ax.invert_yaxis()
ax.tick_params(labelsize=10)

# --- X-axis: Month-Year Ticks ---
ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
fig.autofmt_xdate(rotation=45)

ax.set_xlabel("Date")
ax.set_title("Project Design Phases Timeline", fontsize=18, color=asu_maroon)
ax.grid(True, axis='x', linestyle='--', alpha=0.5)

# --- Legend ---
legend_elements = [Patch(facecolor=phase_colors[phase], label=phase) for phase in phases]
legend_elements.append(Line2D([0], [0], color=asu_maroon, lw=2, label='Today'))
ax.legend(handles=legend_elements, loc="upper right")

plt.tight_layout()
st.pyplot(fig)

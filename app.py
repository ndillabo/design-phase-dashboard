import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import datetime as dt
import smartsheet

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
st.caption("Auto-refreshes on load or when clicking the refresh button.")

if st.button("🔄 Refresh Data"):
    st.cache_data.clear()

df = fetch_smartsheet_data()

# Debug: Show available columns
# st.write("Available columns:", df.columns.tolist())

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

colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
phases = ['Programming', 'Schematic Design', 'Design Development', 'Construction Documents']

# --- Plotting ---
fig, ax = plt.subplots(figsize=(18, len(df) * 0.6))

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
            ax.barh(y=y_pos, width=(ends[j] - starts[j]).days,
                    left=starts[j], color=colors[j], edgecolor='black')

ax.axvline(dt.datetime.today(), color='red', linewidth=2, label='Today')
ax.set_yticks(range(len(df)))
ax.set_yticklabels(df["Project Name"].fillna("Unnamed Project"))
ax.set_xlabel("Date")
ax.set_title("Project Design Phases Timeline")
ax.legend(phases + ["Today"], loc="upper right")
ax.grid(True, axis='x', linestyle='--', alpha=0.5)

st.pyplot(fig)

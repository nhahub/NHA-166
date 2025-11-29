import streamlit as st
import pandas as pd
import psycopg2
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import timedelta
import time

# ---------------------- إعداد الصفحة ----------------------
st.set_page_config(page_title="Hospital Vitals Dashboard", layout="wide")
st.title("Hospital Vitals Dashboard")

# ---------------------- إعداد الاتصال ----------------------
try:
    conn = psycopg2.connect(
        host="postgres_general",
        database="patients_db",
        user="admin",
        password="admin",
        port=5432
    )
except Exception as e:
    st.error(f"❌ Connection failed: {e}")

# ---------------------- دالة الكارد ----------------------
def stat_card(color, icon, title, value):
    return f"""
    <div style="
        background:{color};
        padding:20px;
        border-radius:18px;
        color:white;
        text-align:center;
        font-size:20px;
        font-weight:bold;
        transition:0.3s;
        box-shadow:0 4px 10px rgba(0,0,0,0.2);
    ">
        <div style="font-size:35px;margin-bottom:5px;">{icon}</div>
        {title}<br>
        <span style="font-size:26px;">{value}</span>
    </div>
    """

# ---------------------- تعريف الفيتالز والنطاقات ----------------------
vitals = ['heart_rate','bp_systolic','bp_diastolic','oxygen_saturation',
          'temperature','respiratory_rate','glucose_level']
vital_labels = {
    'heart_rate':'Heart Rate',
    'bp_systolic':'BP Systolic',
    'bp_diastolic':'BP Diastolic',
    'oxygen_saturation':'Oxygen Saturation',
    'temperature':'Temperature',
    'respiratory_rate':'Respiratory Rate',
    'glucose_level':'Glucose Level'
}
normal_ranges = {
    'heart_rate': (60, 100),
    'bp_systolic': (90, 140),
    'bp_diastolic': (60, 90),
    'oxygen_saturation': (95, 100),
    'temperature': (36, 37.5),
    'respiratory_rate': (12, 20),
    'glucose_level': (70, 140)
}

# ---------------------- حساب حالات المرضى ----------------------
def compute_patient_status(df):
    patient_status = {}
    for patient in df['patient_id'].unique():
        patient_data = df[df['patient_id']==patient].sort_values('timestamp')
        latest = patient_data.iloc[-1]  # آخر قراءة
        out_of_range_count = 0
        for vital in vitals:
            val = latest.get(vital, None)
            if pd.isna(val):
                continue
            low, high = normal_ranges[vital]
            if val < low or val > high:
                out_of_range_count +=1
        # تحديد الحالة حسب عدد القيم خارج النطاق
        if out_of_range_count >= 4:
            patient_status[patient] = 'Critical'
        elif out_of_range_count >= 2:
            patient_status[patient] = 'Observation'
        else:
            patient_status[patient] = 'Stable'
    return patient_status

# ---------------------- الكروت ----------------------
if 'conn' in locals():
    df_stats = pd.read_sql_query("SELECT * FROM vitals ORDER BY timestamp DESC;", conn)

    if not df_stats.empty:
        # فصل ضغط الدم لو موجود
        if 'blood_pressure' in df_stats.columns and df_stats['blood_pressure'].notnull().any():
            bp_split = df_stats['blood_pressure'].str.split('/', expand=True)
            df_stats['bp_systolic'] = pd.to_numeric(bp_split[0], errors='coerce')
            df_stats['bp_diastolic'] = pd.to_numeric(bp_split[1], errors='coerce')
        else:
            df_stats['bp_systolic'] = pd.NA
            df_stats['bp_diastolic'] = pd.NA

        df_stats['timestamp'] = pd.to_datetime(df_stats['timestamp'], errors='coerce')

        # حساب الحالة لكل مريض
        patient_status = compute_patient_status(df_stats)

        # تقسيم المرضى حسب الحالة
        critical_patients = [p for p,s in patient_status.items() if s=='Critical']
        stable_patients = [p for p,s in patient_status.items() if s=='Stable']
        obs_patients = [p for p,s in patient_status.items() if s=='Observation']
        total_cases = len(patient_status)

        col1, col2, col3, col4 = st.columns(4)

        col1.markdown(stat_card("#3867d6", "", "Total Cases", total_cases), unsafe_allow_html=True)
        with col1.expander("Show Patients"):
            st.write(list(patient_status.keys()))

        col2.markdown(stat_card("#eb3b5a", "", "Critical", len(critical_patients)), unsafe_allow_html=True)
        with col2.expander("Show Patients"):
            st.write(critical_patients)

        col3.markdown(stat_card("#20bf6b", "", "Stable", len(stable_patients)), unsafe_allow_html=True)
        with col3.expander("Show Patients"):
            st.write(stable_patients)

        col4.markdown(stat_card("#f7b731", "", "Observation", len(obs_patients)), unsafe_allow_html=True)
        with col4.expander("Show Patients"):
            st.write(obs_patients)

# ---------------------- اختيار المريض ----------------------
if 'conn' in locals():
    patient_list = sorted(df_stats['patient_id'].unique())
else:
    patient_list = []
selected_patient = st.selectbox("Select Patient", patient_list, key="patient_selectbox")

# ---------------------- Placeholder للتحديث ----------------------
placeholder = st.empty()

# ---------------------- تحديث البيانات ----------------------
if 'conn' in locals():
    while True:
        with placeholder.container():
            df = pd.read_sql_query("SELECT * FROM vitals ORDER BY timestamp DESC;", conn)
            if df.empty:
                st.info("No data available yet.")
                time.sleep(1)
                continue

            numeric_cols = ['heart_rate','oxygen_saturation','temperature','respiratory_rate','glucose_level']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            if 'blood_pressure' in df.columns and df['blood_pressure'].notnull().any():
                bp_split = df['blood_pressure'].str.split('/', expand=True)
                df['bp_systolic'] = pd.to_numeric(bp_split[0], errors='coerce')
                df['bp_diastolic'] = pd.to_numeric(bp_split[1], errors='coerce')
            else:
                df['bp_systolic'] = pd.NA
                df['bp_diastolic'] = pd.NA

            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            patient_data = df[df['patient_id'] == selected_patient].sort_values('timestamp')
            if patient_data.empty:
                st.warning(f"No data for patient {selected_patient}")
                time.sleep(2)
                continue

            one_hour_ago = patient_data['timestamp'].max() - timedelta(hours=1)
            recent_data = patient_data[patient_data['timestamp'] >= one_hour_ago]

            # ---------------------- جدول المتوسطات ----------------------
            st.subheader("Alerts / Average Readings (Red = Out of Normal Range)")
            avg_data = patient_data[vitals].mean().to_frame(name='Average').T
            def highlight(val, vital_name):
                if pd.isna(val):
                    return 'background-color: #cccccc'
                low, high = normal_ranges[vital_name]
                return 'background-color: #ff4b4b' if val < low or val > high else ''
            styled_avg = avg_data.style.apply(lambda row: [highlight(row[v], v) for v in vitals], axis=1)
            st.dataframe(styled_avg, use_container_width=True)

            # ---------------------- Vitals Overview ----------------------
            st.subheader(f"Vitals Overview for {selected_patient} (Latest Reading)")
            cols = st.columns(4)
            for i, vital in enumerate(vitals):
                col = cols[i % 4]
                latest_value = recent_data[vital].iloc[-1] if not recent_data.empty else pd.NA
                low, high = normal_ranges[vital]
                if pd.isna(latest_value):
                    color = '#aaaaaa'
                    display_value = "N/A"
                else:
                    color = '#ff4b4b' if latest_value < low or latest_value > high else '#4CAF50'
                    display_value = latest_value
                col.markdown(f"""
                <div style='
                    background-color:{color};
                    border-radius:12px;
                    padding:20px;
                    text-align:center;
                    font-size:18px;
                    font-weight:bold;
                    color:white;
                    margin-bottom:10px;
                '>
                    {vital_labels[vital]}<br>{display_value}
                </div>
                """, unsafe_allow_html=True)

            # ---------------------- Trend Chart ----------------------
            st.subheader(f"Vitals Trend for {selected_patient} (Last Hour)")
            fig = make_subplots(
                rows=len(vitals), cols=1, shared_xaxes=True,
                subplot_titles=[vital_labels[v] for v in vitals]
            )

            for i, vital in enumerate(vitals, start=1):
                if not recent_data.empty and recent_data[vital].notna().any():
                    marker_color = [
                        'red' if (v < normal_ranges[vital][0] or v > normal_ranges[vital][1]) else 'green'
                        for v in recent_data[vital]
                    ]
                    fig.add_trace(
                        go.Scatter(
                            x=recent_data['timestamp'],
                            y=recent_data[vital],
                            mode='lines+markers',
                            marker=dict(color=marker_color, size=8),
                            line=dict(color='#1f77b4'),
                            name=vital_labels[vital]
                        ),
                        row=i,
                        col=1
                    )

            fig.update_layout(height=300*len(vitals), showlegend=False)
            st.plotly_chart(fig, use_container_width=True, key=f"trend_{selected_patient}_{int(time.time())}")

        time.sleep(5)
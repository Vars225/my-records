import streamlit as st
from streamlit_mic_recorder import mic_recorder
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv
import pandas as pd

# --- 1. SETUP ---
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    st.error("API Key kanipinchaledu. .env file check cheyyandi.")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

# Google Sheets Connection Setup
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # Dashboard secrets nunchi dict thechukovadam
    creds_dict = dict(st.secrets["GCP_SERVICE_ACCOUNT"])
    
    # 🌟 KEY FIX: Newline characters format ni auto-fix chesthundi
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("my-records").sheet1

# --- 2. LOGIC FUNCTIONS ---
def extract_data_from_audio(audio_bytes):
    # User snippet lo unna model name ni use chesthunnam
    model = genai.GenerativeModel('gemini-2.5-flash') 
    
    prompt = """
    Listen to this Telugu/English voice note. It contains a village business transaction.
    Extract the following details from the audio:
    - Client Name (evari tho transaction jarigindi)
    - Service (em business/service icharu)
    - Total Amount (Motham entha bill ayindi)
    - Paid Amount (Entha money icchesaru)
    - Pending Balance (Inka entha ivvali)

    Return the output STRICTLY in JSON format using these exact keys:
    {"client_name": "", "service": "", "total_amount": 0, "paid_amount": 0, "pending_balance": 0}
    
    If any number is not mentioned, put 0.
    """
    
    audio_part = {
        "mime_type": "audio/webm",
        "data": audio_bytes
    }
    
    response = model.generate_content(
        [prompt, audio_part],
        generation_config={"response_mime_type": "application/json"}
    )
    return response.text

def update_google_sheet(json_data_string):
    sheet = get_sheet()
    data = json.loads(json_data_string)
    today_date = datetime.now().strftime("%Y-%m-%d")
    
    # Row entry (Status column ni default ga 'No' ani peduthunnam)
    row_to_insert = [
        today_date,
        data.get("client_name", ""),
        data.get("service", ""),
        data.get("total_amount", 0),
        data.get("paid_amount", 0),
        data.get("pending_balance", 0),
        "No" # Status Column: "Cleared?"
    ]
    sheet.append_row(row_to_insert)
    return data

def fetch_sheet_data():
    sheet = get_sheet()
    records = sheet.get_all_records()
    if records:
        return pd.DataFrame(records)
    return pd.DataFrame()

# Kothaga add chesina function: Table lo edit chesthe Sheet update avvali
def sync_edits_to_sheets(edited_df):
    sheet = get_sheet()
    # Sheet mothanni okke sari update chestham (Header thopaatu)
    # Pandas DataFrame ni list format loki marchadam
    data_list = [edited_df.columns.values.tolist()] + edited_df.values.tolist()
    sheet.update('A1', data_list)
    st.success("✅ Sheet successfully updated!")

# --- 3. STREAMLIT UI ---
st.set_page_config(page_title="Business Tracker", page_icon="🎙️", layout="wide")

st.title("🎙️ Voice Tracker")
st.write("Meeru button nokki record cheyyandi. Data processed ayyaka kindha table lo edit kuda cheyocchu.")

# Audio Recorder
audio_data = mic_recorder(
    start_prompt="⏺️ Start Recording",
    stop_prompt="⏹️ Stop Recording",
    just_once=True,
    key='audio_recorder'
)

if audio_data:
    with st.spinner("Processing your voice... Please wait ⏳"):
        try:
            extracted_json = extract_data_from_audio(audio_data['bytes'])
            update_google_sheet(extracted_json)
            st.success("✅ Data Added! Check the table below.")
            st.rerun() 
        except Exception as e:
            st.error(f"❌ Error vachindi: {e}")

# --- 4. DISPLAY & EDIT SHEET DATA ---
st.markdown("---")
st.subheader("📊 Transaction Management")
st.info("💡 Tip: Double click on any cell to edit spelling. Use the 'Cleared?' column for status.")

with st.spinner("Fetching data from Google Sheets..."):
    try:
        df = fetch_sheet_data()
        if not df.empty:
            # st.data_editor vaadatam valla Table ni edit cheyocchu
            # Column config tho 'Cleared?' ni checkbox la marchavachu
            edited_df = st.data_editor(
                df, 
                use_container_width=True, 
                num_rows="dynamic",
                column_config={
                    "Cleared?": st.column_config.SelectboxColumn(
                        "Cleared?",
                        help="Has the payment been settled?",
                        options=["Yes", "No"],
                        required=True,
                    )
                }
            )
            
            # Save Button: Edits ni Google Sheet ki sync cheyadaniki
            if st.button("💾 Save All Changes to Sheet"):
                sync_edits_to_sheets(edited_df)
                st.rerun()
                
        else:
            st.info("Inka emi data ledu. First record cheyyandi!")
    except Exception as e:

        st.warning(f"Data load error: {e}")


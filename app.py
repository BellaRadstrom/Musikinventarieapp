import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random
from datetime import datetime
import traceback

# --- CONFIG ---
st.set_page_config(page_title="InstrumentDB", layout="wide", page_icon="🎵")

if 'error_log' not in st.session_state:
    st.session_state.error_log = []

def add_log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.error_log.append(f"[{timestamp}] {msg}")

# --- CONNECTION ---
@st.cache_resource
def get_connection():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception as e:
        add_log(f"Anslutningsfel: {str(e)}")
        return None

conn = get_connection()

def load_data():
    try:
        # Vi läser in med worksheet-namnet du har
        data = conn.read(worksheet="Sheet1", ttl=0)
        # Viktigt: Ersätt alla tomma celler med tomma strängar direkt vid start
        return data.fillna("")
    except Exception as e:
        add_log(f"Läsfel: {str(e)}")
        return pd.DataFrame(columns=[
            "Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", 
            "Resurstagg", "Streckkod", "Serienummer", "Status", 
            "Aktuell ägare", "Utlåningsdatum"
        ])

def save_data(df):
    try:
        add_log(f"Försöker spara tabell med {len(df)} rader och {len(df.columns)} kolumner.")
        
        # --- TVÄTT AV DATA (Viktigt för GSheets) ---
        # 1. Se till att alla kolumner från din bild finns med i rätt ordning
        expected_cols = [
            "Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", 
            "Resurstagg", "Streckkod", "Serienummer", "Status", 
            "Aktuell ägare", "Utlåningsdatum"
        ]
        
        # Säkerställ att vi inte skickar extra eller saknade kolumner
        df_to_save = df.reindex(columns=expected_cols)
        
        # 2. Ersätt ALLA NaN/None med tom sträng (""). GSheets hatar NaN.
        df_to_save = df_to_save.fillna("")
        
        # 3. Konvertera allt till strängar för att undvika JSON-serialiseringsfel
        df_to_save = df_to_save.astype(str)

        conn.update(worksheet="Sheet1", data=df_to_save)
        
        st.cache_data.clear()
        add_log("SUCCESS: Skrivning slutförd.")
        return True
    except Exception:
        # Hämta hela stacktracet för att se EXAKT var i koden det dör
        error_details = traceback.format_exc()
        add_log(f"DETALJERAT SKRIVFEL:\n{error_details}")
        st.error("Skrivfel uppstod. Kolla Admin-loggen för fullständig spårning.")
        return False

# Initiera data
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- UI (Samma som tidigare men med säkrare anrop) ---
st.sidebar.title("🎵 Musikinventering")
menu = st.sidebar.radio("MENY", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "⚙️ Admin"])

# ... (Här följer samma vy-kod som tidigare) ...
# (Jag hoppar till Admin för att visa hur loggen nu blir kraftfullare)

if menu == "⚙️ Admin":
    st.title("Systemadministration")
    
    st.subheader("Deep Trace Logg")
    if st.button("Rensa Logg"):
        st.session_state.error_log = []
    
    # Använd en kod-box för att bevara radbrytningar i stacktracet
    full_log = "\n".join(st.session_state.error_log)
    st.code(full_log, language="text")
    
    st.subheader("Aktuell Dataframe")
    st.write(st.session_state.df)
    
    if st.button("Tvinga omladdning"):
        st.cache_resource.clear()
        st.session_state.df = load_data()
        st.rerun()

# --- REPARATION AV REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.title("Registrera")
    with st.form("reg_form"):
        modell = st.text_input("Modell *")
        if st.form_submit_button("Spara"):
            if modell:
                # Vi skapar en dictionary med ALLA kolumner från start
                new_row = {col: "" for col in st.session_state.df.columns}
                new_row.update({
                    "Modell": modell,
                    "Status": "Tillgänglig",
                    "Resurstagg": str(random.randint(1000, 9999))
                })
                
                # Lägg till i session state
                temp_df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                if save_data(temp_df):
                    st.session_state.df = temp_df
                    st.success("Sparat!")

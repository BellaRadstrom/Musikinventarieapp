import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="InstrumentDB", layout="wide", page_icon="🎵")

# --- SESSION STATE FÖR FELSÖKNING ---
if 'error_log' not in st.session_state:
    st.session_state.error_log = []

def add_log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.error_log.append(f"[{timestamp}] {msg}")

# --- ANSLUTNING ---
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
        # Läser in allt. Vi använder worksheet="Sheet1"
        data = conn.read(worksheet="Sheet1", ttl=0)
        return data
    except Exception as e:
        add_log(f"Läsfel: {str(e)}")
        # Skapa tom df med dina exakta kolumner om det skiter sig
        return pd.DataFrame(columns=[
            "Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", 
            "Resurstagg", "Streckkod", "Serienummer", "Status", 
            "Aktuell ägare", "Utlåningsdatum"
        ])

def save_data(df):
    try:
        # Rensa eventuella helt tomma rader innan sparning
        df = df.dropna(how='all')
        conn.update(worksheet="Sheet1", data=df)
        st.cache_data.clear()
        add_log("System: Lyckades skriva till Sheets!")
        return True
    except Exception as e:
        add_log(f"SKRIVFEL: {str(e)}")
        st.error(f"Kunde inte spara: {e}")
        return False

# Initiera data
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- UI ---
st.sidebar.title("🎵 Musikinventering")
menu = st.sidebar.radio("MENY", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "⚙️ Admin"])

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.title("Sök & Boka")
    search = st.text_input("Sök i registret...")
    
    df = st.session_state.df
    if not df.empty:
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        res = df[mask]
        
        for idx, row in res.iterrows():
            status_color = "🟢" if row['Status'] == 'Tillgänglig' else "🔴"
            with st.expander(f"{status_color} {row['Modell']} - {row['Resurstagg']}"):
                col_a, col_b = st.columns(2)
                col_a.write(f"**Märke:** {row['Tillverkare']}")
                col_a.write(f"**Typ:** {row['Typ']}")
                col_b.write(f"**Serie:** {row['Serienummer']}")
                
                if row['Status'] == 'Utlånad':
                    st.info(f"Innehas av: {row['Aktuell ägare']}")
                else:
                    if st.button("Lägg i lånekorg", key=f"add_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.toast("Tillagd!")

    if st.session_state.cart:
        st.divider()
        st.subheader("🛒 Din lånekorg")
        borrower = st.text_input("Vem ska låna?")
        if st.button("BEKRÄFTA UTKÖP") and borrower:
            for item in st.session_state.cart:
                # Uppdatera status baserat på Resurstagg
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 
                                        ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = \
                                        ['Utlånad', borrower, datetime.now().strftime("%Y-%m-%d")]
            
            if save_data(st.session_state.df):
                st.session_state.cart = []
                st.rerun()

# --- VY: REGISTRERA ---
elif menu == "➕ Registrera Nytt":
    st.title("Ny utrustning")
    with st.form("reg_form"):
        c1, c2 = st.columns(2)
        modell = c1.text_input("Modell *")
        marke = c2.text_input("Tillverkare")
        typ = c1.selectbox("Typ", ["Sträng", "Trummor", "Ljud", "Klaviatur", "Övrigt"])
        tag = c2.text_input("Resurstagg (ID)")
        färg = c1.text_input("Färg")
        sn = c2.text_input("Serienummer")
        
        img = st.camera_input("Fota enheten")
        
        if st.form_submit_button("Spara till Sheets"):
            if modell:
                # Skapa rad som matchar dina kolumner exakt
                new_data = {
                    "Enhetsfoto": "", "Modell": modell, "Tillverkare": marke,
                    "Typ": typ, "Färg": färg, "Resurstagg": tag if tag else str(random.randint(1000,9999)),
                    "Streckkod": "", "Serienummer": sn, "Status": "Tillgänglig",
                    "Aktuell ägare": "", "Utlåningsdatum": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
                if save_data(st.session_state.df):
                    st.success("Registrerad!")
            else:
                st.error("Modellnamn saknas!")

# --- VY: ADMIN ---
elif menu == "⚙️ Admin":
    st.title("Systemadministration")
    
    st.subheader("Felsökning & Logg")
    if st.button("Rensa Logg"):
        st.session_state.error_log = []
    
    # Visa loggen i en box
    log_text = "\n".join(st.session_state.error_log)
    st.text_area("Händelseförlopp:", value=log_text, height=200)
    
    st.subheader("Rådata")
    st.dataframe(st.session_state.df)
    
    if st.button("Tvinga omladdning från Sheets"):
        st.cache_resource.clear()
        st.session_state.df = load_data()
        st.rerun()

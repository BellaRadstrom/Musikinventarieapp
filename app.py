import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import qrcode
from PIL import Image
from io import BytesIO
from datetime import datetime
import random

# --- GRUNDINSTÄLLNINGAR ---
st.set_page_config(page_title="InstrumentDB", layout="wide")

# --- FUNKTION FÖR ANSLUTNING ---
def get_clean_connection():
    try:
        # Vi hämtar inställningarna från Secrets
        conf = st.secrets["connections"]["gsheets"].to_dict()
        
        # Vi rensar bort 'type' från konfigurationen för att undvika krock i koden
        if "type" in conf:
            del conf["type"]
            
        # Fixa radbrytningar i nyckeln om de klistrats in på en rad
        if "private_key" in conf:
            conf["private_key"] = conf["private_key"].replace("\\n", "\n")
        
        # Skapa anslutningen med de rena inställningarna
        return st.connection("gsheets", type=GSheetsConnection, **conf)
    except Exception as e:
        st.error(f"Kopplingsfel: {e}")
        return None

# --- HANTERA DATA ---
conn = get_clean_connection()

def load_data():
    if conn:
        try:
            return conn.read(ttl="0s")
        except Exception as e:
            st.session_state.error_log = str(e)
    return pd.DataFrame()

# Initiera session
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- SIDOMENY ---
with st.sidebar:
    st.title("🎵 Musikinventering")
    menu = st.radio("MENY", ["🔍 Sök & Inventarie", "➕ Lägg till", "🛒 Lånekorg", "🔄 Återlämning", "⚙️ System"])
    if st.button("🔄 Uppdatera från molnet"):
        st.session_state.df = load_data()
        st.rerun()

# --- VY: SÖK & INVENTARIE ---
if menu == "🔍 Sök & Inventarie":
    st.title("Sök & Inventarie")
    df = st.session_state.df
    if not df.empty:
        search = st.text_input("Sök i registret", placeholder="Modell, märke eller ID...")
        # Filtrera datan baserat på sökning
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        
        for idx, row in df[mask].iterrows():
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"**{row['Modell']}** | {row.get('Tillverkare', '')} | ID: {row['Resurstagg']}")
            status = row.get('Status', 'Tillgänglig')
            c2.write(f"Status: {status}")
            if status == 'Tillgänglig' and c3.button("Låna", key=f"l_{idx}"):
                st.session_state.cart.append(row.to_dict())
                st.toast(f"{row['Modell']} tillagd")
    else:
        st.warning("Hittade ingen data i ditt Google Sheet.")

# --- VY: LÄGG TILL (MED KAMERA) ---
elif menu == "➕ Lägg till":
    st.title("Registrera ny utrustning")
    with st.form("new_item"):
        col1, col2 = st.columns(2)
        modell = col1.text_input("Modell *")
        tillverkare = col2.text_input("Tillverkare")
        tagg = col1.text_input("Resurstagg / ID")
        st.write("---")
        foto = st.camera_input("Ta kontrollfoto")
        
        if st.form_submit_button("Spara i databas"):
            if modell:
                new_data = {
                    "Modell": modell, 
                    "Tillverkare": tillverkare, 
                    "Resurstagg": tagg if tagg else str(random.randint(1000, 9999)),
                    "Status": "Tillgänglig",
                    "Aktuell ägare": ""
                }
                # Uppdatera lokal data och skicka till Google
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
                if conn:
                    conn.update(data=st.session_state.df)
                    st.success(f"{modell} sparad!")
                    st.rerun()
            else:
                st.error("Modellnamn krävs.")

# --- VY: LÄNEKORG ---
elif menu == "🛒 Lånekorg":
    st.title("Utlåning")
    if st.session_state.cart:
        for item in st.session_state.cart:
            st.write(f"• **{item['Modell']}** ({item['Resurstagg']})")
        namn = st.text_input("Låntagarens namn")
        if st.button("Bekräfta utlån") and namn:
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare']] = ['Utlånad', namn]
            if conn:
                conn.update(data=st.session_state.df)
                st.session_state.cart = []
                st.success("Utlåning klar!")
                st.rerun()
    else:
        st.info("Lånekorgen är tom.")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    df = st.session_state.df
    loaned = df[df['Status'] == 'Utlånad']
    if not loaned.empty:
        choice = st.selectbox("Välj föremål att lämna tillbaka:", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
        if st.button("Registrera retur"):
            tag = choice.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Aktuell ägare']] = ['Tillgänglig', '']
            if conn:
                conn.update(data=st.session_state.df)
                st.success("Instrumentet är nu ledigt igen!")
                st.rerun()
    else:
        st.info("Inga instrument är utlånade just nu.")

# --- VY: SYSTEM ---
elif menu == "⚙️ System":
    st.title("System & Diagnostik")
    st.success("Anslutningen mot Google Sheets fungerar!")
    st.write("### Aktuell databas (Rådata)")
    st.dataframe(st.session_state.df)

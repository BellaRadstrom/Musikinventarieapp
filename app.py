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

# --- FUNKTION FÖR ATT LAGA NYCKELN ---
def get_clean_connection():
    try:
        # Hämta råa secrets
        conf = st.secrets["connections"]["gsheets"].to_dict()
        # Rensa nyckeln från eventuella dubbla backslash eller felaktiga radbrytningar
        if "private_key" in conf:
            conf["private_key"] = conf["private_key"].replace("\\n", "\n")
        
        # Skapa anslutningen manuellt med de rensade inställningarna
        return st.connection("gsheets", type=GSheetsConnection, **conf)
    except Exception as e:
        st.error(f"Kopplingsfel: {e}")
        return None

# --- LADDA DATA ---
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
    if st.button("🔄 Uppdatera lista"):
        st.session_state.df = load_data()
        st.rerun()

# --- VY: SÖK & INVENTARIE ---
if menu == "🔍 Sök & Inventarie":
    st.title("Sök & Inventarie")
    df = st.session_state.df
    if not df.empty:
        search = st.text_input("Sök i registret", placeholder="Sök på modell, märke eller ID...")
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        
        for idx, row in df[mask].iterrows():
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"**{row['Modell']}** | {row['Tillverkare']} | ID: {row['Resurstagg']}")
            c2.write(f"Status: {row['Status']}")
            if row['Status'] == 'Tillgänglig' and c3.button("Låna", key=f"l_{idx}"):
                st.session_state.cart.append(row.to_dict())
                st.toast("Tillagd i korg")
    else:
        st.warning("Ingen data hittades. Kontrollera 'System' för felmeddelanden.")

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
                    "Status": "Tillgänglig"
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
                # Försök spara till Google Sheets
                if conn:
                    conn.update(data=st.session_state.df)
                    st.success("Sparat!")
                    st.rerun()
            else:
                st.error("Du måste fylla i modellnamn.")

# --- VY: LÅNEKORG ---
elif menu == "🛒 Lånekorg":
    st.title("Utlåning")
    if st.session_state.cart:
        for i, item in enumerate(st.session_state.cart):
            st.write(f"• **{item['Modell']}** ({item['Resurstagg']})")
        
        namn = st.text_input("Vem lånar?")
        if st.button("Bekräfta lån") and namn:
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare']] = ['Utlånad', namn]
            if conn:
                conn.update(data=st.session_state.df)
                st.session_state.cart = []
                st.success("Lånet registrerat!")
                st.rerun()
    else:
        st.info("Korgen är tom.")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        choice = st.selectbox("Välj föremål:", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
        if st.button("Registrera retur"):
            tag = choice.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Aktuell ägare']] = ['Tillgänglig', '']
            if conn:
                conn.update(data=st.session_state.df)
                st.success("Retur klar!")
                st.rerun()
    else:
        st.info("Inga utlånade föremål.")

# --- VY: SYSTEM ---
elif menu == "⚙️ System":
    st.title("System & Diagnostik")
    if 'error_log' in st.session_state:
        st.error(f"Senaste felmeddelande: {st.session_state.error_log}")
    else:
        st.success("Anslutningen mot Google Sheets fungerar!")
    
    st.write("### Rådata")
    st.dataframe(st.session_state.df)

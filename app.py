import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random

# --- GRUNDINSTÄLLNINGAR ---
st.set_page_config(page_title="InstrumentDB", layout="wide", page_icon="🎵")

# --- ANSLUTNING ---
# Vi använder st.cache_resource för att inte ansluta på nytt vid varje klick
@st.cache_resource
def get_connection():
    try:
        # Helt ren anslutning - den hittar själv "gsheets" i secrets
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception as e:
        st.error(f"Kopplingsfel: Kontrollera dina Secrets. Felkod: {e}")
        return None

conn = get_connection()

# --- DATAFUNKTIONER ---
def load_data():
    if conn:
        try:
            # Vi läser Sheet1. ttl=0 gör att vi alltid får färsk data vid refresh.
            return conn.read(worksheet="Sheet1", ttl=0)
        except Exception as e:
            st.error(f"Kunde inte läsa kalkylbladet: {e}")
            return pd.DataFrame(columns=["Modell", "Tillverkare", "Resurstagg", "Status", "Låntagare"])
    return pd.DataFrame()

def save_data(df):
    if conn:
        try:
            conn.update(worksheet="Sheet1", data=df)
            st.toast("✅ Synkat med Google Sheets!", icon="☁️")
            return True
        except Exception as e:
            st.error(f"Kunde inte spara: {e}")
            return False
    return False

# Initiera session state
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- SIDOMENY ---
st.sidebar.title("🎵 Musikinventering")
menu = st.sidebar.radio("GÅ TILL:", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "⚙️ Admin"])

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.title("Instrumentregister")
    
    col1, col2 = st.columns([3, 1])
    search = col1.text_input("Sök...", placeholder="Modell eller märke")
    
    if col2.button("🔄 Uppdatera lista"):
        st.session_state.df = load_data()
        st.rerun()

    df = st.session_state.df
    if not df.empty:
        # Filtrering
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        display_df = df[mask]

        for idx, row in display_df.iterrows():
            with st.expander(f"{row['Modell']} ({row['Tillverkare']}) - {row['Status']}"):
                st.write(f"**ID:** {row['Resurstagg']}")
                
                if row['Status'] == 'Utlånad':
                    st.warning(f"⚠️ Utlånad till: {row['Låntagare']}")
                else:
                    if st.button("Lägg i lånekorg", key=f"btn_{idx}"):
                        if not any(item['Resurstagg'] == row['Resurstagg'] for item in st.session_state.cart):
                            st.session_state.cart.append(row.to_dict())
                            st.toast(f"{row['Modell']} tillagd!")
                        else:
                            st.warning("Redan i korgen")

    # Varukorgs-sektion
    if st.session_state.cart:
        st.divider()
        st.subheader("🛒 Din lånekorg")
        for i, item in enumerate(st.session_state.cart):
            st.info(f"{item['Modell']} ({item['Resurstagg']})")
        
        namn = st.text_input("Vem ska låna dessa?")
        col_c1, col_c2 = st.columns(2)
        
        if col_c1.button("BEKRÄFTA LÅN", type="primary") and namn:
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Låntagare']] = ['Utlånad', namn]
            if save_data(st.session_state.df):
                st.session_state.cart = []
                st.rerun()
        
        if col_c2.button("Töm korg"):
            st.session_state.cart = []
            st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.title("Ny utrustning")
    
    with st.form("new_instrument"):
        m = st.text_input("Modell *")
        t = st.text_input("Tillverkare")
        tag = st.text_input("ID / Resurstagg (lämna tom för auto)")
        
        img_file = st.camera_input("Ta bild")
        
        if st.form_submit_button("SPARA"):
            if m:
                new_tag = tag if tag else str(random.randint(10000, 99999))
                new_row = pd.DataFrame([{
                    "Modell": m, "Tillverkare": t, "Resurstagg": new_tag, 
                    "Status": "Tillgänglig", "Låntagare": ""
                }])
                st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
                if save_data(st.session_state.df):
                    st.success(f"{m} sparad!")
            else:
                st.error("Modell krävs.")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    df = st.session_state.df
    loaned = df[df['Status'] == 'Utlånad']
    
    if not loaned.empty:
        selected_label = st.selectbox("Välj föremål att lämna tillbaka:", 
                                     loaned.apply(lambda r: f"{r['Modell']} ({r['Låntagare']})", axis=1))
        
        if st.button("CHECK IN"):
            # Hitta rätt rad baserat på urvalet
            idx = loaned.index[loaned.apply(lambda r: f"{r['Modell']} ({r['Låntagare']})", axis=1) == selected_label][0]
            st.session_state.df.at[idx, 'Status'] = 'Tillgänglig'
            st.session_state.df.at[idx, 'Låntagare'] = ''
            if save_data(st.session_state.df):
                st.rerun()
    else:
        st.info("Inga lånade instrument.")

# --- VY: ADMIN ---
elif menu == "⚙️ Admin":
    st.title("Admin")
    st.dataframe(st.session_state.df, use_container_width=True)
    if st.button("Hård omstart (Rensa cache)"):
        st.cache_resource.clear()
        st.session_state.df = load_data()
        st.rerun()

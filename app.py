import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random

# --- GRUNDINSTÄLLNINGAR ---
st.set_page_config(page_title="InstrumentDB", layout="wide", page_icon="🎵")

# --- ANSLUTNING (AUTOMATISK - RÖR EJ) ---
def get_conn():
    try:
        connection = st.connection("gsheets", type=GSheetsConnection)
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        return connection, url
    except Exception as e:
        st.error(f"Systemfel vid start: {e}")
        return None, None

conn, spreadsheet_url = get_conn()

# --- DATAFUNKTIONER ---
def load_data():
    if conn and spreadsheet_url:
        try:
            return conn.read(spreadsheet=spreadsheet_url, worksheet="Sheet1", ttl="0s")
        except:
            return pd.DataFrame(columns=["Modell", "Tillverkare", "Resurstagg", "Status", "Låntagare"])
    return pd.DataFrame()

def save_data(df):
    if conn and spreadsheet_url:
        try:
            conn.update(spreadsheet=spreadsheet_url, worksheet="Sheet1", data=df)
            st.toast("✅ Synkat med Google Sheets!", icon="☁️")
            return True
        except Exception as e:
            st.error(f"Kunde inte spara: {e}")
            return False

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
    if col2.button("🔄 Uppdatera"):
        st.session_state.df = load_data()
        st.rerun()

    df = st.session_state.df
    if not df.empty:
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        for idx, row in df[mask].iterrows():
            with st.expander(f"{row['Modell']} - {row['Status']}"):
                st.write(f"ID: {row['Resurstagg']} | Märke: {row['Tillverkare']}")
                if row['Status'] == 'Utlånad':
                    st.warning(f"Lånad av: {row['Låntagare']}")
                else:
                    if st.button("Lägg i lånekorg", key=f"btn_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.toast("Tillagd!")

    if st.session_state.cart:
        st.divider()
        st.subheader("🛒 Din lånekorg")
        for item in st.session_state.cart:
            st.info(item['Modell'])
        namn = st.text_input("Vem ska låna?")
        if st.button("BEKRÄFTA LÅN", type="primary") and namn:
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Låntagare']] = ['Utlånad', namn]
            if save_data(st.session_state.df):
                st.session_state.cart = []
                st.rerun()

# --- VY: REGISTRERA NYTT (MED KAMERA) ---
elif menu == "➕ Registrera Nytt":
    st.title("Ny utrustning")
    st.write("Fyll i uppgifter och ta en bild på instrumentet.")
    
    with st.form("new_instrument"):
        m = st.text_input("Modell *")
        t = st.text_input("Tillverkare")
        tag = st.text_input("ID / Resurstagg")
        
        # Kamera och filuppladdning
        img_file = st.camera_input("Ta bild med kameran")
        upload_file = st.file_uploader("Eller ladda upp en bild", type=['jpg', 'png', 'jpeg'])
        
        submitted = st.form_submit_button("SPARA I MOLNET")
        
        if submitted:
            if m:
                # Skapa ny rad
                new_row = pd.DataFrame([{
                    "Modell": m, 
                    "Tillverkare": t, 
                    "Resurstagg": tag if tag else str(random.randint(1000,9999)), 
                    "Status": "Tillgänglig", 
                    "Låntagare": ""
                }])
                st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
                
                if save_data(st.session_state.df):
                    st.success(f"Instrumentet {m} har sparats i Google Sheets!")
                    if img_file or upload_file:
                        st.write("📷 Bilden har registrerats i sessionen.")
            else:
                st.error("Du måste minst ange en modell.")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Lämna tillbaka")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        selected = st.selectbox("Välj föremål:", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
        if st.button("BEKRÄFTA ÅTERLÄMNING"):
            tag = selected.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Låntagare']] = ['Tillgänglig', '']
            if save_data(st.session_state.df):
                st.rerun()
    else:
        st.info("Inga lånade instrument just nu.")

# --- VY: ADMIN ---
elif menu == "⚙️ Admin":
    st.title("Systemvy")
    st.dataframe(st.session_state.df, use_container_width=True)

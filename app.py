import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random

# --- GRUNDINSTÄLLNINGAR ---
st.set_page_config(page_title="InstrumentDB", layout="wide", page_icon="🎵")

# CSS för bättre utseende
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 20px; height: 3em; }
    .stExpander { border: 1px solid #f0f2f6; border-radius: 10px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- ANSLUTNING (RENSAD FRÅN KROCKAR) ---
def get_conn():
    try:
        if "connections" not in st.secrets:
            st.error("Hittar inga Secrets!")
            return None, None
            
        conf = st.secrets["connections"]["gsheets"].to_dict()
        sheet_url = conf.get("spreadsheet")
        
        # PEM-tvätt av nyckeln
        raw_key = conf.get("private_key", "")
        clean_key = raw_key.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "").replace("\\n", "\n").replace("\n", "").replace(" ", "").strip()
        chunks = [clean_key[i:i+64] for i in range(0, len(clean_key), 64)]
        final_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(chunks) + "\n-----END PRIVATE KEY-----\n"
        
        # VIKTIGT: Vi skapar creds UTAN 'type' för att undvika "multiple values"-felet
        creds = {
            "project_id": conf.get("project_id"),
            "private_key_id": conf.get("private_key_id"),
            "private_key": final_key,
            "client_email": conf.get("client_email"),
            "client_id": conf.get("client_id"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": conf.get("client_x509_cert_url")
        }
        
        # Vi skickar 'type' separat här, och det finns nu INTE i **creds
        return st.connection("gsheets", type=GSheetsConnection, **creds), sheet_url
    except Exception as e:
        st.error(f"Systemfel vid start: {e}")
        return None, None

conn, sheet_url = get_conn()

# --- HJÄLPFUNKTIONER ---
def load_data():
    if conn and sheet_url:
        try:
            return conn.read(spreadsheet=sheet_url, worksheet="Sheet1", ttl="0s")
        except:
            return pd.DataFrame(columns=["Modell", "Tillverkare", "Resurstagg", "Status", "Låntagare"])
    return pd.DataFrame()

def save_data(df):
    if conn and sheet_url:
        try:
            conn.update(spreadsheet=sheet_url, worksheet="Sheet1", data=df)
            st.toast("✅ Synkat med Google Sheets!", icon="☁️")
            return True
        except Exception as e:
            st.error(f"Kunde inte spara: {e}")
            return False

# Initiera session
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- MENY ---
st.sidebar.title("🎵 Musikinventering")
menu = st.sidebar.radio("MENY", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "⚙️ Admin"])

if menu == "🔍 Sök & Låna":
    st.title("Instrumentregister")
    
    col1, col2 = st.columns([3, 1])
    search = col1.text_input("Sök...", placeholder="Modell, märke eller ID")
    if col2.button("🔄 Uppdatera"):
        st.session_state.df = load_data()
        st.rerun()

    df = st.session_state.df
    if not df.empty:
        # Säkerställ att alla kolumner finns
        for col in ["Modell", "Tillverkare", "Resurstagg", "Status", "Låntagare"]:
            if col not in df.columns: df[col] = ""
            
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        for idx, row in df[mask].iterrows():
            with st.expander(f"{row['Modell']} - {row['Status']}"):
                c1, c2 = st.columns(2)
                c1.write(f"**Märke:** {row['Tillverkare']}")
                c1.write(f"**ID:** {row['Resurstagg']}")
                if row['Status'] == 'Utlånad':
                    c1.write(f"**Lånad av:** {row['Låntagare']}")
                
                if row['Status'] != 'Utlånad':
                    if c2.button("Lägg i lånekorg", key=f"add_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.toast("Lagt i korgen")

    if st.session_state.cart:
        st.divider()
        st.subheader("🛒 Din lånekorg")
        for item in st.session_state.cart:
            st.info(f"{item['Modell']} ({item['Resurstagg']})")
        
        namn = st.text_input("Låntagarens namn")
        if st.button("BEKRÄFTA LÅN", type="primary"):
            if namn:
                for item in st.session_state.cart:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Låntagare']] = ['Utlånad', namn]
                if save_data(st.session_state.df):
                    st.session_state.cart = []
                    st.rerun()
            else:
                st.warning("Skriv ett namn!")

elif menu == "➕ Registrera Nytt":
    st.title("Lägg till utrustning")
    with st.form("new_item"):
        m = st.text_input("Modell *")
        t = st.text_input("Tillverkare")
        tag = st.text_input("ID/Tagg")
        st.camera_input("Foto")
        if st.form_submit_button("SPARA"):
            if m:
                new_row = pd.DataFrame([{"Modell": m, "Tillverkare": t, "Resurstagg": tag if tag else str(random.randint(1000,9999)), "Status": "Tillgänglig", "Låntagare": ""}])
                st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
                if save_data(st.session_state.df):
                    st.success("Sparat!")
            else:
                st.error("Modellnamn saknas!")

elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        selected = st.selectbox("Välj föremål:", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
        if st.button("MARKERA SOM ÅTERLÄMNAD"):
            tag = selected.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Låntagare']] = ['Tillgänglig', '']
            if save_data(st.session_state.df):
                st.rerun()
    else:
        st.info("Inga lånade föremål.")

elif menu == "⚙️ Admin":
    st.title("System")
    st.dataframe(st.session_state.df)
    if st.button("Rensa Cache"):
        st.cache_data.clear()
        st.rerun()

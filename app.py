import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random

# --- GRUNDINSTÄLLNINGAR ---
st.set_page_config(page_title="InstrumentDB", layout="wide", page_icon="🎵")

# --- ANSLUTNING (MINIMERAD FÖR ATT UNDVIKA FEL) ---
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
        
        # Vi skapar ett objekt som följer Googles exakta standard för Service Accounts
        # Vi skickar ENDAST dessa i st.connection
        service_account_info = {
            "type": "service_account",
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
        
        # Här är tricket: Vi skickar in info under parametern 'service_account_info'
        # Istället för att sprida ut dem som lösa argument.
        return st.connection("gsheets", type=GSheetsConnection, service_account_info=service_account_info), sheet_url
    except Exception as e:
        st.error(f"Systemfel vid start: {e}")
        return None, None

conn, spreadsheet_url = get_conn()

# --- HJÄLPFUNKTIONER ---
def load_data():
    if conn and spreadsheet_url:
        try:
            # Vi tvingar läsning från Sheet1
            return conn.read(spreadsheet=spreadsheet_url, worksheet="Sheet1", ttl="0s")
        except Exception as e:
            # Om arket är tomt eller inte hittas
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
        # Säkerställ kolumner
        for col in ["Modell", "Tillverkare", "Resurstagg", "Status", "Låntagare"]:
            if col not in df.columns: df[col] = ""
            
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        for idx, row in df[mask].iterrows():
            with st.expander(f"{row['Modell']} - {row['Status']}"):
                st.write(f"**Märke:** {row['Tillverkare']} | **ID:** {row['Resurstagg']}")
                if row['Status'] == 'Utlånad':
                    st.warning(f"Lånad av: {row['Låntagare']}")
                else:
                    if st.button("Lägg i korg", key=f"add_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.toast("Lagt i korgen")

    if st.session_state.cart:
        st.divider()
        st.subheader("🛒 Lånekorg")
        for item in st.session_state.cart: st.info(item['Modell'])
        namn = st.text_input("Låntagarens namn")
        if st.button("SLUTFÖR LÅN", type="primary") and namn:
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Låntagare']] = ['Utlånad', namn]
            if save_data(st.session_state.df):
                st.session_state.cart = []
                st.rerun()

elif menu == "➕ Registrera Nytt":
    st.title("Ny utrustning")
    with st.form("new"):
        m = st.text_input("Modell *")
        t = st.text_input("Tillverkare")
        tag = st.text_input("ID")
        if st.form_submit_button("SPARA"):
            if m:
                new_row = pd.DataFrame([{"Modell": m, "Tillverkare": t, "Resurstagg": tag if tag else str(random.randint(1000,9999)), "Status": "Tillgänglig", "Låntagare": ""}])
                st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
                if save_data(st.session_state.df): st.rerun()

elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        selected = st.selectbox("Välj föremål:", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
        if st.button("REDA UT RETUR"):
            tag = selected.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Låntagare']] = ['Tillgänglig', '']
            save_data(st.session_state.df)
            st.rerun()

elif menu == "⚙️ Admin":
    st.title("Systemvy")
    st.dataframe(st.session_state.df)

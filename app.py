import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random
import re

# --- GRUNDINSTÄLLNINGAR ---
st.set_page_config(page_title="InstrumentDB", layout="wide")

# --- DEN "SMARTA" ANSLUTNINGSFUNKTIONEN ---
def get_robust_connection():
    try:
        # 1. Hämta rådata från Secrets
        if "connections" not in st.secrets or "gsheets" not in st.secrets["connections"]:
            return None, "Hittar inga Secrets i Streamlit Cloud."
            
        conf = st.secrets["connections"]["gsheets"].to_dict()
        sheet_url = conf.get("spreadsheet")
        
        # 2. FIXA PRIVATE KEY (PEM-TVÄTT)
        # Vi extraherar bara själva kodsträngen och bygger om ramen helt
        raw_key = conf.get("private_key", "")
        
        # Ta bort allt som inte är själva nyckel-innehållet
        # Vi rensar bort headers, footers, \n, radbrytningar och mellanslag
        clean_key = raw_key.replace("-----BEGIN PRIVATE KEY-----", "") \
                           .replace("-----END PRIVATE KEY-----", "") \
                           .replace("\\n", "").replace("\n", "").replace(" ", "").strip()
        
        # Google kräver att nyckeln har radbrytningar var 64:e tecken. Vi fixar det:
        chunks = [clean_key[i:i+64] for i in range(0, len(clean_key), 64)]
        final_pem_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(chunks) + "\n-----END PRIVATE KEY-----\n"
        
        # 3. Skapa ett nytt konfigurationsobjekt med den lagade nyckeln
        # Vi skickar med allt Google behöver i ett format biblioteket gillar
        creds = {
            "type": "service_account",
            "project_id": conf.get("project_id"),
            "private_key_id": conf.get("private_key_id"),
            "private_key": final_pem_key,
            "client_email": conf.get("client_email"),
            "client_id": conf.get("client_id"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": conf.get("client_x509_cert_url")
        }
        
        # 4. Anslut (vi använder TTL 0 för att alltid ha färsk data)
        conn = st.connection("gsheets", type=GSheetsConnection, **creds)
        return conn, sheet_url
    except Exception as e:
        return None, str(e)

# Försök ansluta
conn, spreadsheet_url = get_robust_connection()

# --- DATAFUNKTIONER ---
def load_data():
    if conn and spreadsheet_url:
        try:
            return conn.read(spreadsheet=spreadsheet_url, ttl="0s")
        except Exception as e:
            st.session_state.error_log = f"Läsfel från Google: {e}"
    return pd.DataFrame(columns=["Modell", "Tillverkare", "Resurstagg", "Status", "Aktuell ägare"])

# Initiera session
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- GRÄNSSNITT ---
with st.sidebar:
    st.title("🎵 Musikinventering")
    menu = st.radio("MENY", ["🔍 Sök & Inventarie", "➕ Lägg till (Kamera)", "🛒 Lånekorg", "🔄 Återlämning", "⚙️ System"])
    if st.button("🔄 Synka med Google"):
        st.session_state.df = load_data()
        st.rerun()

# --- VYER (Förenklade för att säkerställa att de fungerar) ---
if menu == "🔍 Sök & Inventarie":
    st.title("Inventarie")
    df = st.session_state.df
    if not df.empty:
        search = st.text_input("Sök...", placeholder="Modell eller ID")
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        for idx, row in df[mask].iterrows():
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"**{row['Modell']}** ({row.get('Resurstagg', 'N/A')})")
            status = row.get('Status', 'Tillgänglig')
            c2.write(status)
            if status == 'Tillgänglig' and c3.button("Låna", key=f"l_{idx}"):
                st.session_state.cart.append(row.to_dict())
                st.toast("Tillagd!")
    else:
        st.warning("Ingen data hittades. Se fliken 'System'.")

elif menu == "➕ Lägg till (Kamera)":
    st.title("Lägg till")
    with st.form("add"):
        m = st.text_input("Modell *")
        t = st.text_input("Tillverkare")
        tag = st.text_input("ID")
        st.camera_input("Ta bild")
        if st.form_submit_button("Spara"):
            if m:
                new_row = {"Modell": m, "Tillverkare": t, "Resurstagg": tag if tag else str(random.randint(1000,9999)), "Status": "Tillgänglig", "Aktuell ägare": ""}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                if conn:
                    conn.update(spreadsheet=spreadsheet_url, data=st.session_state.df)
                    st.success("Sparat!")
                    st.rerun()

elif menu == "🛒 Lånekorg":
    st.title("Lånekorg")
    if st.session_state.cart:
        for item in st.session_state.cart: st.write(f"• {item['Modell']}")
        namn = st.text_input("Vem lånar?")
        if st.button("Slutför") and namn:
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare']] = ['Utlånad', namn]
            if conn:
                conn.update(spreadsheet=spreadsheet_url, data=st.session_state.df)
                st.session_state.cart = []
                st.rerun()
    else: st.info("Korgen är tom.")

elif menu == "🔄 Återlämning":
    st.title("Retur")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        choice = st.selectbox("Välj:", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
        if st.button("Lämna tillbaka"):
            tag = choice.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Aktuell ägare']] = ['Tillgänglig', '']
            if conn:
                conn.update(spreadsheet=spreadsheet_url, data=st.session_state.df)
                st.rerun()

elif menu == "⚙️ System":
    st.title("System & Diagnostik")
    if 'error_log' in st.session_state:
        st.error(st.session_state.error_log)
    else:
        st.success("Anslutningen fungerar utmärkt!")
    st.write("### Aktuell Tabell")
    st.dataframe(st.session_state.df)

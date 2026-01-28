import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random

# --- GRUNDINSTÄLLNINGAR ---
st.set_page_config(page_title="InstrumentDB", layout="wide", page_icon="🎵")

# --- ANSLUTNING (TILLBAKA TILL DEN FUNGERANDE MODELLEN) ---
def get_conn():
    try:
        if "connections" not in st.secrets:
            st.error("Hittar inga Secrets!")
            return None, None
            
        conf = st.secrets["connections"]["gsheets"].to_dict()
        sheet_url = conf.get("spreadsheet")
        
        # PEM-tvätt (Denna vet vi fungerar)
        raw_key = conf.get("private_key", "")
        clean_key = raw_key.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "").replace("\\n", "\n").replace("\n", "").replace(" ", "").strip()
        chunks = [clean_key[i:i+64] for i in range(0, len(clean_key), 64)]
        final_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(chunks) + "\n-----END PRIVATE KEY-----\n"
        
        # Vi skickar ENDAST de två absolut viktigaste sakerna biblioteket behöver för att inte krocka
        # Resten lämnar vi till Streamlits inbyggda hantering
        creds = {
            "client_email": conf.get("client_email"),
            "private_key": final_key
        }
        
        # Vi anropar anslutningen med endast mail och den tvättade nyckeln
        return st.connection("gsheets", type=GSheetsConnection, **creds), sheet_url
    except Exception as e:
        st.error(f"Systemfel vid start: {e}")
        return None, None

conn, spreadsheet_url = get_conn()

# --- DATAFUNKTIONER ---
def load_data():
    if conn and spreadsheet_url:
        try:
            # Vi läser från Sheet1. Kontrollera att fliken heter så i ditt ark!
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

# Initiera session
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- MENY ---
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
        # Säkerställ att kolumnerna finns
        for c in ["Modell", "Tillverkare", "Resurstagg", "Status", "Låntagare"]:
            if c not in df.columns: df[c] = ""
            
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
        st.subheader("🛒 Lånekorg")
        for item in st.session_state.cart: st.info(item['Modell'])
        namn = st.text_input("Vem ska låna?")
        if st.button("BEKRÄFTA LÅN", type="primary") and namn:
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Låntagare']] = ['Utlånad', namn]
            if save_data(st.session_state.df):
                st.session_state.cart = []
                st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.title("Lägg till")
    with st.form("new"):
        m = st.text_input("Modell *")
        t = st.text_input("Tillverkare")
        tag = st.text_input("ID")
        if st.form_submit_button("SPARA"):
            if m:
                new_row = pd.DataFrame([{"Modell": m, "Tillverkare": t, "Resurstagg": tag if tag else str(random.randint(1000,9999)), "Status": "Tillgänglig", "Låntagare": ""}])
                st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
                if save_data(st.session_state.df):
                    st.success("Sparat!")
            else: st.error("Namn saknas")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Retur")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        selected = st.selectbox("Välj föremål:", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
        if st.button("MARKERA SOM ÅTERLÄMNAD"):
            tag = selected.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Låntagare']] = ['Tillgänglig', '']
            if save_data(st.session_state.df):
                st.rerun()

# --- VY: ADMIN ---
elif menu == "⚙️ Admin":
    st.title("Systemvy")
    st.dataframe(st.session_state.df)

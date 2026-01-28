import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random

# --- GRUNDINSTÄLLNINGAR ---
st.set_page_config(page_title="InstrumentDB", layout="wide", page_icon="🎵")

# Snyggare knappar och layout
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 20px; height: 3em; background-color: #f0f2f6; }
    .stActionButton { background-color: #007bff !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- ANSLUTNING (DIN TVÄTTADE NYCKEL) ---
def get_conn():
    try:
        conf = st.secrets["connections"]["gsheets"].to_dict()
        # PEM-tvätt
        raw_key = conf.get("private_key", "")
        clean_key = raw_key.replace("-----BEGIN PRIVATE KEY-----", "").replace("-----END PRIVATE KEY-----", "").replace("\\n", "\n").replace("\n", "").replace(" ", "").strip()
        chunks = [clean_key[i:i+64] for i in range(0, len(clean_key), 64)]
        final_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(chunks) + "\n-----END PRIVATE KEY-----\n"
        
        creds = {
            "type": "service_account",
            "project_id": conf.get("project_id"),
            "private_key_id": conf.get("private_key_id"),
            "private_key": final_key,
            "client_email": conf.get("client_email"),
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        return st.connection("gsheets", type=GSheetsConnection, **creds), conf.get("spreadsheet")
    except Exception as e:
        st.error(f"Systemfel vid start: {e}")
        return None, None

conn, sheet_url = get_conn()

# --- FUNKTIONER FÖR DATA ---
def load_data():
    try:
        # Vi tvingar den att läsa fliken "Sheet1"
        return conn.read(spreadsheet=sheet_url, worksheet="Sheet1", ttl="0s")
    except:
        # Om arket är tomt, skapa en mall
        return pd.DataFrame(columns=["Modell", "Tillverkare", "Resurstagg", "Status", "Låntagare"])

def save_data(df):
    try:
        conn.update(spreadsheet=sheet_url, worksheet="Sheet1", data=df)
        st.toast("✅ Synkat med Google Sheets!", icon="☁️")
        return True
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")
        return False

# Initiera data
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- SIDOMENY ---
st.sidebar.title("🎵 Musik-Labbet")
menu = st.sidebar.radio("GÅ TILL:", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "⚙️ Admin"])

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.title("Instrumentregister")
    
    col1, col2 = st.columns([3, 1])
    search = col1.text_input("Sök i lagret...", placeholder="Modell, märke eller ID")
    if col2.button("🔄 Uppdatera"):
        st.session_state.df = load_data()
        st.rerun()

    df = st.session_state.df
    if not df.empty:
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        for idx, row in df[mask].iterrows():
            with st.expander(f"{row['Modell']} - {row['Status']}"):
                c1, c2 = st.columns(2)
                c1.write(f"**Märke:** {row['Tillverkare']}")
                c1.write(f"**ID:** {row['Resurstagg']}")
                
                if row['Status'] == 'Tillgänglig':
                    if c2.button("Lägg i lånekorg", key=f"add_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.toast("Lagt i korgen")
                else:
                    c2.warning(f"Utlånad till: {row.get('Låntagare', 'Okänd')}")

    # --- LÅNEKORG (Floating style) ---
    if st.session_state.cart:
        st.write("---")
        st.subheader("🛒 Din lånekorg")
        for i, item in enumerate(st.session_state.cart):
            st.info(f"{item['Modell']} ({item['Resurstagg']})")
        
        lontagare = st.text_input("Vem ska låna?")
        if st.button("BEKRÄFTA LÅN", type="primary"):
            if lontagare:
                for item in st.session_state.cart:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Låntagare']] = ['Utlånad', lontagare]
                if save_data(st.session_state.df):
                    st.session_state.cart = []
                    st.success(f"Lånet registrerat på {lontagare}!")
                    st.rerun()
            else:
                st.error("Du måste skriva ett namn!")

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.title("Ny utrustning")
    with st.form("new_tool"):
        m = st.text_input("Modell *")
        t = st.text_input("Märke/Tillverkare")
        tag = st.text_input("Resurstagg (ID)")
        st.camera_input("Ta ett foto (valfritt)")
        
        if st.form_submit_button("SPARA I SYSTEMET"):
            if m:
                new_id = tag if tag else f"M-{random.randint(1000, 9999)}"
                new_row = pd.DataFrame([{"Modell": m, "Tillverkare": t, "Resurstagg": str(new_id), "Status": "Tillgänglig", "Låntagare": ""}])
                st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
                if save_data(st.session_state.df):
                    st.success("Instrumentet är nu registrerat!")
            else:
                st.error("Modellnamn är obligatoriskt.")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Lämna tillbaka")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        selected = st.selectbox("Välj föremål:", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
        if st.button("MARKERA SOM ÅTERLÄMNAD"):
            tag = selected.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Låntagare']] = ['Tillgänglig', '']
            if save_data(st.session_state.df):
                st.success("Tack! Instrumentet är nu ledigt.")
                st.rerun()
    else:
        st.info("Inga utlånade föremål just nu.")

# --- VY: ADMIN ---
elif menu == "⚙️ Admin":
    st.title("Systemadministration")
    st.write("Här kan du se all data i tabellform.")
    st.dataframe(st.session_state.df, use_container_width=True)
    
    if st.button("Radera all lokal cache"):
        st.cache_data.clear()
        st.rerun()

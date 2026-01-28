import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random

# --- GRUNDINSTÄLLNINGAR ---
st.set_page_config(page_title="InstrumentDB", layout="wide")

# --- ROBUST ANSLUTNINGSFUNKTION ---
def get_robust_connection():
    try:
        if "connections" not in st.secrets or "gsheets" not in st.secrets["connections"]:
            st.error("Hittar inga Secrets. Kontrollera Streamlit Cloud.")
            return None, None
            
        conf = st.secrets["connections"]["gsheets"].to_dict()
        
        # 1. Extrahera det absolut nödvändiga
        sheet_url = conf.get("spreadsheet")
        
        # 2. Skapa ett rent inloggnings-objekt (endast det biblioteket kräver)
        # Vi tar bort allt som kan orsaka "unexpected keyword argument"
        creds = {
            "type": "service_account",
            "client_email": conf.get("client_email"),
        }
        
        # 3. Fixa Private Key (viktigaste delen)
        raw_key = conf.get("private_key", "")
        clean_content = raw_key.replace("-----BEGIN PRIVATE KEY-----", "") \
                               .replace("-----END PRIVATE KEY-----", "") \
                               .replace("\\n", "\n").replace("\n", "").replace(" ", "").strip()
        
        lines = [clean_content[i:i+64] for i in range(0, len(clean_content), 64)]
        creds["private_key"] = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"
        
        # 4. Skapa anslutningen med enbart de rena inloggningsuppgifterna
        connection = st.connection("gsheets", type=GSheetsConnection, **creds)
        return connection, sheet_url
    except Exception as e:
        st.session_state.error_log = f"Konfigurationsfel: {e}"
        return None, None

# Starta anslutningen
conn, spreadsheet_url = get_robust_connection()

# --- DATAFUNKTIONER ---
def load_data():
    if conn and spreadsheet_url:
        try:
            return conn.read(spreadsheet=spreadsheet_url, ttl="0s")
        except Exception as e:
            st.session_state.error_log = f"Läsfel: {e}"
    return pd.DataFrame(columns=["Modell", "Tillverkare", "Resurstagg", "Status", "Aktuell ägare"])

# Initiera sessionstate
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- SIDOMENY ---
with st.sidebar:
    st.title("🎵 Musikinventering")
    menu = st.radio("MENY", ["🔍 Sök & Inventarie", "➕ Lägg till (Kamera)", "🛒 Lånekorg", "🔄 Återlämning", "⚙️ System"])
    if st.button("🔄 Synka med Google"):
        st.session_state.df = load_data()
        st.rerun()

# --- VYER ---
if menu == "🔍 Sök & Inventarie":
    st.title("Sök & Inventarie")
    df = st.session_state.df
    if not df.empty:
        search = st.text_input("Sök instrument...", placeholder="Modell eller ID")
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        for idx, row in df[mask].iterrows():
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"**{row['Modell']}** ({row.get('Resurstagg', 'N/A')})")
            status = row.get('Status', 'Tillgänglig')
            c2.write(f"Status: {status}")
            if status == 'Tillgänglig' and c3.button("Låna", key=f"l_{idx}"):
                st.session_state.cart.append(row.to_dict())
                st.toast(f"{row['Modell']} tillagd")
    else:
        st.info("Ingen data hittades.")

elif menu == "➕ Lägg till (Kamera)":
    st.title("Registrera ny utrustning")
    with st.form("add_item", clear_on_submit=True):
        m = st.text_input("Modell *")
        t = st.text_input("Tillverkare")
        tag = st.text_input("Resurstagg (ID)")
        st.camera_input("Ta kontrollfoto")
        if st.form_submit_button("Spara till molnet"):
            if m:
                new_row = {"Modell": m, "Tillverkare": t, "Resurstagg": tag if tag else str(random.randint(1000,9999)), "Status": "Tillgänglig", "Aktuell ägare": ""}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                if conn:
                    try:
                        conn.update(spreadsheet=spreadsheet_url, data=st.session_state.df)
                        st.success(f"Sparade {m}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Kunde inte spara: {e}")
            else: st.error("Modellnamn krävs.")

elif menu == "🛒 Lånekorg":
    st.title("Utlåning")
    if st.session_state.cart:
        for item in st.session_state.cart: st.write(f"• **{item['Modell']}** ({item['Resurstagg']})")
        namn = st.text_input("Vem lånar?")
        if st.button("Bekräfta lån") and namn:
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare']] = ['Utlånad', namn]
            if conn:
                conn.update(spreadsheet=spreadsheet_url, data=st.session_state.df)
                st.session_state.cart = []
                st.success("Lånet registrerat!")
                st.rerun()
    else: st.info("Korgen är tom.")

elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        choice = st.selectbox("Välj instrument:", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
        if st.button("Lämna tillbaka"):
            tag = choice.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Aktuell ägare']] = ['Tillgänglig', '']
            if conn:
                conn.update(spreadsheet=spreadsheet_url, data=st.session_state.df)
                st.success("Återlämnad!")
                st.rerun()
    else: st.info("Inga lånade instrument.")

elif menu == "⚙️ System":
    st.title("System & Diagnostik")
    if 'error_log' in st.session_state:
        st.error(st.session_state.error_log)
    else:
        st.success("Anslutningen fungerar!")
    st.write("### Rådata")
    st.dataframe(st.session_state.df)

import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random

# --- GRUNDINSTÄLLNINGAR ---
st.set_page_config(page_title="InstrumentDB", layout="wide")

# --- ROBUST ANSLUTNINGSFUNKTION ---
def get_robust_connection():
    try:
        # 1. Hämta rådata från Secrets
        if "connections" not in st.secrets or "gsheets" not in st.secrets["connections"]:
            st.error("Hittar inga Secrets för 'gsheets'. Kontrollera din konfiguration i Streamlit Cloud.")
            return None
            
        conf = st.secrets["connections"]["gsheets"].to_dict()
        
        # 2. Rensa bort 'type' för att undvika "multiple values"-felet
        # Vi definierar typen direkt i st.connection istället
        if "type" in conf:
            del conf["type"]
        
        # 3. Rensa och formatera om Private Key (Fixar MalformedFraming)
        raw_key = conf.get("private_key", "")
        clean_content = raw_key.replace("-----BEGIN PRIVATE KEY-----", "") \
                               .replace("-----END PRIVATE KEY-----", "") \
                               .replace("\\n", "\n").replace("\n", "").replace(" ", "").strip()
        
        # Dela upp i 64-teckens rader (PEM-standard)
        lines = [clean_content[i:i+64] for i in range(0, len(clean_content), 64)]
        formatted_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"
        
        # Uppdatera konfigurationen med den perfekt formaterade nyckeln
        conf["private_key"] = formatted_key
        
        # 4. Skapa anslutningen med de rensade inställningarna
        return st.connection("gsheets", type=GSheetsConnection, **conf)
    except Exception as e:
        st.session_state.error_log = f"Konfigurationsfel: {e}"
        return None

# Starta anslutningen
conn = get_robust_connection()

# --- DATAFUNKTIONER ---
def load_data():
    if conn:
        try:
            return conn.read(ttl="0s")
        except Exception as e:
            st.session_state.error_log = f"Kunde inte läsa från Google: {e}"
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
    if st.button("🔄 Synka med Google Sheets"):
        st.session_state.df = load_data()
        st.rerun()

# --- VY: SÖK & INVENTARIE ---
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
        st.info("Ingen data hittades. Gå till 'System' för att se felmeddelanden.")

# --- VY: LÄGG TILL ---
elif menu == "➕ Lägg till (Kamera)":
    st.title("Registrera ny utrustning")
    with st.form("add_item", clear_on_submit=True):
        m = st.text_input("Modell *")
        t = st.text_input("Tillverkare")
        tag = st.text_input("Resurstagg (ID)")
        st.camera_input("Ta kontrollfoto")
        
        if st.form_submit_button("Spara till molnet"):
            if m:
                new_row = {
                    "Modell": m, 
                    "Tillverkare": t, 
                    "Resurstagg": tag if tag else str(random.randint(1000,9999)), 
                    "Status": "Tillgänglig",
                    "Aktuell ägare": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                if conn:
                    try:
                        conn.update(data=st.session_state.df)
                        st.success(f"Sparade {m}!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Kunde inte spara till Google: {e}")
            else:
                st.error("Modellnamn krävs.")

# --- VY: LÄNEKORG ---
elif menu == "🛒 Lånekorg":
    st.title("Utlåning")
    if st.session_state.cart:
        for item in st.session_state.cart:
            st.write(f"• **{item['Modell']}** ({item['Resurstagg']})")
        namn = st.text_input("Vem lånar instrumenten?")
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
    df = st.session_state.df
    loaned = df[df['Status'] == 'Utlånad']
    if not loaned.empty:
        choice = st.selectbox("Välj instrument:", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
        if st.button("Lämna tillbaka"):
            tag = choice.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Aktuell ägare']] = ['Tillgänglig', '']
            if conn:
                conn.update(data=st.session_state.df)
                st.success("Instrumentet är nu tillgängligt igen!")
                st.rerun()
    else:
        st.info("Inga lånade instrument just nu.")

# --- VY: SYSTEM ---
elif menu == "⚙️ System":
    st.title("System & Diagnostik")
    if 'error_log' in st.session_state:
        st.error(st.session_state.error_log)
    else:
        st.success("Kopplingen mot Google Sheets fungerar utmärkt!")
    
    st.write("### Rådata i systemet")
    st.dataframe(st.session_state.df)

import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random

# --- GRUNDINSTÄLLNINGAR ---
st.set_page_config(page_title="InstrumentDB", layout="wide")

# --- NY "SKOTTSÄKER" ANSLUTNINGSFUNKTION ---
def get_robust_connection():
    try:
        # 1. Hämta rådata från Secrets
        conf = st.secrets["connections"]["gsheets"].to_dict()
        
        # 2. Rensa Private Key helt från skräptecken
        raw_key = conf.get("private_key", "")
        # Ta bort allt som inte är själva kod-tecknen
        clean_content = raw_key.replace("-----BEGIN PRIVATE KEY-----", "") \
                               .replace("-----END PRIVATE KEY-----", "") \
                               .replace("\\n", "").replace("\n", "").replace(" ", "").strip()
        
        # 3. Återuppbygg nyckeln med exakt rätt PEM-formatering
        # Dela upp i 64-teckens rader
        lines = [clean_content[i:i+64] for i in range(0, len(clean_content), 64)]
        formatted_key = "-----BEGIN PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END PRIVATE KEY-----\n"
        
        # 4. Uppdatera konfigurationen med den lagade nyckeln
        conf["private_key"] = formatted_key
        
        # 5. Skapa anslutningen manuellt
        return st.connection("gsheets", type=GSheetsConnection, **conf)
    except Exception as e:
        st.session_state.error_log = f"Internt konfigurationsfel: {e}"
        return None

conn = get_robust_connection()

# --- DATAFUNKTIONER ---
def load_data():
    if conn:
        try:
            return conn.read(ttl="0s")
        except Exception as e:
            st.session_state.error_log = str(e)
    return pd.DataFrame(columns=["Modell", "Tillverkare", "Resurstagg", "Status", "Aktuell ägare"])

if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- SIDOMENY ---
with st.sidebar:
    st.title("🎵 Musikinventering")
    menu = st.radio("MENY", ["🔍 Sök & Inventarie", "➕ Lägg till (Kamera)", "🛒 Lånekorg", "🔄 Återlämning", "⚙️ System"])
    if st.button("🔄 Uppdatera"):
        st.session_state.df = load_data()
        st.rerun()

# --- VY: SÖK ---
if menu == "🔍 Sök & Inventarie":
    st.title("Sök & Inventarie")
    df = st.session_state.df
    if not df.empty:
        search = st.text_input("Sök...", placeholder="Modell eller ID")
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        for idx, row in df[mask].iterrows():
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"**{row['Modell']}** ({row.get('Resurstagg', 'N/A')})")
            c2.write(f"Status: {row.get('Status', 'Okänd')}")
            if row.get('Status') == 'Tillgänglig' and c3.button("Låna", key=f"l_{idx}"):
                st.session_state.cart.append(row.to_dict())
                st.toast("Tillagd!")
    else:
        st.warning("Ingen data hittades. Se fliken 'System'.")

# --- VY: LÄGG TILL ---
elif menu == "➕ Lägg till (Kamera)":
    st.title("Registrera ny")
    with st.form("add"):
        m = st.text_input("Modell *")
        t = st.text_input("Tillverkare")
        tag = st.text_input("ID")
        st.camera_input("Ta bild")
        if st.form_submit_button("Spara"):
            if m:
                new_row = {"Modell": m, "Tillverkare": t, "Resurstagg": tag if tag else str(random.randint(1000,9999)), "Status": "Tillgänglig"}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                if conn:
                    conn.update(data=st.session_state.df)
                    st.success("Sparat i molnet!")
            else: st.error("Namn saknas")

# --- VY: LÅNEKORG ---
elif menu == "🛒 Lånekorg":
    st.title("Lånekorg")
    if st.session_state.cart:
        for item in st.session_state.cart: st.write(f"• {item['Modell']}")
        namn = st.text_input("Låntagare")
        if st.button("Slutför lån") and namn:
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare']] = ['Utlånad', namn]
            if conn:
                conn.update(data=st.session_state.df)
                st.session_state.cart = []
                st.success("Klart!")
    else: st.info("Korgen är tom.")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        choice = st.selectbox("Välj föremål:", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
        if st.button("Lämna tillbaka"):
            tag = choice.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Aktuell ägare']] = ['Tillgänglig', '']
            if conn:
                conn.update(data=st.session_state.df)
                st.success("Återlämnad!")
    else: st.info("Inga lånade föremål.")

# --- VY: SYSTEM ---
elif menu == "⚙️ System":
    st.title("System & Diagnostik")
    if 'error_log' in st.session_state:
        st.error(f"Detaljerat fel: {st.session_state.error_log}")
    else:
        st.success("Kopplingen är äntligen helt OK!")
    st.write("### Rådata i systemet")
    st.dataframe(st.session_state.df)

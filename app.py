import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import qrcode
from PIL import Image
from io import BytesIO
from datetime import datetime
import random

# --- KONFIGURATION ---
st.set_page_config(page_title="InstrumentDB", layout="wide")

# Hjälpfunktion för att fixa nyckeln innan den skickas till Google
def get_fixed_secrets():
    try:
        # Hämta rådata från secrets
        secrets_dict = st.secrets["connections"]["gsheets"].to_dict()
        raw_key = secrets_dict.get("private_key", "")
        
        # Om nyckeln saknar radbrytningar eller har hamnat på en rad, formatera om den
        if "-----BEGIN PRIVATE KEY-----" in raw_key:
            header = "-----BEGIN PRIVATE KEY-----"
            footer = "-----END PRIVATE KEY-----"
            # Ta ut själva innehållet mellan start och stopp
            content = raw_key.replace(header, "").replace(footer, "").replace("\n", "").strip()
            # Dela upp i 64-teckens rader som PEM-standarden kräver
            lines = [content[i:i+64] for i in range(0, len(content), 64)]
            fixed_key = header + "\n" + "\n".join(lines) + "\n" + footer
            secrets_dict["private_key"] = fixed_key
            
        return secrets_dict
    except Exception as e:
        st.error(f"Kunde inte bearbeta Secrets: {e}")
        return None

# --- ANSLUTNING ---
# Vi skapar anslutningen med den "lagade" konfigurationen
fixed_conf = get_fixed_secrets()
if fixed_conf:
    conn = st.connection("gsheets", type=GSheetsConnection, **fixed_conf)
else:
    st.error("Kunde inte ladda konfigurationen från Secrets.")

def load_data():
    try:
        data = conn.read(ttl="0s")
        if data is None or data.empty:
            return pd.DataFrame(columns=["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"])
        return data
    except Exception as e:
        st.session_state.last_err = str(e)
        return pd.DataFrame(columns=["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"])

def save_data(df):
    try:
        conn.update(data=df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")
        return False

def get_qr_image(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(str(data))
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")

# Initiera session
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- SIDOMENY ---
with st.sidebar:
    st.title("🎵 InstrumentDB")
    menu = st.radio("MENY", ["🔍 Sök & Inventarie", "➕ Lägg till musikutrustning", "🛒 Lånekorg", "🔄 Återlämning", "📝 Hantera & Redigera", "⚙️ System & Export"])
    if st.button("🔄 Synka data"):
        st.session_state.df = load_data()
        st.rerun()

# --- VYER ---
if menu == "🔍 Sök & Inventarie":
    st.title("Sök & Inventarie")
    df = st.session_state.df
    if not df.empty:
        search = st.text_input("Sök...", placeholder="Skriv modell eller ID")
        mask = df.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)
        for idx, row in df[mask].iterrows():
            c1, c2, c3, c4 = st.columns([1, 3, 1, 1])
            c2.write(f"**{row['Modell']}** ({row['Resurstagg']})")
            c3.write(f"Status: {row['Status']}")
            if row['Status'] == 'Tillgänglig' and c4.button("Låna", key=f"btn_{idx}"):
                st.session_state.cart.append(row.to_dict())
                st.toast("Tillagd i korgen")
    else:
        st.info("Ingen data hittades i Google Sheets.")

elif menu == "➕ Lägg till musikutrustning":
    st.title("Registrera Ny")
    with st.form("add_f"):
        modell = st.text_input("Modell *")
        tillv = st.text_input("Tillverkare")
        tagg = st.text_input("Resurstagg (ID)")
        st.write("---")
        cam = st.camera_input("Ta foto")
        if st.form_submit_button("Spara"):
            if modell:
                new_id = tagg if tagg else f"ID-{random.randint(1000,9999)}"
                new_row = {"Modell": modell, "Tillverkare": tillv, "Resurstagg": str(new_id), "Status": "Tillgänglig"}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.success("Sparat!")
                st.rerun()

elif menu == "🛒 Lånekorg":
    st.title("Lånekorg")
    if st.session_state.cart:
        for i, item in enumerate(st.session_state.cart):
            st.write(f"• {item['Modell']}")
        namn = st.text_input("Låntagare")
        if st.button("Slutför lån") and namn:
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare']] = ['Utlånad', namn]
            save_data(st.session_state.df)
            st.session_state.cart = []
            st.rerun()
    else:
        st.write("Korgen är tom.")

elif menu == "🔄 Återlämning":
    st.title("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        obj = st.selectbox("Välj objekt", loaned['Modell'] + " [" + loaned['Resurstagg'] + "]")
        if st.button("Återlämna"):
            tag = obj.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tag, ['Status', 'Aktuell ägare']] = ['Tillgänglig', '']
            save_data(st.session_state.df)
            st.rerun()

elif menu == "📝 Hantera & Redigera":
    st.title("Admin")
    st.write("Här kan du se all rådata.")
    st.dataframe(st.session_state.df)

elif menu == "⚙️ System & Export":
    st.title("System & Diagnostik")
    if "last_err" in st.session_state:
        st.error(f"Senaste fel: {st.session_state.last_err}")
    else:
        st.success("Inga anslutningsfel registrerade.")
    st.write("Använder Service Account: musikinventering@musikinventering.iam.gserviceaccount.com")

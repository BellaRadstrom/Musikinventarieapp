import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import random
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image
import base64

# --- CONFIG ---
st.set_page_config(page_title="Musik-Inventering Pro", layout="wide", page_icon="🎸")

# --- SESSION STATE ---
if 'error_log' not in st.session_state:
    st.session_state.error_log = []
if 'editing_item' not in st.session_state:
    st.session_state.editing_item = None

def add_log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.error_log.append(f"[{timestamp}] {msg}")

# --- HJÄLPFUNKTION: BILD TILL TEXT ---
def process_image_to_base64(image_file):
    try:
        img = Image.open(image_file)
        img.thumbnail((300, 300))
        buffered = BytesIO()
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buffered, format="JPEG", quality=70)
        return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"
    except Exception as e:
        add_log(f"BILD-FEL: {str(e)}")
        return ""

# --- ANSLUTNING ---
@st.cache_resource
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

conn = get_connection()

def load_data():
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        return data.fillna("")
    except Exception as e:
        add_log(f"Läsfel: {str(e)}")
        return pd.DataFrame(columns=["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"])

def save_data(df):
    try:
        conn.update(worksheet="Sheet1", data=df.fillna("").astype(str))
        st.cache_data.clear()
        return True
    except Exception as e:
        add_log(f"Skrivfel: {str(e)}")
        return False

# Initiera Data
if 'df' not in st.session_state:
    st.session_state.df = load_data()
if 'cart' not in st.session_state:
    st.session_state.cart = []

# --- SIDOMENY ---
st.sidebar.title("🎸 InstrumentDB")
menu = st.sidebar.selectbox("Navigering", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "⚙️ Admin"])

# --- VY: SÖK & LÅNA (Inkluderar Redigering) ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    # --- REDIGERINGSLÄGE (Visas bara om man klickat på Edit) ---
    if st.session_state.editing_item is not None:
        idx = st.session_state.editing_item
        item = st.session_state.df.iloc[idx]
        st.info(f"Redigerar: {item['Modell']} ({item['Resurstagg']})")
        
        with st.form("edit_form"):
            new_modell = st.text_input("Modell", value=item['Modell'])
            new_status = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service"], index=["Tillgänglig", "Utlånad", "Service"].index(item['Status']) if item['Status'] in ["Tillgänglig", "Utlånad", "Service"] else 0)
            new_owner = st.text_input("Aktuell ägare", value=item['Aktuell ägare'])
            
            col1, col2 = st.columns(2)
            if col1.form_submit_button("Spara ändringar"):
                st.session_state.df.at[idx, 'Modell'] = new_modell
                st.session_state.df.at[idx, 'Status'] = new_status
                st.session_state.df.at[idx, 'Aktuell ägare'] = new_owner
                if save_data(st.session_state.df):
                    st.success("Ändringar sparade!")
                    st.session_state.editing_item = None
                    st.rerun()
            if col2.form_submit_button("Avbryt"):
                st.session_state.editing_item = None
                st.rerun()
        st.divider()

    # --- SÖKFUNKTION ---
    search_query = st.text_input("Sök i inventariet...", placeholder="Sök modell, ID...")
    mask = st.session_state.df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
    results = st.session_state.df[mask]

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 3, 1.2])
            with c1:
                if row['Enhetsfoto']: st.image(row['Enhetsfoto'], width=100)
                else: st.write("📷")
            with c2:
                st.markdown(f"**{row['Modell']}**")
                st.caption(f"ID: {row['Resurstagg']} | Status: {row['Status']}")
            with c3:
                # Knappar för handlingar
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒 Låna", key=f"lån_{idx}"):
                        if row['Resurstagg'] not in [i['Resurstagg'] for i in st.session_state.cart]:
                            st.session_state.cart.append(row.to_dict())
                            st.toast(f"{row['Modell']} tillagd!")
                
                if st.button("✏️ Redigera", key=f"edit_btn_{idx}"):
                    st.session_state.editing_item = idx
                    st.rerun()

    # Utcheckning
    if st.session_state.cart:
        st.sidebar.divider()
        st.sidebar.subheader("🛒 Utcheckning")
        borrower = st.sidebar.text_input("Låntagare")
        if st.sidebar.button("Bekräfta lån", type="primary"):
            if borrower:
                for item in st.session_state.cart:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 
                                            ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, datetime.now().strftime("%Y-%m-%d")]
                if save_data(st.session_state.df):
                    st.balloons()
                    st.sidebar.success("Lån registrerat!")
                    st.session_state.cart = []
                    st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.header("Registrera nytt instrument")
    with st.form("new_reg", clear_on_submit=True):
        col1, col2 = st.columns(2)
        m = col1.text_input("Modell *")
        s = col2.text_input("Serienummer *")
        t = col1.text_input("Tillverkare")
        tag = col2.text_input("Resurstagg (ID)")
        img = st.camera_input("Foto")
        
        if st.form_submit_button("Skapa Produkt"):
            if m and s:
                res_id = tag if tag else str(random.randint(1000, 9999))
                img_b64 = process_image_to_base64(img) if img else ""
                
                new_data = {"Enhetsfoto": img_b64, "Modell": m, "Serienummer": s, "Tillverkare": t, "Resurstagg": res_id, "Status": "Tillgänglig"}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
                
                if save_data(st.session_state.df):
                    st.balloons()
                    st.success(f"Lyckades! {m} är nu tillagd i systemet.")
            else:
                st.error("Fyll i Modell och Serienummer.")

# --- VY: ADMIN & LOGG ---
elif menu == "⚙️ Admin":
    st.header("Systeminställningar")
    if st.button("Rensa allt cache-minne"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()
    st.dataframe(st.session_state.df)

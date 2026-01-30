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
if 'debug_log' not in st.session_state: st.session_state.debug_log = []
if 'editing_item' not in st.session_state: st.session_state.editing_item = None
if 'cart' not in st.session_state: st.session_state.cart = []
if 'last_checkout' not in st.session_state: st.session_state.last_checkout = None
if 'temp_sn' not in st.session_state: st.session_state.temp_sn = ""

def add_log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.debug_log.append(f"[{timestamp}] {msg}")

# --- HJÄLPFUNKTIONER ---
def clean_id(val):
    if pd.isna(val) or val == "": return ""
    s = str(val).strip()
    if s.endswith(".0"): s = s[:-2]
    return s

def process_image_to_base64(image_file):
    try:
        img = Image.open(image_file)
        img.thumbnail((300, 300)) 
        buffered = BytesIO()
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.save(buffered, format="JPEG", quality=70)
        return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"
    except Exception as e:
        add_log(f"Bildfel: {e}")
        return ""

def generate_qr(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(str(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- ANSLUTNING ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        if "Resurstagg" in data.columns:
            data["Resurstagg"] = data["Resurstagg"].apply(clean_id)
        return data.fillna("")
    except Exception as e:
        add_log(f"Laddningsfel: {e}")
        return pd.DataFrame(columns=["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"])

def save_data(df):
    try:
        conn.update(worksheet="Sheet1", data=df.fillna("").astype(str))
        st.cache_data.clear()
        return True
    except Exception as e:
        add_log(f"Sparfel: {e}")
        return False

st.session_state.df = load_data()

# --- SIDEBAR ---
st.sidebar.title("🎸 Musik-IT")
menu = st.sidebar.selectbox("Navigering", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "⚙️ Admin & Inventering"])

if st.session_state.cart:
    st.sidebar.divider()
    st.sidebar.subheader("🛒 Varukorg")
    for item in st.session_state.cart:
        st.sidebar.caption(f"• {item['Modell']} ({item['Resurstagg']})")
    if st.sidebar.button("Töm korg"):
        st.session_state.cart = []
        st.rerun()
    borrower_name = st.sidebar.text_input("Vem lånar? *")
    if borrower_name and st.sidebar.button("Bekräfta utlån ✅", type="primary"):
        today = datetime.now().strftime("%Y-%m-%d")
        for item in st.session_state.cart:
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower_name, today]
        if save_data(st.session_state.df):
            st.session_state.cart = []
            st.rerun()

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    q_params = st.query_params
    scanned_val = q_params.get("qr", "")
    
    with st.expander("📷 Öppna QR-skanner", expanded=True):
        # Optimerad för Android (Pixel 8 Pro)
        qr_component = f"""
        <div id="reader" style="width: 100%; max-width: 450px; margin: auto; border: 2px solid #4CAF50; border-radius: 8px;"></div>
        <script src="https://unpkg.com/html5-qrcode"></script>
        <script>
            function onScanSuccess(decodedText, decodedResult) {{
                const url = new URL(window.top.location.href);
                url.searchParams.set('qr', decodedText);
                window.top.location.href = url.href;
            }}

            // Specifika inställningar för Android-kameror
            const config = {{ 
                fps: 20, 
                qrbox: {{ width: 250, height: 250 }},
                aspectRatio: 1.0,
                videoConstraints: {{
                    facingMode: "environment",
                    width: {{ min: 640, ideal: 1280, max: 1920 }},
                    height: {{ min: 480, ideal: 720, max: 1080 }},
                    frameRate: {{ ideal: 30, max: 60 }}
                }}
            }};

            const html5QrCode = new Html5Qrcode("reader");
            html5QrCode.start({{ facingMode: "environment" }}, config, onScanSuccess)
                .catch(err => console.error("Kamerafel:", err));
        </script>
        """
        st.components.v1.html(qr_component, height=500)
    
    query = st.text_input("Sök produkt eller skanna QR", value=scanned_val)
    
    if scanned_val and st.button("Rensa sökning"):
        st.query_params.clear()
        st.rerun()

    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)] if query else st.session_state.df

    # Redigerings-logik (behållen)
    if st.session_state.editing_item is not None:
        idx = st.session_state.editing_item
        item = st.session_state.df.iloc[idx]
        with st.form("edit_form"):
            u_mod = st.text_input("Modell", value=item['Modell'])
            u_sn = st.text_input("ID", value=item['Resurstagg'])
            if st.form_submit_button("Spara"):
                st.session_state.df.at[idx, 'Modell'] = u_mod
                st.session_state.df.at[idx, 'Resurstagg'] = clean_id(u_sn)
                save_data(st.session_state.df)
                st.session_state.editing_item = None
                st.rerun()
        if st.button("Avbryt"):
            st.session_state.editing_item = None
            st.rerun()

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 3, 1])
            with c1:
                if str(row['Enhetsfoto']).startswith("data"): st.image(row['Enhetsfoto'], width=80)
            with c2:
                st.write(f"**{row['Modell']}**")
                st.caption(f"ID: {row['Resurstagg']} | Status: {row['Status']}")
            with c3:
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒", key=f"l_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.rerun()
                if st.button("✏️", key=f"e_{idx}"):
                    st.session_state.editing_item = idx
                    st.rerun()

# --- ÖVRIGA VYER ---
elif menu == "➕ Registrera Nytt":
    st.header("Ny produkt")
    with st.form("new_item"):
        m = st.text_input("Modell")
        s = st.text_input("ID")
        img = st.camera_input("Foto")
        if st.form_submit_button("Spara"):
            new_row = {"Modell": m, "Resurstagg": clean_id(s), "Status": "Tillgänglig", "Enhetsfoto": process_image_to_base64(img) if img else ""}
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
            save_data(st.session_state.df)
            st.success("Klar!")

elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    active_b = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']['Aktuell ägare'].unique()
    if len(active_b) > 0:
        target = st.selectbox("Välj person", active_b)
        if st.button("Återlämna allt från denna person"):
            st.session_state.df.loc[st.session_state.df['Aktuell ägare'] == target, ['Status', 'Aktuell ägare']] = ['Tillgänglig', '']
            save_data(st.session_state.df)
            st.rerun()

elif menu == "⚙️ Admin & Inventering":
    st.header("Lagerlista")
    st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"]), use_container_width=True)

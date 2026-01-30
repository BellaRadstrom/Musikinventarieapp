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

def get_label_html(items):
    html = "<div style='display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-start;'>"
    for item in items:
        qr_b64 = base64.b64encode(generate_qr(item['Resurstagg'])).decode()
        html += f"""
        <div style="width: 3.8cm; height: 2.8cm; border: 1px solid #000; padding: 5px; text-align: center; font-family: Arial, sans-serif; background-color: white; color: black; margin-bottom: 5px;">
            <img src="data:image/png;base64,{qr_b64}" style="width: 1.6cm;"><br>
            <div style="font-size: 11px; font-weight: bold; margin-top: 2px;">{str(item['Modell'])[:22]}</div>
            <div style="font-size: 9px;">ID/SN: {item['Resurstagg']}</div>
        </div>
        """
    html += "</div><div style='text-align:center; margin-top:10px;'><button onclick='window.print()'>Skriv ut etiketter</button></div>"
    return html

def get_packing_list_html(borrower, items):
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    list_items = "".join([f"<li style='padding:5px 0;'><b>{item['Modell']}</b><br><small>SN/ID: {item['Resurstagg']}</small></li>" for item in items])
    return f"""
    <div style="font-family: Arial, sans-serif; padding: 30px; border: 2px solid #333; background: white; color: black; max-width: 600px; margin: auto;">
        <h1>🎸 Utlåningskvitto</h1>
        <p><b>Låntagare:</b> {borrower}</p>
        <p><b>Datum:</b> {date_str}</p>
        <hr>
        <h3>Utrustning:</h3>
        <ul>{list_items}</ul>
        <button onclick="window.print()">🖨️ Skriv ut</button>
    </div>
    """

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
        st.session_state.last_checkout = {"borrower": borrower_name, "items": list(st.session_state.cart)}
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
    
    with st.expander("📷 Starta QR-skanning", expanded=True):
        # OPTIMERAD SKANNER FÖR MOBIL
        qr_component = f"""
        <div id="reader" style="width: 100%; max-width: 400px; margin: auto; border-radius: 10px; overflow: hidden;"></div>
        <script src="https://unpkg.com/html5-qrcode"></script>
        <script>
            function onScanSuccess(decodedText, decodedResult) {{
                const url = new URL(window.top.location.href);
                url.searchParams.set('qr', decodedText);
                window.top.location.href = url.href;
                html5QrCode.stop(); // Stoppa kameran direkt vid träff
            }}

            const html5QrCode = new Html5Qrcode("reader");
            const config = {{ 
                fps: 15, 
                qrbox: {{ width: 250, height: 250 }},
                aspectRatio: 1.0 
            }};

            // Tvinga användning av bakre kamera (environment)
            html5QrCode.start(
                {{ facingMode: "environment" }}, 
                config, 
                onScanSuccess
            ).catch((err) => {{
                console.error("Kamerafel:", err);
            }});
        </script>
        """
        st.components.v1.html(qr_component, height=450)
        st.caption("Rikta kameran mot QR-koden. Sidan laddas om vid träff.")

    query = st.text_input("Sök eller skanna", value=scanned_val, placeholder="Skriv här...")
    
    if scanned_val and st.button("Rensa sökning"):
        st.query_params.clear()
        st.rerun()

    if query:
        results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)]
    else:
        results = st.session_state.df

    # Redigeringsläge
    if st.session_state.editing_item is not None:
        idx = st.session_state.editing_item
        item = st.session_state.df.iloc[idx]
        with st.container(border=True):
            st.subheader(f"✏️ Redigerar: {item['Modell']}")
            with st.form("edit_form"):
                u_mod = st.text_input("Modell", value=item['Modell'])
                u_sn = st.text_input("ID/SN", value=item['Resurstagg'])
                u_stat = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service"], index=0)
                if st.form_submit_button("Spara"):
                    st.session_state.df.at[idx, 'Modell'] = u_mod
                    st.session_state.df.at[idx, 'Resurstagg'] = clean_id(u_sn)
                    st.session_state.df.at[idx, 'Status'] = u_stat
                    if save_data(st.session_state.df):
                        st.session_state.editing_item = None
                        st.rerun()
            if st.button("Avbryt"):
                st.session_state.editing_item = None
                st.rerun()

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 3, 1])
            with c1:
                if str(row['Enhetsfoto']).startswith("data:image"): st.image(row['Enhetsfoto'], width=80)
            with c2:
                st.markdown(f"**{row['Modell']}**")
                st.caption(f"ID: {row['Resurstagg']} | Status: {row['Status']}")
            with c3:
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒", key=f"l_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.rerun()
                if st.button("✏️", key=f"e_{idx}"):
                    st.session_state.editing_item = idx
                    st.rerun()

# --- ÖVRIGA VYER (Behållna enligt instruktion) ---
elif menu == "➕ Registrera Nytt":
    st.header("Ny produkt")
    with st.form("new_reg"):
        m_in = st.text_input("Modell *")
        sn_in = st.text_input("Serienummer / ID *", value=st.session_state.temp_sn)
        foto_in = st.camera_input("Produktfoto")
        if st.form_submit_button("Spara"):
            if m_in and sn_in:
                new_row = {
                    "Enhetsfoto": process_image_to_base64(foto_in) if foto_in else "",
                    "Modell": m_in, "Resurstagg": clean_id(sn_in), "Status": "Tillgänglig"
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.success("Sparad!")

elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    active_b = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']['Aktuell ägare'].unique()
    if len(active_b) > 0:
        target = st.selectbox("Välj person:", list(active_b))
        if st.button("Återlämna allt"):
            st.session_state.df.loc[st.session_state.df['Aktuell ägare'] == target, ['Status', 'Aktuell ägare']] = ['Tillgänglig', '']
            save_data(st.session_state.df)
            st.rerun()

elif menu == "⚙️ Admin & Inventering":
    st.header("Admin")
    st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"]), use_container_width=True)

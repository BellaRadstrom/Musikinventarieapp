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
st.set_page_config(page_title="Musik-IT Birka", layout="wide", page_icon="🎸")

# --- SESSION STATE ---
if 'debug_log' not in st.session_state: st.session_state.debug_log = []
if 'editing_item' not in st.session_state: st.session_state.editing_item = None
if 'cart' not in st.session_state: st.session_state.cart = []
if 'last_checkout' not in st.session_state: st.session_state.last_checkout = None
if 'authenticated' not in st.session_state: st.session_state.authenticated = False

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
    except Exception:
        return ""

def get_packing_list_html(borrower, items):
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    list_items = "".join([f"<li>{item['Modell']} ({item['Resurstagg']})</li>" for item in items])
    return f"""
    <div style="font-family: sans-serif; padding: 20px; border: 1px solid #ccc; color: black; background: white;">
        <h2>Utlåningskvitto</h2>
        <p><b>Låntagare:</b> {borrower}</p>
        <p><b>Datum:</b> {date_str}</p>
        <ul>{list_items}</ul>
        <button onclick="window.print()">Skriv ut packlista</button>
    </div>
    """

# --- ANSLUTNING & DATALADDNING ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        # Säkerställ att alla nödvändiga kolumner finns
        required_cols = ["Enhetsfoto", "Modell", "Resurstagg", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad"]
        for col in required_cols:
            if col not in data.columns:
                data[col] = ""
        
        if "Resurstagg" in data.columns:
            data["Resurstagg"] = data["Resurstagg"].apply(clean_id)
        return data.fillna("")
    except Exception:
        return pd.DataFrame(columns=["Enhetsfoto", "Modell", "Resurstagg", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad"])

def save_data(df):
    try:
        conn.update(worksheet="Sheet1", data=df.fillna("").astype(str))
        st.cache_data.clear()
        return True
    except:
        return False

st.session_state.df = load_data()

# --- LOGIN ---
def check_password():
    if st.session_state.authenticated:
        return True
    pwd = st.sidebar.text_input("Lösenord (Birka)", type="password")
    if pwd == "Birka":
        st.session_state.authenticated = True
        st.rerun()
    return False

# --- SIDEBAR ---
st.sidebar.title("🎸 Musik-IT Birka")
menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Låna", "🔄 Återlämning", "➕ Registrera Nytt", "⚙️ Admin"])

if st.session_state.cart:
    st.sidebar.subheader("🛒 Varukorg")
    borrower = st.sidebar.text_input("Namn på låntagare")
    if st.sidebar.button("Slutför utlån") and borrower:
        today = datetime.now().strftime("%Y-%m-%d")
        st.session_state.last_checkout = {"borrower": borrower, "items": list(st.session_state.cart)}
        for item in st.session_state.cart:
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, today]
        save_data(st.session_state.df)
        st.session_state.cart = []
        st.rerun()

if st.session_state.last_checkout:
    with st.sidebar.expander("📄 Senaste packlista", expanded=True):
        st.components.v1.html(get_packing_list_html(st.session_state.last_checkout['borrower'], st.session_state.last_checkout['items']), height=250)

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    scanned_qr = st.query_params.get("qr", "")
    
    with st.expander("📷 Starta QR-skanner", expanded=not bool(scanned_qr)):
        # Förbättrad skanner-motor för Android/Pixel
        qr_js = """
        <div id="reader" style="width: 100%;"></div>
        <script src="https://unpkg.com/html5-qrcode"></script>
        <script>
            function onScanSuccess(decodedText) {
                const url = new URL(window.top.location.href);
                url.searchParams.set('qr', decodedText);
                window.top.location.href = url.href;
            }
            let html5QrCode = new Html5Qrcode("reader");
            html5QrCode.start(
                { facingMode: "environment" }, 
                { fps: 15, qrbox: {width: 250, height: 250} },
                onScanSuccess
            ).catch(err => console.log(err));
        </script>
        """
        st.components.v1.html(qr_js, height=400)

    query = st.text_input("Sök i registret", value=scanned_qr)
    if scanned_qr and st.button("Rensa skanning"):
        st.query_params.clear()
        st.rerun()

    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)] if query else st.session_state.df

    if st.session_state.editing_item is not None:
        if check_password():
            idx = st.session_state.editing_item
            item = st.session_state.df.iloc[idx]
            with st.form("edit"):
                u_mod = st.text_input("Modell", value=item['Modell'])
                u_id = st.text_input("ID", value=item['Resurstagg'])
                if st.form_submit_button("Spara"):
                    st.session_state.df.at[idx, 'Modell'] = u_mod
                    st.session_state.df.at[idx, 'Resurstagg'] = clean_id(u_id)
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
                st.write(f"**{row['Modell']}** - ID: {row['Resurstagg']}")
                st.caption(f"Status: {row['Status']} | Innehavare: {row.get('Aktuell ägare', '-')}")
            with c3:
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒", key=f"add_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.rerun()
                if st.button("✏️", key=f"edit_{idx}"):
                    st.session_state.editing_item = idx
                    st.rerun()

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    borrowers = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']['Aktuell ägare'].unique()
    if len(borrowers) > 0:
        target = st.selectbox("Välj låntagare", borrowers)
        if st.button("Registrera återlämning"):
            st.session_state.df.loc[st.session_state.df['Aktuell ägare'] == target, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
            save_data(st.session_state.df)
            st.rerun()
    else: st.info("Inga utlånade prylar.")

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    if check_password():
        st.header("Lägg till utrustning")
        with st.form("new"):
            m = st.text_input("Modell")
            i = st.text_input("Resurstagg/ID")
            f = st.camera_input("Foto")
            if st.form_submit_button("Spara"):
                new_row = {"Modell": m, "Resurstagg": clean_id(i), "Status": "Tillgänglig", "Enhetsfoto": process_image_to_base64(f) if f else "", "Senast inventerad": ""}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.success("Tillagd!")

# --- VY: ADMIN & INVENTERING ---
elif menu == "⚙️ Admin":
    if check_password():
        st.header("Administration")
        tab1, tab2 = st.tabs(["📊 Lagerstatus", "📋 Inventering"])
        
        with tab1:
            st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"]), use_container_width=True)
            if st.button("Spara till Sheets"):
                save_data(st.session_state.df)

        with tab2:
            st.subheader("Inventering")
            inv_id = st.text_input("Skanna/Skriv ID")
            if inv_id:
                cid = clean_id(inv_id)
                if cid in st.session_state.df['Resurstagg'].values:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == cid, 'Senast inventerad'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    save_data(st.session_state.df)
                    st.success(f"Inventerat: {cid}")
            
            # Säkrad visning
            disp_cols = ['Modell', 'Resurstagg', 'Senast inventerad']
            st.write(st.session_state.df[disp_cols])

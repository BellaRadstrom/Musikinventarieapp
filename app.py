import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image
import base64

# --- CONFIG ---
st.set_page_config(page_title="Musik-IT Birka", layout="wide", page_icon="🎸")

# --- SESSION STATE ---
if 'df' not in st.session_state: st.session_state.df = None
if 'cart' not in st.session_state: st.session_state.cart = []
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'editing_idx' not in st.session_state: st.session_state.editing_idx = None
if 'debug_logs' not in st.session_state: st.session_state.debug_logs = []

# --- HJÄLPFUNKTIONER ---
def add_log(msg):
    now = datetime.now().strftime("%H:%M:%S")
    st.session_state.debug_logs.append(f"[{now}] {msg}")

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
        add_log(f"Fotofel: {str(e)}")
        return ""

def generate_qr_base64(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(str(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def get_label_html(items):
    html = "<div style='display: flex; flex-wrap: wrap; gap: 10px;'>"
    for item in items:
        qr_b64 = generate_qr_base64(item['Resurstagg'])
        html += f"""
        <div style="width: 3.5cm; height: 2.5cm; border: 1px solid #000; padding: 5px; text-align: center; background: white; color: black;">
            <img src="data:image/png;base64,{qr_b64}" style="width: 1.4cm;"><br>
            <b style="font-size: 10px;">{str(item['Modell'])[:20]}</b><br>
            <span style="font-size: 8px;">ID: {item['Resurstagg']}</span>
        </div>"""
    html += "</div><br><button onclick='window.print()'>Skriv ut etiketter</button>"
    return html

# --- DATALADDNING ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad"]
        for col in cols:
            if col not in data.columns: data[col] = ""
        data["Resurstagg"] = data["Resurstagg"].apply(clean_id)
        st.session_state.df = data.fillna("")
        add_log("Data laddad.")
    except Exception as e:
        add_log(f"Laddningsfel: {str(e)}")

def save_data(df):
    try:
        conn.update(worksheet="Sheet1", data=df.fillna("").astype(str))
        st.session_state.df = df
        add_log("Data sparad.")
    except Exception as e:
        add_log(f"Spara-fel: {str(e)}")

if st.session_state.df is None:
    load_data()

# --- SIDEBAR & LOGIN ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Lösenord", type="password")
st.session_state.authenticated = (pwd == "Birka")

# VARUKORG I SIDOMENYN
if st.session_state.cart:
    st.sidebar.subheader("🛒 Varukorg")
    for item in st.session_state.cart:
        st.sidebar.caption(f"• {item['Modell']}")
    
    borrower = st.sidebar.text_input("Vem lånar?")
    if st.sidebar.button("Slutför Utlån", type="primary"):
        if borrower:
            today = datetime.now().strftime("%Y-%m-%d")
            for c_item in st.session_state.cart:
                idx = st.session_state.df[st.session_state.df['Resurstagg'] == c_item['Resurstagg']].index
                st.session_state.df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, today]
            save_data(st.session_state.df)
            st.session_state.cart = []
            st.sidebar.success("Utlånat!")
            st.rerun()
        else: st.sidebar.error("Ange namn!")
    if st.sidebar.button("Rensa vagn"):
        st.session_state.cart = []
        st.rerun()

menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Låna", "🔄 Återlämning", "➕ Registrera Nytt", "⚙️ Admin"])

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    with st.expander("📷 Kamera / QR-skanner", expanded=True):
        qr_js = """
        <div id="reader" style="width: 100%; max-width: 400px; margin: auto; border: 2px solid #ccc; border-radius: 10px; overflow: hidden;"></div>
        <p id="msg" style="text-align: center; font-weight: bold; margin-top: 10px;">Siktar...</p>
        <script src="https://unpkg.com/html5-qrcode"></script>
        <script>
            function onScan(txt) {
                document.getElementById('msg').innerText = "HITTAD: " + txt;
                localStorage.setItem('scanned_qr', txt);
                if(navigator.vibrate) navigator.vibrate(50);
            }
            const scanner = new Html5Qrcode("reader");
            scanner.start({ facingMode: "environment" }, { fps: 10, qrbox: 250 }, onScan);
        </script>
        """
        st.components.v1.html(qr_js, height=430)

    if st.button("📥 HÄMTA SKANNAD KOD TILL SÖKRUTAN", use_container_width=True, type="primary"):
        js_bridge = """
        <script>
            const code = localStorage.getItem('scanned_qr');
            if(code) {
                const url = new URL(window.parent.location.href);
                url.searchParams.set('qr', code);
                window.parent.location.href = url.href;
            } else { alert("Ingen kod hittades!"); }
        </script>
        """
        st.components.v1.html(js_bridge, height=0)

    # SÖKFÄLT
    scanned_val = st.query_params.get("qr", "")
    query = st.text_input("Sök produkt eller ID", value=scanned_val)
    
    if scanned_val and st.button("Rensa sökning"):
        st.query_params.clear()
        st.rerun()

    # RESULTATLISTA
    if st.session_state.df is not None:
        results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)] if query else st.session_state.df

        for idx, row in results.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
                with c1:
                    if str(row['Enhetsfoto']).startswith("data"): st.image(row['Enhetsfoto'], width=80)
                    else: st.write("📷")
                with c2:
                    st.markdown(f"**{row['Modell']}**")
                    st.caption(f"ID: {row['Resurstagg']} | {row['Status']}")
                    if row['Status'] == 'Utlånad': st.warning(f"Lånad av: {row['Aktuell ägare']}")
                with c3:
                    # Visa QR-koden för produkten
                    qr_img = generate_qr_base64(row['Resurstagg'])
                    st.image(f"data:image/png;base64,{qr_img}", width=70, caption="QR")
                with c4:
                    if row['Status'] == 'Tillgänglig':
                        if st.button("🛒 Låna", key=f"add_{idx}"):
                            st.session_state.cart.append(row.to_dict())
                            st.rerun()
                    
                    if st.session_state.authenticated:
                        if st.button("✏️ Ändra", key=f"edit_{idx}"):
                            st.session_state.editing_idx = idx
                            st.rerun()

    # EDIT-MODAL (Visas om man tryckt på Ändra)
    if st.session_state.editing_idx is not None:
        idx = st.session_state.editing_idx
        row = st.session_state.df.loc[idx]
        with st.form("edit_form"):
            st.subheader(f"Editera: {row['Modell']}")
            new_modell = st.text_input("Modell", value=row['Modell'])
            new_tagg = st.text_input("Resurstagg", value=row['Resurstagg'])
            new_status = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service", "Trasig"], index=["Tillgänglig", "Utlånad", "Service", "Trasig"].index(row['Status']) if row['Status'] in ["Tillgänglig", "Utlånad", "Service", "Trasig"] else 0)
            
            if st.form_submit_button("Spara ändringar"):
                st.session_state.df.at[idx, 'Modell'] = new_modell
                st.session_state.df.at[idx, 'Resurstagg'] = clean_id(new_tagg)
                st.session_state.df.at[idx, 'Status'] = new_status
                save_data(st.session_state.df)
                st.session_state.editing_idx = None
                st.rerun()
            if st.form_submit_button("Avbryt"):
                st.session_state.editing_idx = None
                st.rerun()

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    borrowed = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if borrowed.empty: st.info("Inga utlånade saker.")
    else:
        for idx, row in borrowed.iterrows():
            with st.container(border=True):
                st.write(f"**{row['Modell']}** - Lånad av {row['Aktuell ägare']}")
                if st.button("Registrera återlämning", key=f"ret_{idx}"):
                    st.session_state.df.at[idx, 'Status'] = 'Tillgänglig'
                    st.session_state.df.at[idx, 'Aktuell ägare'] = ''
                    st.session_state.df.at[idx, 'Senast inventerad'] = datetime.now().strftime("%Y-%m-%d")
                    save_data(st.session_state.df)
                    st.rerun()

# --- VY: REGISTRERA ---
elif menu == "➕ Registrera Nytt":
    if not st.session_state.authenticated: st.warning("Logga in.")
    else:
        with st.form("new"):
            m = st.text_input("Modell *")
            i = st.text_input("ID/Resurstagg *")
            f = st.camera_input("Foto")
            if st.form_submit_button("Spara"):
                new_row = {"Modell": m, "Resurstagg": clean_id(i), "Status": "Tillgänglig", "Enhetsfoto": process_image_to_base64(f) if f else ""}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.success("Sparad!")

# --- VY: ADMIN ---
elif menu == "⚙️ Admin":
    if not st.session_state.authenticated: st.warning("Logga in.")
    else:
        t1, t2, t3 = st.tabs(["📊 Lager", "🏷️ Bulk QR", "📋 Logg"])
        with t1: st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"]))
        with t2:
            sel = st.multiselect("Välj produkter:", st.session_state.df['Modell'].tolist())
            if sel:
                to_p = st.session_state.df[st.session_state.df['Modell'].isin(sel)].to_dict('records')
                st.components.v1.html(get_label_html(to_p), height=500, scrolling=True)
        with t3:
            if st.button("Uppdatera från GSheets"): load_data(); st.rerun()
            for log in st.session_state.debug_logs: st.text(log)

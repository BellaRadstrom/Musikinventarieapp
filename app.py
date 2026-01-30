import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image
import base64
import time
import random

# --- 1. KONFIGURATION ---
st.set_page_config(page_title="Musik-IT Birka v5", layout="wide", page_icon="🎸")

# --- 2. SESSION STATE ---
if 'df' not in st.session_state: st.session_state.df = None
if 'cart' not in st.session_state: st.session_state.cart = []
if 'last_loan' not in st.session_state: st.session_state.last_loan = None
if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None

# --- 3. HJÄLPFUNKTIONER ---
def generate_serial():
    return f"{datetime.now().strftime('%y%m%d')}-{random.randint(100, 999)}"

def img_to_b64(image_file):
    try:
        img = Image.open(image_file)
        img.thumbnail((400, 400))
        buf = BytesIO()
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=80)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except: return ""

def generate_qr_b64(data):
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(str(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# --- 4. DATAHANTERING ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad"]
        for c in cols:
            if c not in data.columns: data[c] = ""
        st.session_state.df = data.fillna("")
    except Exception as e:
        st.error(f"Kunde inte ladda data: {e}")

if st.session_state.df is None: load_data()

def save_data():
    conn.update(worksheet="Sheet1", data=st.session_state.df.astype(str))
    st.toast("Data sparad!")

# --- 5. ADMIN LOGIN ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Admin lösenord", type="password")
is_admin = (pwd == "Birka")

if is_admin:
    st.sidebar.success("🔓 Admin-läge aktivt")
else:
    st.sidebar.info("👤 Användar-läge")

# --- 6. VARUKORG & UTskrift AV LÅNELISTA ---
if st.session_state.cart:
    with st.sidebar.expander("🛒 VARUKORG", expanded=True):
        for i, item in enumerate(st.session_state.cart):
            st.write(f"{i+1}. {item['Modell']}")
        
        borrower = st.text_input("Namn på låntagare *")
        if st.button("BEKRÄFTA LÅN", type="primary", use_container_width=True):
            if borrower:
                today = datetime.now().strftime("%Y-%m-%d")
                for itm in st.session_state.cart:
                    idx = st.session_state.df[st.session_state.df['Resurstagg'] == itm['Resurstagg']].index
                    st.session_state.df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, today]
                
                st.session_state.last_loan = {"name": borrower, "date": today, "items": st.session_state.cart.copy()}
                st.session_state.cart = []
                save_data()
                st.rerun()
            else: st.error("Ange namn!")

# --- 7. HUVUDMENY ---
menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Låna", "➕ Registrera Ny", "🔄 Återlämning", "⚙️ Admin"])

# --- 8. VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    # 🖨️ SKRIV UT LÅNELISTA (FÖLJESEDEL)
    if st.session_state.last_loan:
        st.markdown("### 📄 Lånebekräftelse skapad")
        items_html = "".join([f"<li>{i['Modell']} ({i['Resurstagg']})</li>" for i in st.session_state.last_loan['items']])
        receipt_content = f"""
            <div id='printMe' style='padding: 20px; border: 1px solid #ccc; font-family: sans-serif;'>
                <h2>Låneföljesedel - Musik-IT Birka</h2>
                <p><b>Låntagare:</b> {st.session_state.last_loan['name']}</p>
                <p><b>Datum:</b> {st.session_state.last_loan['date']}</p>
                <ul>{items_html}</ul>
            </div>
            <br>
            <button onclick="window.print()" style="padding:10px 20px; background:#4CAF50; color:white; border:none; border-radius:5px; cursor:pointer;">
                🖨️ SKRIV UT LÅNELISTA
            </button>
        """
        st.components.v1.html(receipt_content, height=350)
        if st.button("Klar / Stäng"): 
            st.session_state.last_loan = None
            st.rerun()

    # 📷 KAMERA / SKANNER
    with st.expander("📷 Starta QR-Skanner", expanded=False):
        st.components.v1.html("""
            <div id="reader" style="width:100%;"></div>
            <script src="https://unpkg.com/html5-qrcode"></script>
            <script>
                function onScanSuccess(decodedText) {
                    localStorage.setItem('scanned_id', decodedText);
                    document.getElementById('reader').style.border = "5px solid green";
                    alert("Kod hittad: " + decodedText + ". Tryck på knappen under kameran.");
                }
                let html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 });
                html5QrcodeScanner.render(onScanSuccess);
            </script>
        """, height=400)
        if st.button("Hämta skannat ID till sök"):
            st.components.v1.html("""<script>window.parent.location.href = window.parent.location.href.split('?')[0] + '?q=' + localStorage.getItem('scanned_id');</script>""", height=0)

    q_val = st.query_params.get("q", "")
    query = st.text_input("Sök (ID eller Modell)", value=q_val)

    if st.session_state.df is not None:
        # Filtrering
        results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)] if query else st.session_state.df
        
        # Om vi editerar, visa formulär istället för listan
        if is_admin and st.session_state.edit_idx is not None:
            idx = st.session_state.edit_idx
            row = st.session_state.df.loc[idx]
            st.warning(f"🛠️ Redigerar: {row['Modell']}")
            with st.form("edit_form"):
                c1, c2 = st.columns(2)
                m = c1.text_input("Modell", value=row['Modell'])
                t = c1.text_input("Tillverkare", value=row['Tillverkare'])
                rt = c1.text_input("ID", value=row['Resurstagg'])
                s = c2.selectbox("Status", ["Tillgänglig", "Utlånad", "Service", "Trasig"], index=0)
                own = c2.text_input("Ägare", value=row['Aktuell ägare'])
                
                col_save, col_del, col_can = st.columns(3)
                if col_save.form_submit_button("Spara"):
                    st.session_state.df.loc[idx, ['Modell', 'Tillverkare', 'Resurstagg', 'Status', 'Aktuell ägare']] = [m, t, rt, s, own]
                    save_data(); st.session_state.edit_idx = None; st.rerun()
                if col_del.form_submit_button("Radera 🗑️"):
                    st.session_state.df = st.session_state.df.drop(idx).reset_index(drop=True)
                    save_data(); st.session_state.edit_idx = None; st.rerun()
                if col_can.form_submit_button("Avbryt"):
                    st.session_state.edit_idx = None; st.rerun()
        else:
            # Visa sökresultat
            for idx, row in results.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1, 2, 1])
                    with c1:
                        if row['Enhetsfoto']: st.image(row['Enhetsfoto'], width=100)
                        else: st.write("📷 Ingen bild")
                    with c2:
                        st.subheader(row['Modell'])
                        st.write(f"ID: {row['Resurstagg']} | Status: {row['Status']}")
                        if row['Status'] == 'Utlånad': st.error(f"Lånad av: {row['Aktuell ägare']}")
                    with c3:
                        if row['Status'] == 'Tillgänglig':
                            if st.button("🛒 Låna", key=f"btn_l_{idx}"):
                                st.session_state.cart.append(row.to_dict())
                                st.rerun()
                        if is_admin:
                            if st.button("✏️ EDIT", key=f"btn_e_{idx}"):
                                st.session_state.edit_idx = idx
                                st.rerun()

# --- 9. VY: REGISTRERA NY (ALLA FÄLT) ---
elif menu == "➕ Registrera Ny":
    st.header("Registrera ny utrustning")
    with st.form("reg_form"):
        col1, col2 = st.columns(2)
        with col1:
            m = st.text_input("Modell *")
            t = st.text_input("Tillverkare")
            ty = st.text_input("Typ")
            f = st.text_input("Färg")
        with col2:
            rt_col, gen_col = st.columns([2,1])
            res_tag = rt_col.text_input("Resurstagg (ID) *", key="reg_id")
            if gen_col.form_submit_button("🔄"): # Generera-knapp
                res_tag = generate_serial()
                st.info(f"ID genererat: {res_tag}")
            
            barcode = st.text_input("Streckkod")
            status = st.selectbox("Status", ["Tillgänglig", "Service", "Reserv"])
        
        foto = st.camera_input("Ta foto")
        
        if st.form_submit_button("✅ SPARA I LAGER"):
            if m and res_tag:
                new_row = {
                    "Modell": m, "Tillverkare": t, "Typ": ty, "Färg": f,
                    "Resurstagg": res_tag, "Streckkod": barcode, "Status": status,
                    "Enhetsfoto": img_to_b64(foto) if foto else "",
                    "Senast inventerad": datetime.now().strftime("%Y-%m-%d")
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data()
                st.success("Produkt sparad!")
            else: st.error("Modell och ID krävs!")

# --- 10. VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    borrowed = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    for idx, row in borrowed.iterrows():
        with st.container(border=True):
            st.write(f"**{row['Modell']}** - Lånad av: {row['Aktuell ägare']}")
            if st.button("REGISTRERA SOM ÅTERKOMMEN", key=f"ret_btn_{idx}"):
                st.session_state.df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
                save_data(); st.rerun()

# --- 11. VY: ADMIN (BULK QR 3x4 cm) ---
elif menu == "⚙️ Admin":
    if not is_admin: st.warning("Logga in som admin.")
    else:
        t1, t2 = st.tabs(["Lagerlista", "🖨️ Bulk QR-Utskrift"])
        with t1:
            st.dataframe(st.session_state.df)
            if st.button("Synka om med Google"): load_data(); st.rerun()
        
        with t2:
            st.subheader("Välj produkter för etiketter (3x4 cm)")
            selected = st.multiselect("Välj prylar", st.session_state.df['Modell'].tolist())
            if selected:
                # CSS för exakt 3x4 cm utskrift
                qr_html = """
                <style>
                    .label-grid { display: flex; flex-wrap: wrap; gap: 5px; background: white; }
                    .qr-label { 
                        width: 3cm; 
                        height: 4cm; 
                        border: 0.5px solid #eee; 
                        display: flex; 
                        flex-direction: column; 
                        align-items: center; 
                        justify-content: center; 
                        padding: 2px;
                        font-family: sans-serif;
                        page-break-inside: avoid;
                    }
                    .qr-label img { width: 2.5cm; height: 2.5cm; }
                    .qr-label b { font-size: 10px; margin-top: 2px; text-align: center; overflow: hidden; }
                </style>
                <div class="label-grid">
                """
                for m_name in selected:
                    item = st.session_state.df[st.session_state.df['Modell'] == m_name].iloc[0]
                    qr_code = generate_qr_b64(item['Resurstagg'])
                    qr_html += f"""
                    <div class="qr-label">
                        <img src="data:image/png;base64,{qr_code}">
                        <b>{item['Modell']}</b>
                        <small style="font-size:8px;">{item['Resurstagg']}</small>
                    </div>
                    """
                qr_html += "</div><br><button onclick='window.print()'>SKRIV UT ETIKETTER</button>"
                st.components.v1.html(qr_html, height=600, scrolling=True)

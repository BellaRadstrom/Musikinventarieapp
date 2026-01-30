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

# --- INITIALISERING ---
if 'df' not in st.session_state: st.session_state.df = None
if 'cart' not in st.session_state: st.session_state.cart = []
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None

# --- HJÄLPFUNKTIONER ---
def clean_id(val):
    if pd.isna(val) or val == "": return ""
    s = str(val).strip()
    if s.endswith(".0"): s = s[:-2]
    return s

def img_to_b64(image_file):
    try:
        img = Image.open(image_file)
        img.thumbnail((300, 300))
        buf = BytesIO()
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=75)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except: return ""

def generate_qr_b64(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(str(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# --- DATALADDNING ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        expected_cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad"]
        for col in expected_cols:
            if col not in data.columns: data[col] = ""
        data["Resurstagg"] = data["Resurstagg"].apply(clean_id)
        st.session_state.df = data.fillna("")
    except Exception as e: st.error(f"Kunde inte ladda Sheets: {e}")

def save_data():
    try:
        conn.update(worksheet="Sheet1", data=st.session_state.df.fillna("").astype(str))
        st.cache_data.clear()
    except Exception as e: st.error(f"Kunde inte spara: {e}")

if st.session_state.df is None: load_data()

# --- ADMIN STATUS ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Admin-lösenord", type="password")
if pwd == "Birka":
    st.session_state.authenticated = True
    st.success("🔓 Inloggad som Admin")
else:
    st.session_state.authenticated = False
    st.info("👤 Standard-användare")

# --- UI BANNER ---
if st.session_state.authenticated:
    st.markdown("<div style='background-color:#ff4b4b; padding:10px; border-radius:5px; text-align:center; color:white; font-weight:bold;'>ADMIN-LÄGE AKTIVERAT (Ändra/Radera tillgängligt)</div>", unsafe_image_metadata=True, unsafe_allow_html=True)
else:
    st.markdown("<div style='background-color:#2e7d32; padding:10px; border-radius:5px; text-align:center; color:white; font-weight:bold;'>ANVÄNDAR-LÄGE (Sök & Låna)</div>", unsafe_allow_html=True)

# --- VARUKORG (SIDEBAR) ---
if st.session_state.cart:
    st.sidebar.divider()
    st.sidebar.subheader("🛒 Varukorg")
    for i, item in enumerate(st.session_state.cart):
        st.sidebar.caption(f"{i+1}. {item['Modell']} ({item['Resurstagg']})")
    
    borrower_name = st.sidebar.text_input("Namn på låntagare (Krävs) *")
    
    if st.sidebar.button("SLUTFÖR UTLÅN", type="primary", use_container_width=True):
        if borrower_name:
            today = datetime.now().strftime("%Y-%m-%d")
            for item in st.session_state.cart:
                idx = st.session_state.df[st.session_state.df['Resurstagg'] == item['Resurstagg']].index
                st.session_state.df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower_name, today]
            save_data()
            st.session_state.last_borrower = borrower_name
            st.session_state.last_loan = st.session_state.cart.copy()
            st.session_state.cart = []
            st.rerun()
        else:
            st.sidebar.error("Du måste ange ett namn!")

    if st.sidebar.button("Rensa vagn"):
        st.session_state.cart = []
        st.rerun()

# --- MENY ---
menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Låna", "🔄 Återlämning", "➕ Registrera Nytt", "⚙️ Admin"])

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    # Kvitto efter utlån
    if 'last_loan' in st.session_state and st.session_state.last_loan:
        with st.expander("✅ Utlåning lyckades! Klicka här för kvitto", expanded=True):
            receipt_html = f"<h3>Lånekvitto - {datetime.now().strftime('%Y-%m-%d')}</h3><p>Låntagare: <b>{st.session_state.last_borrower}</b></p><ul>"
            for itm in st.session_state.last_loan: receipt_html += f"<li>{itm['Modell']} ({itm['Resurstagg']})</li>"
            receipt_html += "</ul><button onclick='window.print()'>Skriv ut kvitto</button>"
            st.components.v1.html(receipt_html, height=200)
            if st.button("Stäng kvitto"): 
                st.session_state.last_loan = None
                st.rerun()

    with st.expander("📷 Starta QR-skanner", expanded=True):
        st.components.v1.html("""
            <div id="reader" style="width:100%;"></div>
            <p id="status" style="text-align:center; font-family:sans-serif; color:gray;">Siktar...</p>
            <script src="https://unpkg.com/html5-qrcode"></script>
            <script>
                function onScanSuccess(decodedText) {
                    document.getElementById('status').innerText = "TRÄFF: " + decodedText;
                    localStorage.setItem('scanned_code', decodedText);
                    if(navigator.vibrate) navigator.vibrate(100);
                }
                let html5QrcodeScanner = new Html5Qrcode("reader");
                html5QrcodeScanner.start({ facingMode: "environment" }, { fps: 10, qrbox: 250 }, onScanSuccess);
            </script>
        """, height=350)
        
        if st.button("📥 HÄMTA KOD TILL SÖKFÄLTET", use_container_width=True, type="primary"):
            st.components.v1.html("""
                <script>
                    const code = localStorage.getItem('scanned_code');
                    if(code) {
                        const url = new URL(window.parent.location.href);
                        url.searchParams.set('q', code);
                        window.parent.location.href = url.href;
                    } else { alert("Ingen kod skannad ännu."); }
                </script>
            """, height=0)

    search_query = st.query_params.get("q", "")
    query = st.text_input("Sök produkt (ID, Modell, Typ...)", value=search_query)

    if query:
        res = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)]
        for idx, row in res.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([1, 3, 1])
                with col1:
                    if row['Enhetsfoto']: st.image(row['Enhetsfoto'], width=100)
                    else: st.write("📷 Ingen bild")
                with col2:
                    st.subheader(row['Modell'])
                    st.write(f"**ID:** {row['Resurstagg']} | **Status:** {row['Status']}")
                    if row['Status'] == 'Utlånad': st.error(f"Lånad av: {row['Aktuell ägare']} ({row['Utlåningsdatum']})")
                with col3:
                    if row['Status'] == 'Tillgänglig':
                        if st.button("🛒 Låna", key=f"add_{idx}"):
                            if not any(d['Resurstagg'] == row['Resurstagg'] for d in st.session_state.cart):
                                st.session_state.cart.append(row.to_dict())
                                st.rerun()
                    if st.session_state.authenticated:
                        if st.button("✏️ Editera", key=f"ed_{idx}"):
                            st.session_state.edit_idx = idx
                            st.rerun()

# --- VY: EDITERING (VISAS NÄR MAN TRYCKER PÅ EDITERA) ---
if st.session_state.edit_idx is not None:
    idx = st.session_state.edit_idx
    row = st.session_state.df.loc[idx]
    st.divider()
    st.subheader(f"🛠️ Redigera: {row['Modell']}")
    
    with st.form("edit_form"):
        col_a, col_b = st.columns(2)
        with col_a:
            new_modell = st.text_input("Modell", value=row['Modell'])
            new_tillverkare = st.text_input("Tillverkare", value=row['Tillverkare'])
            new_typ = st.text_input("Typ", value=row['Typ'])
            new_färg = st.text_input("Färg", value=row['Färg'])
            new_id = st.text_input("Resurstagg (ID)", value=row['Resurstagg'])
        with col_b:
            new_barcode = st.text_input("Streckkod", value=row['Streckkod'])
            new_status = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service", "Trasig"], index=["Tillgänglig", "Utlånad", "Service", "Trasig"].index(row['Status']) if row['Status'] in ["Tillgänglig", "Utlånad", "Service", "Trasig"] else 0)
            new_owner = st.text_input("Aktuell ägare", value=row['Aktuell ägare'])
            new_date = st.text_input("Utlåningsdatum", value=row['Utlåningsdatum'])
            new_img_file = st.file_uploader("Byt bild (valfritt)")
            
        delete_confirm = st.checkbox("Jag vill RADERA denna produkt permanent")
        
        c_save, c_cancel = st.columns(2)
        if c_save.form_submit_button("SPARA ÄNDRINGAR", use_container_width=True):
            if delete_confirm:
                st.session_state.df = st.session_state.df.drop(idx).reset_index(drop=True)
                save_data()
                st.session_state.edit_idx = None
                st.rerun()
            else:
                st.session_state.df.at[idx, 'Modell'] = new_modell
                st.session_state.df.at[idx, 'Tillverkare'] = new_tillverkare
                st.session_state.df.at[idx, 'Typ'] = new_typ
                st.session_state.df.at[idx, 'Färg'] = new_färg
                st.session_state.df.at[idx, 'Resurstagg'] = clean_id(new_id)
                st.session_state.df.at[idx, 'Streckkod'] = new_barcode
                st.session_state.df.at[idx, 'Status'] = new_status
                st.session_state.df.at[idx, 'Aktuell ägare'] = new_owner
                st.session_state.df.at[idx, 'Utlåningsdatum'] = new_date
                if new_img_file: st.session_state.df.at[idx, 'Enhetsfoto'] = img_to_b64(new_img_file)
                save_data()
                st.session_state.edit_idx = None
                st.rerun()
        if c_cancel.form_submit_button("AVBRYT", use_container_width=True):
            st.session_state.edit_idx = None
            st.rerun()

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    borrowed_df = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if borrowed_df.empty:
        st.info("Inga produkter är utlånade just nu.")
    else:
        for idx, row in borrowed_df.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{row['Modell']}** (ID: {row['Resurstagg']}) - Lånad av: {row['Aktuell ägare']}")
                if c2.button("ÅTERLÄMNA", key=f"ret_{idx}"):
                    st.session_state.df.at[idx, 'Status'] = 'Tillgänglig'
                    st.session_state.df.at[idx, 'Aktuell ägare'] = ''
                    st.session_state.df.at[idx, 'Utlåningsdatum'] = ''
                    st.session_state.df.at[idx, 'Senast inventerad'] = datetime.now().strftime("%Y-%m-%d")
                    save_data()
                    st.success(f"{row['Modell']} återlämnad!")
                    st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    if not st.session_state.authenticated: st.warning("Du måste vara inloggad som Admin för att registrera.")
    else:
        with st.form("new_reg"):
            m = st.text_input("Modell *")
            rt = st.text_input("Resurstagg (ID) *")
            f = st.camera_input("Ta foto")
            if st.form_submit_button("Registrera"):
                new_row = {"Modell": m, "Resurstagg": clean_id(rt), "Status": "Tillgänglig", "Enhetsfoto": img_to_b64(f) if f else ""}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data()
                st.success("Registrerad!")

# --- VY: ADMIN (BULK QR) ---
elif menu == "⚙️ Admin":
    if not st.session_state.authenticated: st.warning("Logga in.")
    else:
        tab1, tab2 = st.tabs(["📊 Databas", "🏷️ Bulk QR"])
        with tab1:
            st.dataframe(st.session_state.df)
            if st.button("Tvinga omladdning från Sheets"): load_data(); st.rerun()
        with tab2:
            st.subheader("Skriv ut etiketter")
            sel = st.multiselect("Välj produkter:", st.session_state.df['Modell'].tolist())
            if sel:
                itms = st.session_state.df[st.session_state.df['Modell'].isin(sel)].to_dict('records')
                html = "<div style='display:flex; flex-wrap:wrap; gap:10px;'>"
                for itm in itms:
                    qr = generate_qr_b64(itm['Resurstagg'])
                    html += f"<div style='border:1px solid black; padding:5px; text-align:center; width:120px;'><img src='data:image/png;base64,{qr}' style='width:100px;'><br><small>{itm['Modell']}<br>{itm['Resurstagg']}</small></div>"
                html += "</div><br><button onclick='window.print()'>Skriv ut</button>"
                st.components.v1.html(html, height=500, scrolling=True)

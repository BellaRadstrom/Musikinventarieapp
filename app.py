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
st.set_page_config(page_title="Musik-IT Birka v4", layout="wide", page_icon="🎸")

# --- 2. SESSION STATE (Loggar och Minne) ---
if 'df' not in st.session_state: st.session_state.df = None
if 'cart' not in st.session_state: st.session_state.cart = []
if 'error_log' not in st.session_state: st.session_state.error_log = []
if 'last_loan' not in st.session_state: st.session_state.last_loan = None

def add_log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.error_log.append(f"[{ts}] {msg}")

# --- 3. HJÄLPFUNKTIONER ---
def generate_serial():
    prefix = datetime.now().strftime("%y%m%d")
    suffix = random.randint(100, 999)
    return f"{prefix}-{suffix}"

def img_to_b64(image_file):
    try:
        img = Image.open(image_file)
        img.thumbnail((400, 400))
        buf = BytesIO()
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=80)
        return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except Exception as e:
        add_log(f"Bildfel: {e}")
        return ""

def generate_qr_b64(data):
    qr = qrcode.QRCode(box_size=10, border=2)
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
        add_log(f"Sheets-laddning misslyckades: {e}")

if st.session_state.df is None: load_data()

def save_data():
    try:
        conn.update(worksheet="Sheet1", data=st.session_state.df.astype(str))
        st.toast("Synkat med Google Sheets!")
    except Exception as e:
        add_log(f"Spara-fel: {e}")
        st.error("Kunde inte spara till Sheets.")

# --- 5. ADMIN LOGIN ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Admin lösenord", type="password")
is_admin = (pwd == "Birka")

# --- 6. VARUKORG & FÖLJESEDEL ---
if st.session_state.cart:
    with st.sidebar.expander("🛒 VARUKORG", expanded=True):
        for i, item in enumerate(st.session_state.cart):
            st.write(f"{i+1}. {item['Modell']}")
        
        name = st.text_input("Ditt namn *")
        if st.button("SLUTFÖR LÅN", type="primary"):
            if name:
                today = datetime.now().strftime("%Y-%m-%d")
                for itm in st.session_state.cart:
                    idx = st.session_state.df[st.session_state.df['Resurstagg'] == itm['Resurstagg']].index
                    st.session_state.df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', name, today]
                
                st.session_state.last_loan = {"name": name, "date": today, "items": st.session_state.cart.copy()}
                st.session_state.cart = []
                save_data()
                st.rerun()
            else: st.error("Namn krävs!")

# --- 7. MENY ---
menu = st.sidebar.selectbox("Välj funktion", ["🔍 Sök & Låna", "➕ Registrera Ny", "🔄 Återlämning", "⚙️ Admin-Verktyg"])

# --- 8. VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    # Visa Följesedel (Kvitto)
    if st.session_state.last_loan:
        with st.container(border=True):
            st.success("### ✅ Lån genomfört!")
            st.write(f"**Låntagare:** {st.session_state.last_loan['name']}")
            st.write(f"**Datum:** {st.session_state.last_loan['date']}")
            st.write("**Produkter:**")
            for i in st.session_state.last_loan['items']: st.write(f"- {i['Modell']} ({i['Resurstagg']})")
            st.button("🖨️ Skriv ut (Använd webbläsarens utskrift)", on_click=lambda: None)
            if st.button("Stäng kvitto"): 
                st.session_state.last_loan = None
                st.rerun()

    # QR-Skanner (Kompakt storlek)
    with st.expander("📷 Öppna QR-Skanner", expanded=False):
        st.components.v1.html("""
            <style>#reader { width: 300px !important; margin: auto; }</style>
            <div id="reader"></div>
            <script src="https://unpkg.com/html5-qrcode"></script>
            <script>
                const scanner = new Html5Qrcode("reader");
                scanner.start({ facingMode: "environment" }, { fps: 10, qrbox: 200 }, 
                (txt) => { 
                    localStorage.setItem('scanned_id', txt);
                    document.getElementById('reader').style.border = "5px solid #4CAF50";
                });
            </script>
        """, height=350)
        if st.button("Fyll i skannat ID"):
            st.components.v1.html("""<script>window.parent.location.href = window.parent.location.href.split('?')[0] + '?q=' + localStorage.getItem('scanned_id');</script>""", height=0)

    search_q = st.query_params.get("q", "")
    query = st.text_input("Sök på Modell eller ID", value=search_q)

    if st.session_state.df is not None:
        filtered = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)] if query else st.session_state.df
        
        for idx, row in filtered.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 2, 1])
                with c1:
                    if row['Enhetsfoto']: st.image(row['Enhetsfoto'], width=150)
                    else: st.info("Ingen bild")
                    qr_img = generate_qr_b64(row['Resurstagg'])
                    st.markdown(f"<img src='data:image/png;base64,{qr_img}' width='100'>", unsafe_allow_html=True)
                with c2:
                    st.subheader(row['Modell'])
                    st.write(f"**ID:** {row['Resurstagg']} | **Status:** {row['Status']}")
                    st.write(f"**Typ:** {row['Typ']} | **Färg:** {row['Färg']}")
                    if row['Status'] == 'Utlånad': st.warning(f"Lånad av: {row['Aktuell ägare']}")
                with c3:
                    if row['Status'] == 'Tillgänglig':
                        if st.button("🛒 Lägg i vagn", key=f"add_{idx}"):
                            st.session_state.cart.append(row.to_dict())
                            st.rerun()
                    if is_admin:
                        if st.button("✏️ EDITERA", key=f"edit_{idx}"):
                            st.session_state.edit_idx = idx
                            st.rerun()

    # Edit-läge för Admin
    if is_admin and 'edit_idx' in st.session_state and st.session_state.edit_idx is not None:
        idx = st.session_state.edit_idx
        row = st.session_state.df.loc[idx]
        with st.form("edit_form"):
            st.subheader(f"Redigerar {row['Modell']}")
            col1, col2 = st.columns(2)
            # Här kan du lägga till alla fält för editering likt "Registrera Ny"
            new_status = col1.selectbox("Status", ["Tillgänglig", "Utlånad", "Trasig", "Service"], index=0)
            delete_me = st.checkbox("❌ Radera denna produkt helt")
            if st.form_submit_button("Spara ändringar"):
                if delete_me: st.session_state.df = st.session_state.df.drop(idx)
                else: st.session_state.df.at[idx, 'Status'] = new_status
                save_data()
                st.session_state.edit_idx = None
                st.rerun()

# --- 9. VY: REGISTRERA NY (ALLA FÄLT) ---
elif menu == "➕ Registrera Ny":
    st.header("Registrera ny utrustning")
    
    with st.form("reg_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            mod = st.text_input("Modell *")
            tillv = st.text_input("Tillverkare")
            typ = st.text_input("Typ (t.ex. Gitarr)")
            farg = st.text_input("Färg")
        with c2:
            tag_col1, tag_col2 = st.columns([2,1])
            res_tag = tag_col1.text_input("Resurstagg / ID *", key="manual_tag")
            if tag_col2.form_submit_button("🔄 Generera"):
                st.info("Klicka igen för att bekräfta ID") # Streamlit form quirk
                res_tag = generate_serial()
            
            barcode = st.text_input("Streckkod")
            status = st.selectbox("Status", ["Tillgänglig", "Service", "Reserv"])
        
        foto = st.camera_input("Ta enhetsfoto")
        
        if st.form_submit_button("✅ SPARA PRODUKT"):
            if mod and res_tag:
                new_data = {
                    "Modell": mod, "Tillverkare": tillv, "Typ": typ, "Färg": farg,
                    "Resurstagg": res_tag, "Streckkod": barcode, "Status": status,
                    "Enhetsfoto": img_to_b64(foto) if foto else "",
                    "Senast inventerad": datetime.now().strftime("%Y-%m-%d")
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
                save_data()
                st.success(f"Sparade {mod} med ID {res_tag}")
            else: st.error("Modell och ID är obligatoriskt!")

# --- 10. VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Lämna tillbaka utrustning")
    borrowed = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if borrowed.empty: st.info("Inga utlånade produkter.")
    for idx, row in borrowed.iterrows():
        with st.container(border=True):
            st.write(f"**{row['Modell']}** (Lånad av: {row['Aktuell ägare']})")
            if st.button("REGISTRERA ÅTERLÄMNAD", key=f"ret_{idx}"):
                st.session_state.df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
                st.session_state.df.at[idx, 'Senast inventerad'] = datetime.now().strftime("%Y-%m-%d")
                save_data()
                st.rerun()

# --- 11. VY: ADMIN-VERKTYG ---
elif menu == "⚙️ Admin-Verktyg":
    if not is_admin: 
        st.warning("Vänligen ange lösenord i sidomenyn.")
    else:
        tab1, tab2, tab3 = st.tabs(["📊 Lagerhantering", "🖨️ Bulk QR-utskrift", "📝 Fel-logg"])
        
        with tab1:
            st.dataframe(st.session_state.df)
            if st.button("Tvinga omladdning från Sheets"):
                st.session_state.df = None
                st.rerun()
        
        with tab2:
            st.subheader("Välj produkter för QR-utskrift")
            to_print = st.multiselect("Välj prylar", st.session_state.df['Modell'].tolist())
            if to_print:
                html_grid = "<div style='display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px;'>"
                for m_name in to_print:
                    item = st.session_state.df[st.session_state.df['Modell'] == m_name].iloc[0]
                    qr_b64 = generate_qr_b64(item['Resurstagg'])
                    html_grid += f"""
                        <div style='border: 1px solid #ccc; padding: 10px; text-align: center;'>
                            <img src='data:image/png;base64,{qr_b64}' width='100'><br>
                            <b style='font-size: 10px;'>{item['Modell']}</b><br>
                            <small style='font-size: 8px;'>ID: {item['Resurstagg']}</small>
                        </div>
                    """
                html_grid += "</div>"
                st.components.v1.html(html_grid, height=600, scrolling=True)
                st.button("Skriv ut sidan (Ctrl + P)")

        with tab3:
            st.subheader("Systemhändelser")
            for log in reversed(st.session_state.error_log):
                st.code(log)
            if st.button("Rensa logg"): 
                st.session_state.error_log = []
                st.rerun()

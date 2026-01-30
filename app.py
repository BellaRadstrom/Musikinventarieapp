import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image
import base64
import time

# --- 1. CONFIG & RESET ---
st.set_page_config(page_title="Musik-IT Birka v3", layout="wide", page_icon="🎸")

# Tvinga appen att glömma gammal skit om man vill
if st.sidebar.button("🔄 Nollställ & Ladda om app"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.cache_data.clear()
    st.rerun()

# --- 2. INITIALISERING ---
if 'df' not in st.session_state: st.session_state.df = None
if 'cart' not in st.session_state: st.session_state.cart = []
if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None

# --- 3. ADMIN LOGIN (STRIKT) ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Lösenord för Admin", type="password")
is_admin = (pwd == "Birka")

if is_admin:
    st.markdown("""<div style='background-color:#d32f2f; color:white; padding:15px; border-radius:10px; text-align:center; font-size:20px; font-weight:bold; margin-bottom:20px;'>
                🚨 ADMIN-LÄGE AKTIVERAT 🚨<br><small>Du kan nu ändra, radera och registrera produkter</small></div>""", unsafe_allow_html=True)
else:
    st.markdown("""<div style='background-color:#388e3c; color:white; padding:15px; border-radius:10px; text-align:center; font-size:20px; font-weight:bold; margin-bottom:20px;'>
                📱 ANVÄNDAR-LÄGE<br><small>Sök och låna utrustning</small></div>""", unsafe_allow_html=True)

# --- 4. FUNKTIONER ---
def clean_id(val):
    if pd.isna(val) or val == "": return ""
    return str(val).strip().split('.')[0]

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
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(str(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# --- 5. DATAHANTERING ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # Cache-buster: lägger till en unik siffra (timestamp) för att tvinga fram ny data
        cache_buster = str(time.time())
        data = conn.read(worksheet="Sheet1", ttl=0) 
        cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad"]
        for col in cols:
            if col not in data.columns: data[col] = ""
        data["Resurstagg"] = data["Resurstagg"].apply(clean_id)
        st.session_state.df = data.fillna("")
    except Exception as e:
        st.error(f"Fel vid hämtning: {e}")

if st.session_state.df is None:
    load_data()

def save_to_sheets():
    try:
        conn.update(worksheet="Sheet1", data=st.session_state.df.astype(str))
        st.toast("Sparat i molnet!", icon="☁️")
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")

# --- 6. VARUKORG ---
if st.session_state.cart:
    st.sidebar.divider()
    st.sidebar.subheader("🛒 Varukorg")
    for i, item in enumerate(st.session_state.cart):
        st.sidebar.write(f"{i+1}. {item['Modell']}")
    
    borrower = st.sidebar.text_input("Vem lånar? (Tvingande) *")
    
    if st.sidebar.button("SLUTFÖR LÅN", type="primary", use_container_width=True):
        if borrower:
            today = datetime.now().strftime("%Y-%m-%d")
            for c_item in st.session_state.cart:
                idx = st.session_state.df[st.session_state.df['Resurstagg'] == c_item['Resurstagg']].index
                st.session_state.df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, today]
            save_to_sheets()
            st.session_state.last_loan_info = {"name": borrower, "items": st.session_state.cart.copy()}
            st.session_state.cart = []
            st.rerun()
        else:
            st.sidebar.error("Ange låntagarens namn!")

    if st.sidebar.button("Töm vagn"):
        st.session_state.cart = []
        st.rerun()

# --- 7. MENY ---
menu = st.sidebar.selectbox("Gå till", ["🔍 Sök & Låna", "🔄 Återlämning", "➕ Registrera Ny", "⚙️ Lagerlista"])

# --- 8. VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    # Visa kvitto om lån just gjorts
    if 'last_loan_info' in st.session_state:
        with st.container(border=True):
            st.success(f"✅ Utlånat till {st.session_state.last_loan_info['name']}")
            st.write("Produkter:")
            for itm in st.session_state.last_loan_info['items']:
                st.write(f"- {itm['Modell']} ({itm['Resurstagg']})")
            if st.button("Stäng kvitto"):
                del st.session_state.last_loan_info
                st.rerun()

    # Kamera
    with st.expander("📷 Skanna QR", expanded=True):
        st.components.v1.html("""
            <div id="reader" style="width:100%;"></div>
            <script src="https://unpkg.com/html5-qrcode"></script>
            <script>
                const scanner = new Html5Qrcode("reader");
                scanner.start({ facingMode: "environment" }, { fps: 15, qrbox: 250 }, 
                (txt) => { 
                    localStorage.setItem('birka_qr', txt);
                    document.getElementById('reader').style.border = "10px solid #4CAF50";
                });
            </script>
        """, height=350)
        if st.button("Hämta kod till sök", use_container_width=True, type="primary"):
            st.components.v1.html("""<script>window.parent.location.href = window.parent.location.href.split('?')[0] + '?s=' + localStorage.getItem('birka_qr');</script>""", height=0)

    search_val = st.query_params.get("s", "")
    q = st.text_input("Sök i lagret", value=search_val)

    if st.session_state.df is not None:
        results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)] if q else st.session_state.df
        
        for idx, row in results.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 2, 1])
                with c1:
                    if row['Enhetsfoto']: st.image(row['Enhetsfoto'], width=100)
                    else: st.write("📷")
                with c2:
                    st.subheader(row['Modell'])
                    st.write(f"ID: {row['Resurstagg']} | Status: {row['Status']}")
                    if row['Status'] == 'Utlånad': st.warning(f"Låntagare: {row['Aktuell ägare']}")
                with c3:
                    if row['Status'] == 'Tillgänglig':
                        if st.button("🛒 Låna", key=f"l_{idx}"):
                            st.session_state.cart.append(row.to_dict())
                            st.rerun()
                    if is_admin:
                        if st.button("✏️ EDIT", key=f"e_{idx}"):
                            st.session_state.edit_idx = idx
                            st.rerun()

# --- 9. VY: EDITERING (FULLSTÄNDIG) ---
if st.session_state.edit_idx is not None:
    idx = st.session_state.edit_idx
    row = st.session_state.df.loc[idx]
    st.divider()
    st.header(f"Redigerar: {row['Modell']}")
    
    with st.form("edit_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_m = st.text_input("Modell", value=row['Modell'])
            new_t = st.text_input("Tillverkare", value=row['Tillverkare'])
            new_ty = st.text_input("Typ", value=row['Typ'])
            new_f = st.text_input("Färg", value=row['Färg'])
            new_id = st.text_input("Resurstagg (ID)", value=row['Resurstagg'])
        with col2:
            new_s = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service", "Trasig"], 
                               index=["Tillgänglig", "Utlånad", "Service", "Trasig"].index(row['Status']) if row['Status'] in ["Tillgänglig", "Utlånad", "Service", "Trasig"] else 0)
            new_owner = st.text_input("Aktuell ägare", value=row['Aktuell ägare'])
            new_date = st.text_input("Utlåningsdatum", value=row['Utlåningsdatum'])
            new_inv = st.text_input("Senast inventerad", value=row['Senast inventerad'])
            new_img = st.file_uploader("Byt bild")
        
        st.write("---")
        delete_confirm = st.checkbox("❌ RADERA DENNA PRODUKT HELT OCH HÅLLET")
        
        sub, can = st.columns(2)
        if sub.form_submit_button("SPARA ÄNDRINGAR", use_container_width=True):
            if delete_confirm:
                st.session_state.df = st.session_state.df.drop(idx).reset_index(drop=True)
            else:
                st.session_state.df.loc[idx, ['Modell', 'Tillverkare', 'Typ', 'Färg', 'Resurstagg', 'Status', 'Aktuell ägare', 'Utlåningsdatum', 'Senast inventerad']] = [new_m, new_t, new_ty, new_f, new_id, new_s, new_owner, new_date, new_inv]
                if new_img: st.session_state.df.at[idx, 'Enhetsfoto'] = img_to_b64(new_img)
            
            save_to_sheets()
            st.session_state.edit_idx = None
            st.rerun()
        if can.form_submit_button("AVBRYT", use_container_width=True):
            st.session_state.edit_idx = None
            st.rerun()

# --- 10. VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    borrowed = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if borrowed.empty:
        st.info("Inga utestående lån hittades.")
    else:
        for idx, row in borrowed.iterrows():
            with st.container(border=True):
                st.write(f"**{row['Modell']}** - Lånad av: {row['Aktuell ägare']} ({row['Utlåningsdatum']})")
                if st.button("REGISTRERA ÅTERKOMMEN", key=f"r_{idx}"):
                    st.session_state.df.at[idx, 'Status'] = 'Tillgänglig'
                    st.session_state.df.at[idx, 'Aktuell ägare'] = ''
                    st.session_state.df.at[idx, 'Utlåningsdatum'] = ''
                    st.session_state.df.at[idx, 'Senast inventerad'] = datetime.now().strftime("%Y-%m-%d")
                    save_to_sheets()
                    st.rerun()

# --- 11. VY: REGISTRERA ---
elif menu == "➕ Registrera Ny":
    if not is_admin: st.warning("Logga in som Admin först.")
    else:
        with st.form("new_item"):
            m = st.text_input("Modell *")
            i = st.text_input("ID/Resurstagg *")
            f = st.camera_input("Ta foto")
            if st.form_submit_button("Spara i lager"):
                new_row = {"Modell": m, "Resurstagg": clean_id(i), "Status": "Tillgänglig", "Enhetsfoto": img_to_b64(f) if f else ""}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_to_sheets()
                st.success("Produkten sparad!")

# --- 12. VY: LAGERLISTA (ADMIN) ---
elif menu == "⚙️ Lagerlista":
    if not is_admin: st.warning("Logga in.")
    else:
        st.subheader("Hela lagret")
        st.dataframe(st.session_state.df)
        if st.button("Synka om med Google Sheets nu"):
            load_data()
            st.rerun()

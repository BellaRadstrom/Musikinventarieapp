import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image
import base64
import random
import cv2
import numpy as np

# --- 1. SETUP ---
st.set_page_config(page_title="Musik-IT Birka v16.3", layout="wide")

# Session states
for key in ['cart', 'edit_idx', 'debug_log', 'last_loan', 'search_query', 'gen_id', 'cam_active', 'inv_check']:
    if key not in st.session_state:
        if key == 'inv_check': st.session_state[key] = {}
        elif key in ['cart', 'debug_log']: st.session_state[key] = []
        else: st.session_state[key] = False if key == 'cam_active' else ""

def add_log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.debug_log.append(f"[{ts}] {msg}")

# --- 2. DATA CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data_force():
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        # Säkerställ att alla kolumner finns för att undvika KeyError
        cols = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", 
                "Streckkod", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad", "Notering"]
        for c in cols:
            if c not in df.columns: df[c] = ""
        return df.fillna("")
    except Exception as e:
        add_log(f"Fetch Error: {e}")
        return pd.DataFrame()

def save_to_sheets(df):
    try:
        conn.update(worksheet="Sheet1", data=df.astype(str))
        st.cache_data.clear()
        st.session_state.df = df
        add_log("Data sparad till Sheets.")
        return True
    except Exception as e:
        st.error(f"Kunde inte spara: {e}")
        return False

if 'df' not in st.session_state or st.session_state.df is None:
    st.session_state.df = get_data_force()

# --- 3. UTILITIES ---
def generate_id(): 
    return f"{datetime.now().strftime('%y%m%d')}-{random.randint(100, 999)}"

def img_to_b64(file):
    if not file: return ""
    img = Image.open(file).convert("RGB")
    img.thumbnail((300, 300))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"

def get_qr_b64(data):
    qr = qrcode.make(str(data))
    buf = BytesIO()
    qr.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def decode_qr_logic(image_file):
    try:
        file_bytes = np.asarray(bytearray(image_file.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(gray)
        return data.strip() if data else ""
    except:
        return ""

# --- 4. SIDEBAR & ADMIN ---
st.sidebar.title("🎸 Musik-IT Birka")
pwd = st.sidebar.text_input("Admin lösenord", type="password", key="sidebar_pwd")
is_admin = (pwd == "Birka")

if is_admin:
    st.markdown("<div style='background:#ff4b4b;padding:10px;border-radius:5px;text-align:center;color:white;font-weight:bold;'>🔴 ADMIN-LÄGE AKTIVERAT</div>", unsafe_allow_html=True)
else:
    st.markdown("<div style='background:#28a745;padding:10px;border-radius:5px;text-align:center;color:white;font-weight:bold;'>🟢 ANVÄNDAR-LÄGE</div>", unsafe_allow_html=True)

# --- 5. VARUKORG ---
if st.session_state.cart:
    with st.sidebar.expander("🛒 VARUKORG", expanded=True):
        for itm in st.session_state.cart: st.caption(f"• {itm['Modell']}")
        borrower = st.text_input("Låntagarens namn *", key="cart_borrower")
        if st.button("BEKRÄFTA LÅN", type="primary"):
            if borrower:
                df = get_data_force()
                today = datetime.now().strftime("%Y-%m-%d")
                for itm in st.session_state.cart:
                    idx = df[df['Resurstagg'] == itm['Resurstagg']].index
                    df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, today]
                if save_to_sheets(df):
                    st.session_state.last_loan = {"name": borrower, "date": today, "items": st.session_state.cart.copy()}
                    st.session_state.cart = []
                    add_log(f"Utlåning till {borrower}")
                    st.rerun()

# --- 6. MENY ---
menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Skanna", "➕ Ny registrering", "🔄 Återlämning", "⚙️ Admin & Inventering"])

# --- 7. SÖK & SKANNA ---
if menu == "🔍 Sök & Skanna":
    if st.session_state.last_loan:
        l = st.session_state.last_loan
        rows = "".join([f"<li><b>{i['Modell']}</b> (ID: {i['Resurstagg']}){f' <br><i>Notering: {i['Notering']}</i>' if i['Notering'] else ''}</li>" for i in l['items']])
        st.components.v1.html(f"<div style='border:2px solid #333;padding:15px;background:white;font-family:sans-serif;'><h3>Lånekvitto: {l['name']}</h3><p>Datum: {l['date']}</p><hr><ul>{rows}</ul><button onclick='window.print()'>🖨️ SKRIV UT</button></div>", height=300)
        if st.button("Stäng kvitto"): st.session_state.last_loan = None; st.rerun()

    with st.expander("📷 QR-SKANNER", expanded=False):
        if not st.session_state.cam_active:
            if st.button("🔌 Starta Kamera"):
                st.session_state.cam_active = True
                st.rerun()
        else:
            if st.button("🔌 Stäng Kamera"):
                st.session_state.cam_active = False
                st.rerun()
            cam_image = st.camera_input("Fota QR-kod", key="search_cam")
            if cam_image:
                scanned = decode_qr_logic(cam_image)
                if scanned:
                    st.session_state.search_query = scanned
                    st.session_state.cam_active = False
                    st.rerun()

    if is_admin and st.session_state.edit_idx is not None:
        idx = st.session_state.edit_idx
        if idx in st.session_state.df.index:
            row = st.session_state.df.loc[idx]
            with st.container(border=True):
                st.subheader(f"🛠️ Editera: {row['Modell']}")
                with st.form("edit_v16_3"):
                    c1, c2 = st.columns(2)
                    e_mod = c1.text_input("Modell", row['Modell'])
                    e_brand = c1.text_input("Tillverkare", row['Tillverkare'])
                    e_typ = c1.selectbox("Typ", ["Instrument", "PA", "Mikrofoner", "Kablage", "Ljus", "Övrigt"], index=0)
                    e_color = c1.text_input("Färg", row['Färg'])
                    e_status = c2.selectbox("Status", ["Tillgänglig", "Service", "Trasig", "Utlånad"], index=0)
                    e_owner = c2.text_input("Ägare", row['Aktuell ägare'])
                    e_note = st.text_area("Notering", row['Notering'])
                    new_edit_photo = st.camera_input("Uppdatera bild (Valfritt)", key="edit_photo_cam")
                    if st.form_submit_button("Spara ändringar"):
                        df = get_data_force()
                        df.loc[idx, ['Modell', 'Tillverkare', 'Typ', 'Färg', 'Status', 'Aktuell ägare', 'Notering']] = [e_mod, e_brand, e_typ, e_color, e_status, e_owner, e_note]
                        if new_edit_photo: df.at[idx, 'Enhetsfoto'] = img_to_b64(new_edit_photo)
                        if save_to_sheets(df):
                            st.session_state.edit_idx = None
                            st.rerun()
                    if st.form_submit_button("Avbryt"): st.session_state.edit_idx = None; st.rerun()

    q_input = st.text_input("Sök...", value=st.session_state.search_query)
    st.session_state.search_query = q_input
    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(st.session_state.search_query, case=False)).any(axis=1)] if st.session_state.search_query else st.session_state.df

    for idx, row in results.head(25).iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if row['Enhetsfoto']: st.image(row['Enhetsfoto'], width=120)
                st.image(f"data:image/png;base64,{get_qr_b64(row['Resurstagg'])}", width=70)
            with c2:
                st.subheader(row['Modell'])
                st.write(f"ID: {row['Resurstagg']} | Status: {row['Status']} | Typ: {row['Typ']}")
                if row['Notering']: st.caption(f"📝 {row['Notering']}")
            with c3:
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒 Lägg till", key=f"a{idx}"):
                        st.session_state.cart.append(row.to_dict()); st.rerun()
                if is_admin:
                    if st.button("✏️ Edit", key=f"e{idx}"):
                        st.session_state.edit_idx = idx; st.rerun()

# --- 8. NY REGISTRERING ---
elif menu == "➕ Ny registrering":
    st.subheader("Registrera ny utrustning")
    if st.button("🔄 Generera ID"):
        st.session_state.gen_id = generate_id(); st.rerun()
    
    with st.form("new_v16_3", clear_on_submit=True):
        c1, c2 = st.columns(2)
        f_mod = c1.text_input("Modell *")
        f_brand = c1.text_input("Tillverkare")
        f_typ = c1.selectbox("Typ", ["Instrument", "PA", "Mikrofoner", "Kablage", "Ljus", "Övrigt"])
        f_color = c1.text_input("Färg")
        f_tag = c2.text_input("Resurstagg (ID) *", value=st.session_state.gen_id)
        f_bc = c2.text_input("Streckkod", value=st.session_state.gen_id)
        f_status = c2.selectbox("Status", ["Tillgänglig", "Service", "Reserv", "Trasig"])
        f_note = st.text_area("Notering")
        
        if st.form_submit_button("✅ SPARA TILL DATABAS"):
            if f_mod and f_tag:
                df_current = get_data_force()
                new_row = {"Modell": f_mod, "Tillverkare": f_brand, "Typ": f_typ, "Färg": f_color, "Resurstagg": f_tag, "Streckkod": f_bc, "Status": f_status, "Notering": f_note, "Enhetsfoto": st.session_state.get('temp_img', ""), "Senast inventerad": datetime.now().strftime("%Y-%m-%d"), "Aktuell ägare": "", "Utlåningsdatum": ""}
                if save_to_sheets(pd.concat([df_current, pd.DataFrame([new_row])], ignore_index=True)):
                    st.success("Sparad!"); st.session_state.gen_id = ""; st.session_state.temp_img = ""; st.rerun()

    if st.checkbox("📷 Ta foto"):
        f_foto = st.camera_input("Produktfoto")
        if f_foto: st.session_state.temp_img = img_to_b64(f_foto); st.success("Bild redo!")

# --- 9. ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.subheader("Återlämning av produkter")
    df_return = get_data_force() # Hämta frisk data för att undvika KeyError
    borrowed = df_return[df_return['Status'] == 'Utlånad']
    
    if not borrowed.empty:
        owner = st.selectbox("Välj låntagare", ["---"] + list(borrowed['Aktuell ägare'].unique()))
        if owner != "---":
            items = borrowed[borrowed['Aktuell ägare'] == owner]
            
            # Knapp för att återlämna ALLA
            if st.button(f"🚨 Återlämna ALLA produkter för {owner}", type="primary"):
                df_upd = get_data_force()
                today = datetime.now().strftime("%Y-%m-%d")
                for idx_item, row_item in items.iterrows():
                    p_idx = df_upd[df_upd['Resurstagg'] == row_item['Resurstagg']].index
                    df_upd.loc[p_idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum', 'Senast inventerad']] = ['Tillgänglig', '', '', today]
                if save_to_sheets(df_upd):
                    add_log(f"Massåterlämning: {owner}")
                    st.success(f"Alla produkter för {owner} har återlämnats!")
                    st.rerun()

            st.write("---")
            st.write("Individuell återlämning:")
            for idx, row in items.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"**{row['Modell']}** (ID: {row['Resurstagg']})")
                    if c2.button("✅ Återlämna", key=f"ret_{row['Resurstagg']}"):
                        df_upd = get_data_force()
                        p_idx = df_upd[df_upd['Resurstagg'] == row['Resurstagg']].index
                        df_upd.loc[p_idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum', 'Senast inventerad']] = ['Tillgänglig', '', '', datetime.now().strftime("%Y-%m-%d")]
                        if save_to_sheets(df_upd): 
                            add_log(f"Återlämning: {row['Modell']}")
                            st.rerun()
    else:
        st.info("Inga produkter är för närvarande utlånade.")

# --- 10. ADMIN & INVENTERING ---
elif menu == "⚙️ Admin & Inventering":
    if is_admin:
        t1, t2, t3 = st.tabs(["📋 Inventering", "🖨️ Bulk QR", "📜 Logg"])
        with t1:
            st.subheader("Checklista för inventering")
            df_inv = st.session_state.df.copy()
            df_inv = df_inv[df_inv['Status'].isin(['Tillgänglig', 'Reserv', 'Service', 'Trasig'])]
            for idx, row in df_inv.iterrows():
                c1, c2, c3 = st.columns([0.5, 3, 2])
                is_checked = c1.checkbox("", key=f"inv_{row['Resurstagg']}", value=st.session_state.inv_check.get(row['Resurstagg'], False))
                if is_checked != st.session_state.inv_check.get(row['Resurstagg'], False):
                    st.session_state.inv_check[row['Resurstagg']] = is_checked
                    if is_checked:
                        temp_df = get_data_force()
                        t_idx = temp_df[temp_df['Resurstagg'] == row['Resurstagg']].index
                        temp_df.loc[t_idx, 'Senast inventerad'] = datetime.now().strftime("%Y-%m-%d")
                        save_to_sheets(temp_df)
                c2.write(f"**{row['Modell']}** ({row['Resurstagg']})")
                c3.write(f"Senast sedd: {row['Senast inventerad']}")
            if st.button("🚩 GENERERA AVVIKELSELISTA"):
                missing = [row for idx, row in df_inv.iterrows() if not st.session_state.inv_check.get(row['Resurstagg'], False)]
                if missing:
                    m_rows = "".join([f"<li><b>{m['Modell']}</b> ({m['Resurstagg']})</li>" for m in missing])
                    st.components.v1.html(f"<div style='border:2px solid red;padding:15px;background:white;'><h2>⚠️ AVVIKELSE</h2><ul>{m_rows}</ul><button onclick='window.print()'>SKRIV UT</button></div>", height=400)
        with t2:
            sel = st.multiselect("Utskrift", st.session_state.df['Modell'].tolist())
            if sel:
                html = "<div style='display:flex;flex-wrap:wrap;gap:10px;'>"
                for m in sel:
                    r = st.session_state.df[st.session_state.df['Modell'] == m].iloc[0]
                    qr_img = get_qr_b64(r['Resurstagg'])
                    html += f"<div style='width:3cm;text-align:center;border:1px solid #ccc;padding:5px;'><img src='data:image/png;base64,{qr_img}' style='width:2.5cm;'><br><small>{r['Modell']}</small></div>"
                st.components.v1.html(html + "</div><br><button onclick='window.print()'>Print</button>", height=500)
        with t3:
            for l in reversed(st.session_state.debug_log): st.text(l)

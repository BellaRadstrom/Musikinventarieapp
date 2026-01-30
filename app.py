import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import qrcode
from io import BytesIO
from PIL import Image
import base64
import random

# --- 1. KONFIGURATION ---
st.set_page_config(page_title="Musik-IT Birka v8", layout="wide")

if 'cart' not in st.session_state: st.session_state.cart = []
if 'last_loan' not in st.session_state: st.session_state.last_loan = None
if 'edit_idx' not in st.session_state: st.session_state.edit_idx = None
if 'debug_log' not in st.session_state: st.session_state.debug_log = []

def add_log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.debug_log.append(f"[{ts}] {msg}")

# --- 2. DATAHANTERING ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_fresh_data():
    try:
        df = conn.read(worksheet="Sheet1", ttl=0)
        needed = ["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", 
                  "Streckkod", "Status", "Aktuell ägare", "Utlåningsdatum", "Senast inventerad"]
        for c in needed:
            if c not in df.columns: df[c] = ""
        return df.fillna("")
    except Exception as e:
        add_log(f"Laddningsfel: {e}")
        return pd.DataFrame()

def sync_save(df):
    try:
        conn.update(worksheet="Sheet1", data=df.astype(str))
        st.cache_data.clear()
        add_log("Data sparad till Sheets.")
        return True
    except Exception as e:
        add_log(f"Spara-fel: {e}")
        return False

# Ladda data om den inte finns
if 'df' not in st.session_state:
    st.session_state.df = get_fresh_data()

# --- 3. HJÄLPFUNKTIONER ---
def generate_id(): return f"{datetime.now().strftime('%y%m%d')}-{random.randint(100, 999)}"

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

# --- 4. SIDEBAR ---
st.sidebar.title("🎸 Musik-IT Birka v8")
pwd = st.sidebar.text_input("Admin lösenord", type="password")
is_admin = (pwd == "Birka")

if st.sidebar.button("🔄 Uppdatera lista"):
    st.session_state.df = get_fresh_data()
    st.rerun()

# Varukorg
if st.session_state.cart:
    with st.sidebar.expander("🛒 VARUKORG", expanded=True):
        for itm in st.session_state.cart:
            st.caption(f"• {itm['Modell']}")
        name = st.text_input("Vem lånar? *")
        if st.button("BEKRÄFTA UTLÅNING", type="primary"):
            if name:
                df = get_fresh_data()
                today = datetime.now().strftime("%Y-%m-%d")
                for itm in st.session_state.cart:
                    idx = df[df['Resurstagg'] == itm['Resurstagg']].index
                    df.loc[idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', name, today]
                if sync_save(df):
                    st.session_state.last_loan = {"name": name, "date": today, "items": st.session_state.cart.copy()}
                    st.session_state.cart = []; st.session_state.df = df; st.rerun()
            else: st.error("Namn krävs!")

# --- 5. MENY ---
menu = st.sidebar.selectbox("Meny", ["🔍 Sök & Skanna", "➕ Ny produkt", "🔄 Återlämning", "⚙️ Admin"])

# --- 6. SÖK & SKANNA ---
if menu == "🔍 Sök & Skanna":
    if st.session_state.last_loan:
        l = st.session_state.last_loan
        rows = "".join([f"<li>{i['Modell']}</li>" for i in l['items']])
        st.components.v1.html(f"<div style='border:2px solid #333; padding:10px;'><h3>Lånekvitto: {l['name']}</h3><ul>{rows}</ul><button onclick='window.print()'>SKRIV UT</button></div>", height=250)
        if st.button("Stäng kvitto"): st.session_state.last_loan = None; st.rerun()

    q = st.text_input("Sök i registret", value=st.query_params.get("q", ""))
    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)] if q else st.session_state.df

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if row['Enhetsfoto']: st.image(row['Enhetsfoto'], width=100)
                st.image(f"data:image/png;base64,{get_qr_b64(row['Resurstagg'])}", width=60)
            with c2:
                st.subheader(row['Modell'])
                st.write(f"ID: {row['Resurstagg']} | Status: {row['Status']}")
                if row['Status'] == 'Utlånad': st.error(f"Hos: {row['Aktuell ägare']}")
            with c3:
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒 Lägg till", key=f"a{idx}"):
                        st.session_state.cart.append(row.to_dict()); st.rerun()
                if is_admin:
                    if st.button("✏️ Edit", key=f"e{idx}"):
                        st.session_state.edit_idx = idx; st.rerun()

    # Editering
    if is_admin and st.session_state.edit_idx is not None:
        idx = st.session_state.edit_idx
        with st.form("edit"):
            e_mod = st.text_input("Modell", value=st.session_state.df.loc[idx, 'Modell'])
            e_img = st.file_uploader("Byt bild")
            if st.form_submit_button("Spara"):
                df = get_fresh_data()
                df.at[idx, 'Modell'] = e_mod
                if e_img: df.at[idx, 'Enhetsfoto'] = img_to_b64(e_img)
                sync_save(df); st.session_state.edit_idx = None; st.rerun()

# --- 7. NY PRODUKT ---
elif menu == "➕ Ny produkt":
    with st.form("new", clear_on_submit=True):
        st.subheader("Registrera ny utrustning")
        c1, c2 = st.columns(2)
        f_mod = c1.text_input("Modell *")
        f_brand = c1.text_input("Tillverkare")
        f_typ = c1.text_input("Typ")
        f_farg = c1.text_input("Färg")
        f_tag = c2.text_input("ID (Lämna tom för auto)")
        f_bc = c2.text_input("Streckkod")
        f_status = c2.selectbox("Status", ["Tillgänglig", "Service"])
        f_foto = st.camera_input("Ta foto")
        if st.form_submit_button("Spara"):
            if f_mod:
                df = get_fresh_data()
                new = {"Modell": f_mod, "Tillverkare": f_brand, "Typ": f_typ, "Färg": f_farg, 
                       "Resurstagg": f_tag if f_tag else generate_id(), "Streckkod": f_bc, 
                       "Status": f_status, "Enhetsfoto": img_to_b64(f_foto) if f_foto else "",
                       "Senast inventerad": datetime.now().strftime("%Y-%m-%d")}
                df = pd.concat([df, pd.DataFrame([new])], ignore_index=True)
                sync_save(df); st.rerun()

# --- 8. ÅTERLÄMNING (INDIVIDUELL BEKRÄFTELSE) ---
elif menu == "🔄 Återlämning":
    st.header("Bekräfta återlämning")
    borrowed = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    
    if borrowed.empty:
        st.info("Inga produkter är utlånade.")
    else:
        owners = borrowed['Aktuell ägare'].unique()
        sel_owner = st.selectbox("Välj låntagare för att visa produkter", ["---"] + list(owners))
        
        if sel_owner != "---":
            st.write(f"### Aktiva lån för: {sel_owner}")
            items = borrowed[borrowed['Aktuell ägare'] == sel_owner]
            
            for idx, row in items.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.write(f"📦 **{row['Modell']}** (ID: {row['Resurstagg']})")
                    c1.caption(f"Lånades: {row['Utlåningsdatum']}")
                    # Här sker den individuella bekräftelsen
                    if c2.button("✅ Bekräfta", key=f"ret_{idx}"):
                        df = get_fresh_data()
                        # Vi hittar produkten via ID för säkerhet
                        p_idx = df[df['Resurstagg'] == row['Resurstagg']].index
                        df.loc[p_idx, ['Status', 'Aktuell ägare', 'Utlåningsdatum', 'Senast inventerad']] = \
                            ['Tillgänglig', '', '', datetime.now().strftime("%Y-%m-%d")]
                        if sync_save(df):
                            st.toast(f"{row['Modell']} återlämnad!")
                            st.session_state.df = df
                            st.rerun()

# --- 9. ADMIN ---
elif menu == "⚙️ Admin":
    if is_admin:
        t1, t2, t3 = st.tabs(["Inventering", "QR-Bulk", "Systemlogg"])
        with t1:
            st.write("### Inventering")
            st.dataframe(st.session_state.df[['Modell', 'Resurstagg', 'Senast inventerad']])
        with t2:
            st.write("Etiketter 3x4 cm")
            sel = st.multiselect("Välj", st.session_state.df['Modell'].tolist())
            if sel:
                html = "<div style='display:flex; flex-wrap:wrap; gap:5px;'>"
                for m in sel:
                    r = st.session_state.df[st.session_state.df['Modell'] == m].iloc[0]
                    qr = get_qr_b64(r['Resurstagg'])
                    html += f"<div style='width:3cm; height:4cm; border:1px solid #ccc; text-align:center;'><img src='data:image/png;base64,{qr}' width='80'><br><small>{r['Modell']}</small></div>"
                st.components.v1.html(html + "</div><br><button onclick='window.print()'>Print</button>", height=400)
        with t3:
            for l in reversed(st.session_state.debug_log): st.text(l)

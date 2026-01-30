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
if 'error_log' not in st.session_state: st.session_state.error_log = []
if 'editing_item' not in st.session_state: st.session_state.editing_item = None
if 'cart' not in st.session_state: st.session_state.cart = []
if 'inv_scanned' not in st.session_state: st.session_state.inv_scanned = []

# --- HJÄLPFUNKTIONER ---
def process_image_to_base64(image_file):
    try:
        img = Image.open(image_file)
        img.thumbnail((250, 250)) 
        buffered = BytesIO()
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.save(buffered, format="JPEG", quality=60)
        return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"
    except Exception as e:
        return ""

def generate_qr(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def get_label_html(modell, tag):
    qr_b64 = base64.b64encode(generate_qr(str(tag))).decode()
    return f"""
    <div style="width: 3.8cm; height: 2.8cm; border: 1px solid #000; padding: 5px; text-align: center; font-family: Arial, sans-serif; background-color: white; color: black; margin: 10px auto;">
        <img src="data:image/png;base64,{qr_b64}" style="width: 1.8cm;"><br>
        <div style="font-size: 12px; font-weight: bold; margin-top: 2px; line-height: 1.1;">{modell[:25]}</div>
        <div style="font-size: 10px; margin-top: 2px;">ID: {tag}</div>
    </div>
    <div style="text-align: center;">
        <button onclick="window.print()" style="padding: 5px 10px; cursor: pointer;">Skriv ut etikett</button>
    </div>
    """

# --- ANSLUTNING ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        data = conn.read(worksheet="Sheet1", ttl=0)
        return data.fillna("")
    except:
        return pd.DataFrame(columns=["Enhetsfoto", "Modell", "Tillverkare", "Typ", "Färg", "Resurstagg", "Streckkod", "Serienummer", "Status", "Aktuell ägare", "Utlåningsdatum"])

def save_data(df):
    conn.update(worksheet="Sheet1", data=df.fillna("").astype(str))
    st.cache_data.clear()
    return True

# Initial laddning
if 'df' not in st.session_state:
    st.session_state.df = load_data()

# --- SIDOMENY (INKL. VARUKORG) ---
st.sidebar.title("🎸 Musik-IT")
menu = st.sidebar.selectbox("Navigering", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "⚙️ Admin & Inventering"])

# VARUKORG I SIDOMENY
if st.session_state.cart:
    st.sidebar.divider()
    st.sidebar.subheader("🛒 Varukorg")
    for i, item in enumerate(st.session_state.cart):
        st.sidebar.caption(f"{item['Modell']} ({item['Resurstagg']})")
    
    if st.sidebar.button("Rensa korgen"):
        st.session_state.cart = []
        st.rerun()
        
    borrower = st.sidebar.text_input("Vem lånar? (Tvingande) *", key="borrower_name")
    
    # Knapp som bara fungerar om namn är ifyllt
    if borrower:
        if st.sidebar.button("Bekräfta utlån ✅", type="primary"):
            today = datetime.now().strftime("%Y-%m-%d")
            for item in st.session_state.cart:
                # Uppdatera rader i huvud-dataframe
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 
                                        ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, today]
            
            if save_data(st.session_state.df):
                st.balloons()
                st.session_state.cart = []
                st.sidebar.success(f"Lån registrerat på {borrower}!")
                st.rerun()
    else:
        st.sidebar.warning("Fyll i namn för att bekräfta lån.")

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    with st.expander("📷 Snabb-skanna QR (Sök)"):
        st.camera_input("Skanna en kod för att filtrera")

    # REDIGERING
    if st.session_state.editing_item is not None:
        idx = st.session_state.editing_item
        item = st.session_state.df.iloc[idx]
        with st.container(border=True):
            st.subheader(f"Editera: {item['Modell']}")
            col_edit, col_print = st.columns([2, 1])
            with col_edit:
                with st.form("edit_form"):
                    e_mod = st.text_input("Modell", value=item['Modell'])
                    e_till = st.text_input("Tillverkare", value=item['Tillverkare'])
                    e_stat = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service"], index=0)
                    new_img = st.camera_input("Uppdatera bild")
                    if st.form_submit_button("Spara"):
                        st.session_state.df.at[idx, 'Modell'] = e_mod
                        st.session_state.df.at[idx, 'Tillverkare'] = e_till
                        st.session_state.df.at[idx, 'Status'] = e_stat
                        if new_img: st.session_state.df.at[idx, 'Enhetsfoto'] = process_image_to_base64(new_img)
                        save_data(st.session_state.df)
                        st.session_state.editing_item = None
                        st.rerun()
            with col_print:
                st.components.v1.html(get_label_html(item['Modell'], item['Resurstagg']), height=280)
                if st.button("Radera produkt", type="secondary"):
                    st.session_state.df = st.session_state.df.drop(st.session_state.df.index[idx]).reset_index(drop=True)
                    save_data(st.session_state.df)
                    st.session_state.editing_item = None
                    st.rerun()

    # SÖKLISTA
    query = st.text_input("Sök i lagret...")
    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)]

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
            with c1:
                if str(row['Enhetsfoto']).startswith("data:image"): st.image(row['Enhetsfoto'], width=90)
                else: st.write("📷")
            with c2:
                st.write(f"**{row['Modell']}**")
                st.caption(f"{row['Tillverkare']} | SN: {row['Serienummer']}")
            with c3:
                st.image(generate_qr(str(row['Resurstagg'])), width=65)
                st.caption(f"ID: {row['Resurstagg']}")
            with c4:
                st.write(f"Status: **{row['Status']}**")
                if row['Status'] == 'Tillgänglig':
                    # Hindra att man lägger till samma sak två gånger i korgen
                    if any(item['Resurstagg'] == row['Resurstagg'] for item in st.session_state.cart):
                        st.info("I korgen")
                    elif st.button("🛒 Lägg i korg", key=f"add_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.rerun()
                if st.button("✏️ Edit/Print", key=f"ed_{idx}"):
                    st.session_state.editing_item = idx
                    st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.header("Registrera nytt instrument")
    with st.form("reg"):
        c1, c2 = st.columns(2)
        m = c1.text_input("Modell *")
        s = c2.text_input("Serienummer *")
        t = c1.text_input("Tillverkare")
        ty = c2.selectbox("Typ", ["Gitarr", "Bas", "Trummor", "Keyboard", "PA", "Kabel", "Övrigt"])
        tag_in = st.text_input("ID (Lämna tom för auto)")
        foto = st.camera_input("Foto")
        if st.form_submit_button("Spara"):
            if m and s:
                rid = tag_in if tag_in else str(random.randint(100000, 999999))
                new_row = {
                    "Enhetsfoto": process_image_to_base64(foto) if foto else "", "Modell": m, "Serienummer": s, 
                    "Tillverkare": t, "Typ": ty, "Resurstagg": rid, "Status": "Tillgänglig", 
                    "Aktuell ägare": "", "Utlåningsdatum": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.success(f"Skapad: {rid}")
            else: st.error("Fyll i obligatoriska fält!")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        sel = st.multiselect("Välj instrument att återlämna:", loaned.apply(lambda r: f"{r['Modell']} [{r['Resurstagg']}] - Lånad av: {r['Aktuell ägare']}", axis=1))
        if st.button("Checka in valda"):
            for s in sel:
                tid = s.split("[")[1].split("]")[0]
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == tid, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
            save_data(st.session_state.df)
            st.rerun()
    else:
        st.info("Inga instrument är utlånade just nu.")

# --- VY: ADMIN ---
elif menu == "⚙️ Admin & Inventering":
    st.header("Admin")
    t1, t2 = st.tabs(["📊 Lagerstatus", "📋 Inventering"])
    with t1:
        st.download_button("Exportera CSV", st.session_state.df.to_csv(index=False).encode('utf-8'), "lager.csv")
        st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"]))
    with t2:
        st.subheader("Inventeringsläge")
        inv_id = st.text_input("Skanna för avprickning:")
        if inv_id and inv_id in st.session_state.df['Resurstagg'].values:
            if inv_id not in st.session_state.inv_scanned:
                st.session_state.inv_scanned.append(inv_id)
                st.success(f"Hittad: {inv_id}")
        if st.button("Visa saknade"):
            missing = st.session_state.df[~st.session_state.df['Resurstagg'].isin(st.session_state.inv_scanned)]
            st.warning(f"{len(missing)} produkter saknas.")
            st.table(missing[['Modell', 'Resurstagg']])

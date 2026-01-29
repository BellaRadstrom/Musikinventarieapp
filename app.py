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

def add_log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.error_log.append(f"[{timestamp}] {msg}")

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
        add_log(f"Bildfel: {e}")
        return ""

def generate_qr(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

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

if 'df' not in st.session_state:
    st.session_state.df = load_data()

# --- SIDOMENY ---
st.sidebar.title("🎸 Musik-IT")
menu = st.sidebar.selectbox("Navigering", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "⚙️ Admin & Inventering"])

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    # 1. Kameraskanning för Sök
    with st.expander("📷 Skanna QR-kod för sökning"):
        cam_search = st.camera_input("Rikta kameran mot produktens QR-kod")
        if cam_search:
            st.info("Kameran är aktiv. För full QR-avkodning i webbläsaren, skriv in ID nedan.")

    # 2. Redigeringsvy (Om aktiv)
    if st.session_state.editing_item is not None:
        idx = st.session_state.editing_item
        item = st.session_state.df.iloc[idx]
        with st.status(f"Redigerar: {item['Modell']}", expanded=True):
            with st.form("edit_product"):
                col_a, col_b = st.columns(2)
                e_mod = col_a.text_input("Modell", value=item['Modell'])
                e_till = col_b.text_input("Tillverkare", value=item['Tillverkare'])
                e_stat = col_a.selectbox("Status", ["Tillgänglig", "Utlånad", "Service"], index=0)
                
                st.write("---")
                st.write("📸 **Uppdatera eller lägg till bild**")
                new_img = st.camera_input("Ta nytt foto för att ersätta nuvarande")
                
                if st.form_submit_button("Spara ändringar"):
                    st.session_state.df.at[idx, 'Modell'] = e_mod
                    st.session_state.df.at[idx, 'Tillverkare'] = e_till
                    st.session_state.df.at[idx, 'Status'] = e_stat
                    if new_img:
                        st.session_state.df.at[idx, 'Enhetsfoto'] = process_image_to_base64(new_img)
                    save_data(st.session_state.df)
                    st.success("Ändringar sparade!")
                    st.session_state.editing_item = None
                    st.rerun()
            
            if st.button("🗑️ Radera produkt permanent", type="secondary"):
                st.session_state.df = st.session_state.df.drop(st.session_state.df.index[idx]).reset_index(drop=True)
                save_data(st.session_state.df)
                st.session_state.editing_item = None
                st.rerun()

    # 3. Söklista
    query = st.text_input("Sök på modell, serienummer eller ID...")
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
                if row['Status'] == 'Tillgänglig' and st.button("🛒 Låna", key=f"l_{idx}"):
                    st.session_state.cart.append(row.to_dict())
                    st.toast("Tillagd!")
                if st.button("✏️ Edit", key=f"e_{idx}"):
                    st.session_state.editing_item = idx
                    st.rerun()

    # Utcheckning Sidebar
    if st.session_state.cart:
        st.sidebar.divider()
        borrower = st.sidebar.text_input("Vem lånar?")
        if st.sidebar.button("Bekräfta utlån", type="primary"):
            if borrower:
                for item in st.session_state.cart:
                    st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, datetime.now().strftime("%Y-%m-%d")]
                save_data(st.session_state.df)
                st.balloons()
                st.session_state.cart = []
                st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.header("Ny registrering")
    with st.form("new_reg"):
        c1, c2 = st.columns(2)
        m = c1.text_input("Modell *")
        s = c2.text_input("Serienummer *")
        t = c1.text_input("Tillverkare")
        ty = c2.selectbox("Typ", ["Gitarr", "Bas", "Trummor", "Keyboard", "PA", "Kabel", "Övrigt"])
        tag_in = st.text_input("Eget ID (lämna tom för auto)")
        foto = st.camera_input("Ta produktfoto")
        
        if st.form_submit_button("Skapa Produkt"):
            if m and s:
                rid = tag_in if tag_in else str(random.randint(100000, 999999))
                new_data = {
                    "Enhetsfoto": process_image_to_base64(foto) if foto else "",
                    "Modell": m, "Serienummer": s, "Tillverkare": t, "Typ": ty,
                    "Resurstagg": rid, "Status": "Tillgänglig", "Aktuell ägare": "", "Utlåningsdatum": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
                save_data(st.session_state.df)
                st.balloons()
                st.success(f"Sparad med ID: {rid}")
            else: st.error("Fyll i Modell och Serienummer!")

# --- VY: ADMIN & INVENTERING ---
elif menu == "⚙️ Admin & Inventering":
    st.header("Admin")
    t1, t2, t3 = st.tabs(["📊 Data & Export", "📋 Inventering", "🏷️ Etiketter"])
    
    with t1:
        st.download_button("📥 Exportera CSV", st.session_state.df.to_csv(index=False).encode('utf-8'), "lager.csv")
        st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"], errors="ignore"))

    with t2:
        st.subheader("Inventeringsläge")
        inv_id = st.text_input("Skanna QR / Skriv ID:")
        if inv_id and inv_id in st.session_state.df['Resurstagg'].values:
            if inv_id not in st.session_state.inv_scanned:
                st.session_state.inv_scanned.append(inv_id)
                st.success(f"Check: {inv_id}")
        
        if st.button("Kör Avvikelseanalys"):
            missing = st.session_state.df[~st.session_state.df['Resurstagg'].isin(st.session_state.inv_scanned)]
            if not missing.empty:
                st.error(f"Avvikelse! {len(missing)} objekt saknas.")
                st.table(missing[['Modell', 'Resurstagg', 'Status']])
            else: st.success("Inventering OK! Allt på plats.")

    with t3:
        st.subheader("Etikett-utskrift (3x4 cm)")
        if st.button("Generera ark"):
            html = "<div style='display: grid; grid-template-columns: repeat(auto-fill, 4cm); gap: 10px;'>"
            for _, r in st.session_state.df.iterrows():
                q = base64.b64encode(generate_qr(str(r['Resurstagg']))).decode()
                html += f"""
                <div style="width: 3.8cm; height: 2.8cm; border: 1px solid #000; padding: 5px; text-align: center; font-family: sans-serif; font-size: 10px;">
                    <img src="data:image/png;base64,{q}" style="width: 1.8cm;"><br>
                    <b>{r['Modell'][:18]}</b><br>{r['Resurstagg']}
                </div>"""
            html += "</div>"
            st.components.v1.html(html, height=800, scrolling=True)

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    sel = st.multiselect("Välj objekt:", loaned.apply(lambda r: f"{r['Modell']} [{r['Resurstagg']}]", axis=1))
    if st.button("Återlämna valda"):
        for s in sel:
            tid = s.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tid, ['Status', 'Aktuell ägare']] = ['Tillgänglig', '']
        save_data(st.session_state.df)
        st.rerun()

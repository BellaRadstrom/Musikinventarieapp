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
    
    if st.session_state.editing_item is not None:
        idx = st.session_state.editing_item
        item = st.session_state.df.iloc[idx]
        with st.expander("Redigera produkt", expanded=True):
            with st.form("edit"):
                e_mod = st.text_input("Modell", value=item['Modell'])
                e_stat = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service"], index=0)
                if st.form_submit_button("Spara"):
                    st.session_state.df.at[idx, 'Modell'] = e_mod
                    st.session_state.df.at[idx, 'Status'] = e_stat
                    save_data(st.session_state.df)
                    st.session_state.editing_item = None
                    st.rerun()
            if st.button("🗑️ Radera permanent"):
                st.session_state.df = st.session_state.df.drop(st.session_state.df.index[idx]).reset_index(drop=True)
                save_data(st.session_state.df)
                st.session_state.editing_item = None
                st.rerun()

    query = st.text_input("Sök i lagret...")
    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)]

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
            with c1:
                if str(row['Enhetsfoto']).startswith("data:image"): st.image(row['Enhetsfoto'], width=80)
                else: st.write("📷")
            with c2:
                st.write(f"**{row['Modell']}**")
                st.caption(f"SN: {row['Serienummer']}")
            with c3:
                st.image(generate_qr(str(row['Resurstagg'])), width=60)
                st.caption(row['Resurstagg'])
            with c4:
                if row['Status'] == 'Tillgänglig' and st.button("🛒 Låna", key=f"l_{idx}"):
                    st.session_state.cart.append(row.to_dict())
                if st.button("✏️ Edit", key=f"e_{idx}"):
                    st.session_state.editing_item = idx
                    st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.header("Ny produkt")
    with st.form("reg"):
        c1, c2 = st.columns(2)
        mod = c1.text_input("Modell *")
        sn = c2.text_input("Serienummer *")
        till = c1.text_input("Tillverkare")
        typ = c2.selectbox("Typ", ["Gitarr", "Bas", "Trummor", "Keyboard", "Övrigt"])
        tag = st.text_input("ID (lämna tom för auto)")
        img = st.camera_input("Foto")
        if st.form_submit_button("Spara"):
            if mod and sn:
                rid = tag if tag else str(random.randint(1000, 9999))
                new_row = {"Enhetsfoto": process_image_to_base64(img) if img else "", "Modell": mod, "Serienummer": sn, "Tillverkare": till, "Typ": typ, "Resurstagg": rid, "Status": "Tillgänglig"}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.balloons()
            else: st.error("Fyll i obligatoriska fält!")

# --- VY: ADMIN & INVENTERING ---
elif menu == "⚙️ Admin & Inventering":
    st.header("Administration & Inventering")
    
    tabs = st.tabs(["📊 Lagersaldo & Export", "📋 Inventeringsläge", "🏷️ Etikett-utskrift"])
    
    with tabs[0]:
        st.subheader("Exporter")
        csv = st.session_state.df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Ladda ner hela lagersaldot (CSV)", csv, "lagersaldo.csv", "text/csv")
        st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"], errors="ignore"))

    with tabs[1]:
        st.subheader("Starta Inventering")
        inv_input = st.text_input("Skanna QR-kod / Skriv ID för att checka av:")
        if inv_input:
            if inv_input in st.session_state.df['Resurstagg'].values:
                if inv_input not in st.session_state.inv_scanned:
                    st.session_state.inv_scanned.append(inv_input)
                    st.success(f"Incheckad: {inv_input}")
            else: st.warning("ID finns inte i systemet.")
        
        st.write(f"Antal skannade: {len(st.session_state.inv_scanned)} av {len(st.session_state.df)}")
        
        if st.button("Slutför Inventering & Visa Avvikelser"):
            missing = st.session_state.df[~st.session_state.df['Resurstagg'].isin(st.session_state.inv_scanned)]
            if not missing.empty:
                st.error(f"AVVIKELSE: {len(missing)} produkter saknas!")
                st.table(missing[['Modell', 'Resurstagg', 'Status']])
            else:
                st.success("Allt i lager! Ingen avvikelse.")

    with tabs[2]:
        st.subheader("Generera Etiketter (3x4 cm)")
        st.info("Detta skapar ett ark med QR-koder och text anpassat för utskrift.")
        if st.button("Skapa PDF-ark för utskrift"):
            html = "<div style='display: flex; flex-wrap: wrap;'>"
            for _, r in st.session_state.df.iterrows():
                qr_b64 = base64.b64encode(generate_qr(str(r['Resurstagg']))).decode()
                html += f"""
                <div style="width: 3.8cm; height: 2.8cm; border: 1px solid #ccc; padding: 2px; margin: 2px; text-align: center; font-family: Arial; font-size: 10px;">
                    <img src="data:image/png;base64,{qr_b64}" style="width: 1.8cm;"><br>
                    <b>{r['Modell'][:15]}</b><br>{r['Resurstagg']}
                </div>
                """
            html += "</div>"
            st.components.v1.html(html, height=600, scrolling=True)

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    sel = st.multiselect("Välj instrument:", loaned.apply(lambda r: f"{r['Modell']} [{r['Resurstagg']}]", axis=1))
    if st.button("Återlämna"):
        for s in sel:
            tid = s.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tid, ['Status', 'Aktuell ägare']] = ['Tillgänglig', '']
        save_data(st.session_state.df)
        st.rerun()

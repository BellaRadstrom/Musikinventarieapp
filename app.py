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
if 'editing_item' not in st.session_state: st.session_state.editing_item = None
if 'cart' not in st.session_state: st.session_state.cart = []
if 'inv_scanned' not in st.session_state: st.session_state.inv_scanned = []
if 'last_checkout' not in st.session_state: st.session_state.last_checkout = None

# --- HJÄLPFUNKTIONER ---
def process_image_to_base64(image_file):
    try:
        img = Image.open(image_file)
        img.thumbnail((250, 250)) 
        buffered = BytesIO()
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.save(buffered, format="JPEG", quality=60)
        return f"data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}"
    except:
        return ""

def generate_qr(data):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def get_label_html(items):
    # Genererar HTML för en eller flera etiketter (3x4 cm format)
    html = "<div style='display: flex; flex-wrap: wrap; gap: 10px; justify-content: center;'>"
    for item in items:
        qr_b64 = base64.b64encode(generate_qr(str(item['Resurstagg']))).decode()
        html += f"""
        <div style="width: 3.8cm; height: 2.8cm; border: 1px solid #000; padding: 5px; text-align: center; font-family: Arial, sans-serif; background-color: white; color: black;">
            <img src="data:image/png;base64,{qr_b64}" style="width: 1.6cm;"><br>
            <div style="font-size: 11px; font-weight: bold; margin-top: 2px;">{item['Modell'][:22]}</div>
            <div style="font-size: 9px;">ID: {item['Resurstagg']}</div>
        </div>
        """
    html += "</div><div style='text-align:center; margin-top:20px;'><button onclick='window.print()'>Skriv ut valda etiketter</button></div>"
    return html

def get_packing_list_html(borrower, items):
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    list_items = "".join([f"<li>{item['Modell']} (SN: {item['Serienummer']})</li>" for item in items])
    return f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #ccc; background: white; color: black;">
        <h2>📦 Packlista / Lånekvitto</h2>
        <p><b>Låntagare:</b> {borrower}</p>
        <p><b>Datum:</b> {date_str}</p>
        <hr>
        <ul>{list_items}</ul>
        <p style="margin-top:20px; font-size: 0.8em;"><i>Vänligen lämna tillbaka utrustningen i samma skick som vid utlåning.</i></p>
        <button onclick="window.print()">Skriv ut packlista</button>
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

if 'df' not in st.session_state:
    st.session_state.df = load_data()

# --- SIDOMENY ---
st.sidebar.title("🎸 Musik-IT")
menu = st.sidebar.selectbox("Navigering", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "⚙️ Admin & Inventering"])

# VARUKORG & PACKLISTA
if st.session_state.cart:
    st.sidebar.divider()
    st.sidebar.subheader("🛒 Varukorg")
    for item in st.session_state.cart:
        st.sidebar.caption(f"• {item['Modell']}")
    
    borrower = st.sidebar.text_input("Vem lånar? *")
    if borrower:
        if st.sidebar.button("Bekräfta utlån ✅", type="primary"):
            today = datetime.now().strftime("%Y-%m-%d")
            # Spara kopia för packlistan innan vi rensar korgen
            st.session_state.last_checkout = {"borrower": borrower, "items": list(st.session_state.cart)}
            
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 
                                        ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower, today]
            
            if save_data(st.session_state.df):
                st.session_state.cart = []
                st.rerun()

if st.session_state.last_checkout:
    with st.sidebar.expander("📄 Senaste packlista", expanded=True):
        if st.button("Visa packlista för utskrift"):
            st.components.v1.html(get_packing_list_html(st.session_state.last_checkout['borrower'], st.session_state.last_checkout['items']), height=400)
        if st.button("Stäng packlista"):
            st.session_state.last_checkout = None
            st.rerun()

# --- VY: SÖK & LÅNA ---
if menu == "🔍 Sök & Låna":
    st.header("Sök & Låna")
    
    # EDITERA
    if st.session_state.editing_item is not None:
        idx = st.session_state.editing_item
        item = st.session_state.df.iloc[idx]
        with st.container(border=True):
            col_e, col_p = st.columns([2, 1])
            with col_e:
                with st.form("edit"):
                    e_mod = st.text_input("Modell", value=item['Modell'])
                    e_stat = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service"], index=0)
                    if st.form_submit_button("Spara"):
                        st.session_state.df.at[idx, 'Modell'] = e_mod
                        st.session_state.df.at[idx, 'Status'] = e_stat
                        save_data(st.session_state.df)
                        st.session_state.editing_item = None
                        st.rerun()
            with col_p:
                st.components.v1.html(get_label_html([item.to_dict()]), height=250)
                if st.button("Avbryt"): 
                    st.session_state.editing_item = None
                    st.rerun()

    query = st.text_input("Sök i lager...")
    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)]

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
            with c1:
                if str(row['Enhetsfoto']).startswith("data:image"): st.image(row['Enhetsfoto'], width=80)
            with c2:
                st.write(f"**{row['Modell']}**")
                st.caption(f"ID: {row['Resurstagg']} | SN: {row['Serienummer']}")
            with c3:
                st.image(generate_qr(str(row['Resurstagg'])), width=60)
            with c4:
                if row['Status'] == 'Tillgänglig':
                    if st.button("🛒 Låna", key=f"l_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.rerun()
                if st.button("✏️ Edit", key=f"e_{idx}"):
                    st.session_state.editing_item = idx
                    st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.header("Ny produkt")
    with st.form("reg"):
        m = st.text_input("Modell *")
        s = st.text_input("Serienummer *")
        t = st.text_input("ID (Lämna tom för auto)")
        foto = st.camera_input("Foto")
        if st.form_submit_button("Spara"):
            if m and s:
                rid = t if t else str(random.randint(100000, 999999))
                new_row = {"Enhetsfoto": process_image_to_base64(foto) if foto else "", "Modell": m, "Serienummer": s, "Resurstagg": rid, "Status": "Tillgänglig"}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.success(f"Skapad: {rid}")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    sel = st.multiselect("Välj instrument:", loaned.apply(lambda r: f"{r['Modell']} [{r['Resurstagg']}]", axis=1))
    if st.button("Checka in"):
        for s in sel:
            tid = s.split("[")[1].split("]")[0]
            st.session_state.df.loc[st.session_state.df['Resurstagg'] == tid, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
        save_data(st.session_state.df)
        st.rerun()

# --- VY: ADMIN & INVENTERING ---
elif menu == "⚙️ Admin & Inventering":
    st.header("Admin")
    t1, t2, t3 = st.tabs(["📊 Data", "📋 Inventering", "🏷️ Bulk-etiketter"])
    
    with t1:
        st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"]))
    
    with t2:
        inv_id = st.text_input("Skanna QR:")
        if inv_id and inv_id in st.session_state.df['Resurstagg'].values:
            if inv_id not in st.session_state.inv_scanned:
                st.session_state.inv_scanned.append(inv_id)
                st.success(f"OK: {inv_id}")
        if st.button("Kör analys"):
            missing = st.session_state.df[~st.session_state.df['Resurstagg'].isin(st.session_state.inv_scanned)]
            st.error(f"{len(missing)} saknas!")
            st.table(missing[['Modell', 'Resurstagg']])

    with t3:
        st.subheader("Massutskrift av etiketter")
        selected_labels = st.multiselect("Välj produkter för utskrift:", 
                                         st.session_state.df.apply(lambda r: f"{r['Modell']} ({r['Resurstagg']})", axis=1))
        if selected_labels:
            items_to_print = []
            for label in selected_labels:
                tag = label.split("(")[-1].replace(")", "")
                item_row = st.session_state.df[st.session_state.df['Resurstagg'] == tag].iloc[0]
                items_to_print.append(item_row.to_dict())
            
            if st.button("Generera valda etiketter"):
                st.components.v1.html(get_label_html(items_to_print), height=600, scrolling=True)

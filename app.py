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
    html = "<div style='display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-start;'>"
    for item in items:
        qr_b64 = base64.b64encode(generate_qr(str(item['Resurstagg']))).decode()
        html += f"""
        <div style="width: 3.8cm; height: 2.8cm; border: 1px solid #000; padding: 5px; text-align: center; font-family: Arial, sans-serif; background-color: white; color: black; margin-bottom: 5px;">
            <img src="data:image/png;base64,{qr_b64}" style="width: 1.6cm;"><br>
            <div style="font-size: 11px; font-weight: bold; margin-top: 2px;">{str(item['Modell'])[:22]}</div>
            <div style="font-size: 9px;">ID: {item['Resurstagg']}</div>
        </div>
        """
    html += "</div><div style='text-align:center; margin-top:20px;'><button onclick='window.print()'>Skriv ut dessa etiketter</button></div>"
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

# --- SIDOMENY (VARUKORG & NAVIGATION) ---
st.sidebar.title("🎸 Musik-IT")
menu = st.sidebar.selectbox("Navigering", ["🔍 Sök & Låna", "➕ Registrera Nytt", "🔄 Återlämning", "⚙️ Admin & Inventering"])

# VARUKORG LOGIK
if st.session_state.cart:
    st.sidebar.divider()
    st.sidebar.subheader("🛒 Varukorg")
    for item in st.session_state.cart:
        st.sidebar.caption(f"• {item['Modell']} ({item['Resurstagg']})")
    
    if st.sidebar.button("Töm korg"):
        st.session_state.cart = []
        st.rerun()
        
    borrower_name = st.sidebar.text_input("Vem lånar? (Tvingande) *", key="borrower_input")
    
    if borrower_name:
        if st.sidebar.button("Bekräfta utlån ✅", type="primary"):
            today = datetime.now().strftime("%Y-%m-%d")
            st.session_state.last_checkout = {"borrower": borrower_name, "items": list(st.session_state.cart)}
            
            for item in st.session_state.cart:
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == item['Resurstagg'], 
                                        ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Utlånad', borrower_name, today]
            
            if save_data(st.session_state.df):
                st.session_state.cart = []
                st.rerun()
    else:
        st.sidebar.warning("Skriv namn för att låna")

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
    
    # EDITERA PRODUKT
    if st.session_state.editing_item is not None:
        idx = st.session_state.editing_item
        item = st.session_state.df.iloc[idx]
        with st.container(border=True):
            col_e, col_p = st.columns([2, 1])
            with col_e:
                with st.form("edit_form"):
                    e_mod = st.text_input("Modell", value=item['Modell'])
                    e_stat = st.selectbox("Status", ["Tillgänglig", "Utlånad", "Service"], index=0)
                    new_img = st.camera_input("Ta nytt foto")
                    if st.form_submit_button("Spara ändringar"):
                        st.session_state.df.at[idx, 'Modell'] = e_mod
                        st.session_state.df.at[idx, 'Status'] = e_stat
                        if new_img: st.session_state.df.at[idx, 'Enhetsfoto'] = process_image_to_base64(new_img)
                        save_data(st.session_state.df)
                        st.session_state.editing_item = None
                        st.rerun()
            with col_p:
                st.write("🖨️ Snabbetikett")
                st.components.v1.html(get_label_html([item.to_dict()]), height=250)
                if st.button("Avbryt editering"): 
                    st.session_state.editing_item = None
                    st.rerun()

    query = st.text_input("Sök på modell, märke eller ID...")
    results = st.session_state.df[st.session_state.df.astype(str).apply(lambda x: x.str.contains(query, case=False)).any(axis=1)]

    for idx, row in results.iterrows():
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
            with c1:
                if str(row['Enhetsfoto']).startswith("data:image"): st.image(row['Enhetsfoto'], width=80)
                else: st.write("📷")
            with c2:
                st.write(f"**{row['Modell']}**")
                st.caption(f"ID: {row['Resurstagg']} | SN: {row['Serienummer']}")
            with c3:
                st.image(generate_qr(str(row['Resurstagg'])), width=60)
            with c4:
                if row['Status'] == 'Tillgänglig':
                    if any(item['Resurstagg'] == row['Resurstagg'] for item in st.session_state.cart):
                        st.info("I korgen")
                    elif st.button("🛒 Lägg i korg", key=f"cart_{idx}"):
                        st.session_state.cart.append(row.to_dict())
                        st.rerun()
                else:
                    st.write(f"🚫 {row['Status']}")
                
                if st.button("✏️ Edit", key=f"editbtn_{idx}"):
                    st.session_state.editing_item = idx
                    st.rerun()

# --- VY: REGISTRERA NYTT ---
elif menu == "➕ Registrera Nytt":
    st.header("Registrera nytt instrument")
    with st.form("new_reg"):
        m = st.text_input("Modell *")
        s = st.text_input("Serienummer *")
        t = st.text_input("Eget ID (Lämna tom för slumpat)")
        foto = st.camera_input("Produktfoto")
        if st.form_submit_button("Spara till lager"):
            if m and s:
                rid = t if t else str(random.randint(100000, 999999))
                new_row = {"Enhetsfoto": process_image_to_base64(foto) if foto else "", "Modell": m, "Serienummer": s, "Resurstagg": rid, "Status": "Tillgänglig"}
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                save_data(st.session_state.df)
                st.success(f"Registrerad med ID: {rid}")
            else: st.error("Modell och Serienummer krävs!")

# --- VY: ÅTERLÄMNING ---
elif menu == "🔄 Återlämning":
    st.header("Återlämning")
    loaned = st.session_state.df[st.session_state.df['Status'] == 'Utlånad']
    if not loaned.empty:
        sel = st.multiselect("Välj instrument att återlämna:", loaned.apply(lambda r: f"{r['Modell']} [{r['Resurstagg']}]", axis=1))
        if st.button("Checka in valda"):
            for s in sel:
                tid = s.split("[")[1].split("]")[0]
                st.session_state.df.loc[st.session_state.df['Resurstagg'] == tid, ['Status', 'Aktuell ägare', 'Utlåningsdatum']] = ['Tillgänglig', '', '']
            save_data(st.session_state.df)
            st.rerun()
    else:
        st.info("Inga instrument är utlånade just nu.")

# --- VY: ADMIN & INVENTERING ---
elif menu == "⚙️ Admin & Inventering":
    st.header("Administration")
    t1, t2, t3 = st.tabs(["📊 Lagerlista", "📋 Inventering", "🏷️ Bulk-utskrift"])
    
    with t1:
        st.dataframe(st.session_state.df.drop(columns=["Enhetsfoto"]))
    
    with t2:
        inv_id = st.text_input("Skanna QR för avprickning:")
        if inv_id and inv_id in st.session_state.df['Resurstagg'].values:
            if inv_id not in st.session_state.inv_scanned:
                st.session_state.inv_scanned.append(inv_id)
                st.success(f"Prickat av ID: {inv_id}")
        if st.button("Visa avvikelser"):
            missing = st.session_state.df[~st.session_state.df['Resurstagg'].isin(st.session_state.inv_scanned)]
            st.warning(f"{len(missing)} produkter saknas.")
            st.table(missing[['Modell', 'Resurstagg', 'Status']])

    with t3:
        st.subheader("Massutskrift av etiketter")
        # Skapar en lista där vi visar Modell + ID för tydlighet
        label_options = st.session_state.df.apply(lambda r: f"{r['Modell']} | ID:{r['Resurstagg']}", axis=1).tolist()
        selected_options = st.multiselect("Välj produkter för etikettutskrift:", label_options)
        
        if selected_options:
            items_to_print = []
            for opt in selected_options:
                # Extraherar ID:t som kommer efter "ID:"
                tag_id = opt.split("| ID:")[-1]
                match = st.session_state.df[st.session_state.df['Resurstagg'] == tag_id]
                if not match.empty:
                    items_to_print.append(match.iloc[0].to_dict())
            
            if items_to_print:
                if st.button("Generera och förbered utskrift"):
                    st.components.v1.html(get_label_html(items_to_print), height=600, scrolling=True)

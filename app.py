# --- VY: LÄGG TILL (Uppdaterad med kamerafunktion) ---
elif menu == "➕ Lägg till musikutrustning":
    st.title("Lägg till musikutrustning")
    st.write("Fyll i informationen nedan för att registrera en ny produkt i systemet.")
    
    with st.container():
        col1, col2 = st.columns(2)
        modell = col1.text_input("Modell *", placeholder="Ex. Stratocaster eller Mixerbord")
        tillverkare = col2.text_input("Tillverkare", placeholder="Ex. Fender eller Yamaha")
        typ = col1.text_input("Typ av utrustning", placeholder="Ex. Elgitarr eller Ljudkort")
        farg = col2.text_input("Färg / Utförande", placeholder="Ex. Sunburst eller Svart")
        
        col3, col4, col5 = st.columns(3)
        tagg = col3.text_input("Resurstagg (ID) *", placeholder="Ex. EQ-102")
        sn = col5.text_input("Serienummer", placeholder="Ex. SN-123456")
        
        st.write("---")
        st.subheader("Foto")
        
        # Välj mellan URL eller Kamera
        photo_mode = st.radio("Välj metod för foto:", ["Klistra in URL", "Ta bild med mobilkameran"], horizontal=True)
        
        foto_path = ""
        
        if photo_mode == "Klistra in URL":
            foto_path = st.text_input("Bild-URL", placeholder="https://...")
        else:
            cam_image = st.camera_input("Fota instrumentet")
            if cam_image:
                # I en enkel version sparar vi inte filen permanent på disk än, 
                # men vi kan visa den. För permanent lagring på GitHub krävs mer kod.
                st.image(cam_image, caption="Bild tagen!", width=200)
                # Som en enkel lösning kan vi använda en placeholder eller spara binärdatan
                foto_path = "Bild tagen via kamera" 

        if st.button("💾 Spara musikutrustning"):
            if modell and tagg:
                new_data = {
                    "Enhetsfoto": foto_path,
                    "Modell": modell,
                    "Tillverkare": tillverkare,
                    "Typ": typ,
                    "Färg": farg,
                    "Resurstagg": tagg,
                    "Streckkod": tagg,
                    "Serienummer": sn,
                    "Status": "Tillgänglig",
                    "Aktuell ägare": ""
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_data])], ignore_index=True)
                save_data(st.session_state.df)
                st.success("✅ Produkten har lagts till!")
                st.balloons()

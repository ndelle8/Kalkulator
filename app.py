# --- TAB 3: SKANOWANIE ---
with tab3:
    st.subheader("📸 Skanowanie tabeli grafiku")
    st.write("Wskazówka: Zrób zdjęcie prosto z góry, przy dobrym oświetleniu.")
    plik = st.file_uploader("Wgraj zdjęcie:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        img = Image.open(plik)
        # Poprawa orientacji zdjęcia (częsty problem z telefonami)
        img = ImageOps.exif_transpose(img)
        img.thumbnail((1200, 1200))
        st.image(img, width=400)
        
        if st.button("🚀 Rozpocznij analizę"):
            try:
                with st.spinner("Przetwarzam zdjęcie..."):
                    reader = load_ocr()
                    wyniki = reader.readtext(np.array(img))
                
                # DIAGNOSTYKA: Pokaż co widzi OCR (poprawione formatowanie)
                with st.expander("🔍 Zobacz co odczytał program (Diagnostyka)"):
                    for res in wyniki: 
                        # Używamy .2f dla liczb zmiennoprzecinkowych
                        st.write(f"Tekst: {res[1]} (Pewność: {res[2]:.2f})")

                # SZUKANIE KOLUMNY
                header_x = None
                for (bbox, tekst, prob) in wyniki:
                    t = tekst.lower()
                    # Szukamy nagłówka (bardziej odporne na błędy odczytu)
                    if any(x in t for x in ["ilo", "godz", "ilos", "god"]):
                        header_x = (bbox[0][0] + bbox[1][0]) / 2
                        st.success(f"📍 Znaleziono nagłówek: {tekst}")
                        break
                
                # Jeśli nie znalazł nagłówka, szukaj po prawej stronie (ok. 70% szerokości)
                if header_x is None:
                    st.warning("Nie znalazłem napisu 'Ilość godzin'. Próbuję analizować prawą stronę tabeli...")
                    img_width = np.array(img).shape[1]
                    header_x = img_width * 0.7 

                # ZBIERANIE DANYCH
                dni_godziny = []
                for (bbox, tekst, prob) in wyniki:
                    x_c = (bbox[0][0] + bbox[1][0]) / 2
                    y_c = (bbox[0][1] + bbox[2][1]) / 2
                    
                    # Czyścimy tekst - szukamy tylko cyfr
                    clean_txt = "".join(filter(str.isdigit, tekst))
                    if clean_txt:
                        val = int(clean_txt)
                        # Sprawdzamy czy liczba jest w pionie pod nagłówkiem (margines 100px)
                        if abs(x_c - header_x) < 100 and 1 <= val <= 24:
                            dni_godziny.append({'y': y_c, 'val': val})

                # Sortowanie i rozliczanie
                dni_godziny.sort(key=lambda x: x['y'])
                
                stats = {"std": 0.0, "nad": 0.0, "sob": 0.0, "nie": 0.0}
                pl_holidays = holidays.Poland(years=wybrany_rok)
                
                # Wyświetlenie odczytanych dni dla pewności
                with st.expander("📝 Wykaz wykrytych godzin (dzień po dniu)"):
                    for i, d in enumerate(dni_godziny[:31]):
                        dzien_nr = i + 1
                        h = float(d['val'])
                        curr_d = date(wybrany_rok, m_idx, dzien_nr)
                        
                        # Klasyfikacja
                        if curr_d.weekday() == 5: 
                            stats["sob"] += h
                            rodzaj = "Sobota"
                        elif curr_d.weekday() == 6 or curr_d in pl_holidays: 
                            stats["nie"] += h
                            rodzaj = "Niedziela/Święto"
                        else:
                            rodzaj = "Dzień roboczy"
                            if h > 8:
                                stats["std"] += 8
                                stats["nad"] += (h - 8)
                            else: 
                                stats["std"] += h
                        
                        st.write(f"Dzień {dzien_nr} ({curr_d}): {h}h -> {rodzaj}")

                # Zapis do sesji
                st.session_state['ocr_std'] = stats["std"]
                st.session_state['ocr_nad'] = stats["nad"]
                st.session_state['ocr_sob'] = stats["sob"]
                st.session_state['ocr_nie'] = stats["nie"]
                
                st.success("✅ Dane odczytane! Wartości zostały przesłane do zakładki 'Obliczenia'.")
                
                # Podsumowanie pod przyciskiem
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Standard", f"{stats['std']}h")
                c2.metric("Nadgodziny", f"{stats['nad']}h")
                c3.metric("Soboty", f"{stats['sob']}h")
                c4.metric("Nd/Święta", f"{stats['nie']}h")

            except Exception as e:
                st.error(f"Wystąpił błąd: {e}")

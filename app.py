import streamlit as st
import pandas as pd
import holidays
import calendar
import os
import numpy as np
import easyocr
import re
from datetime import datetime, date
from PIL import Image, ImageOps

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(page_title="Kalkulator Zarobków PRO", page_icon="💰", layout="wide")

@st.cache_resource
def load_ocr():
    # Inicjalizacja silnika OCR (bez GPU dla wersji Cloud)
    return easyocr.Reader(['pl'], gpu=False)

# --- 2. FUNKCJE POMOCNICZE ---
def get_working_hours_pl(year, month):
    pl_holidays = holidays.Poland(years=year)
    working_days = 0
    num_days = calendar.monthrange(year, month)[1]
    for day in range(1, num_days + 1):
        curr_date = date(year, month, day)
        if curr_date.weekday() < 5 and curr_date not in pl_holidays:
            working_days += 1
    return working_days * 8

# --- 3. BOCZNY PANEL (USTAWIENIA) ---
with st.sidebar:
    st.header("⚙️ Ustawienia")
    wybrany_rok = st.selectbox("Rok:", [2024, 2025, 2026], index=1)
    
    miesiace = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
                "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    wybrany_m_nazwa = st.selectbox("Miesiąc:", miesiace, index=datetime.now().month-1)
    m_idx = miesiace.index(wybrany_m_nazwa) + 1
    
    st.divider()
    stawka_podst = st.number_input("Stawka podstawowa (zł/h):", value=25.0)
    dodatek_nadg = st.number_input("Dodatek za nadgodzinę (+ zł):", value=30.0)

# --- 4. GŁÓWNY INTERFEJS ---
st.title("💰 Kalkulator Wypłaty z OCR")

# Definicja zakładek - to musi być przed "with tab3"
tab1, tab2, tab3 = st.tabs(["🧮 Obliczenia", "📊 Historia", "📸 Skanuj Grafik"])

# --- TAB 1: OBLICZENIA ---
with tab1:
    h_etat = get_working_hours_pl(wybrany_rok, m_idx)
    st.info(f"Wymiar czasu pracy w {wybrany_m_nazwa} {wybrany_rok}: **{h_etat}h**")
    
    # Pobieranie danych z sesji (jeśli skanowaliśmy zdjęcie)
    h_std_val = st.session_state.get('ocr_std', float(h_etat))
    h_nad_val = st.session_state.get('ocr_nad', 0.0)
    h_sob_val = st.session_state.get('ocr_sob', 0.0)
    h_nie_val = st.session_state.get('ocr_nie', 0.0)

    c1, c2 = st.columns(2)
    with c1:
        h_p = st.number_input("Godziny standardowe:", value=h_std_val)
        h_n = st.number_input("Nadgodziny:", value=h_nad_val)
    with c2:
        h_s = st.number_input("Soboty (+50%):", value=h_sob_val)
        h_ni = st.number_input("Niedziele (+100%):", value=h_nie_val)

    total = (h_p * stawka_podst) + (h_n * (stawka_podst + dodatek_nadg)) + \
            (h_s * stawka_podst * 1.5) + (h_ni * stawka_podst * 2.0)
    
    st.divider()
    st.metric("Suma do wypłaty (Brutto)", f"{total:,.2f} zł")

# --- TAB 2: HISTORIA ---
with tab2:
    st.subheader("Twoja Historia")
    st.info("Wgraj swój plik CSV, aby zobaczyć statystyki z poprzednich miesięcy.")
    # (Tutaj możesz dodać kod do obsługi CSV z poprzednich wersji)

# --- TAB 3: SKANOWANIE (Z POPRAWKĄ BŁĘDU :.2f) ---
with tab3:
    st.subheader("📸 Skanowanie grafiku")
    st.write(f"Skanuję dla: {wybrany_m_nazwa} {wybrany_rok}")
    
    plik_foto = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik_foto:
        img = Image.open(plik_foto)
        img = ImageOps.exif_transpose(img) # Poprawa orientacji
        img.thumbnail((1200, 1200)) # Oszczędność RAM
        st.image(img, caption="Podgląd zdjęcia", width=400)
        
        if st.button("🚀 Analizuj i przelicz"):
            try:
                with st.spinner("Przetwarzam zdjęcie..."):
                    reader = load_ocr()
                    wyniki_ocr = reader.readtext(np.array(img))

                # DIAGNOSTYKA
                with st.expander("🔍 Zobacz co widzi OCR"):
                    for res in wyniki_ocr: 
                        st.write(f"Tekst: {res[1]} (Pewność: {res[2]:.2f})")

                # SZUKANIE KOLUMNY
                header_x = None
                for (bbox, tekst, prob) in wyniki_ocr:
                    t = tekst.lower()
                    if any(x in t for x in ["ilo", "godz", "ilos", "god"]):
                        header_x = (bbox[0][0] + bbox[1][0]) / 2
                        st.success(f"📍 Znaleziono kolumnę: {tekst}")
                        break

                if header_x is None:
                    st.warning("Nie znalazłem nagłówka 'Ilość godzin'. Próbuję analizować prawą stronę...")
                    img_width = np.array(img).shape[1]
                    header_x = img_width * 0.7

                # ZBIERANIE LICZB
                data_points = []
                for (bbox, tekst, prob) in wyniki_ocr:
                    x_c = (bbox[0][0] + bbox[1][0]) / 2
                    y_c = (bbox[0][1] + bbox[2][1]) / 2
                    
                    clean_txt = "".join(filter(str.isdigit, tekst))
                    if clean_txt:
                        val = int(clean_txt)
                        if abs(x_c - header_x) < 100 and 1 <= val <= 24:
                            data_points.append({'y': y_c, 'val': val})

                data_points.sort(key=lambda x: x['y'])

                # ROZLICZANIE
                pl_holidays = holidays.Poland(years=wybrany_rok)
                stats = {"std": 0.0, "nad": 0.0, "sob": 0.0, "nie": 0.0}
                
                with st.expander("📝 Wykaz wykrytych dni"):
                    for i, d in enumerate(data_points[:31]):
                        dzien_nr = i + 1
                        h = float(d['val'])
                        curr_d = date(wybrany_rok, m_idx, dzien_nr)
                        
                        if curr_d.weekday() == 5: stats["sob"] += h
                        elif curr_d.weekday() == 6 or curr_d in pl_holidays: stats["nie"] += h
                        else:
                            if h > 8:
                                stats["std"] += 8; stats["nad"] += (h - 8)
                            else: stats["std"] += h
                        st.write(f"Dzień {dzien_nr}: {h}h")

                # Zapis do sesji, aby Tab 1 mógł odczytać dane
                st.session_state['ocr_std'] = stats["std"]
                st.session_state['ocr_nad'] = stats["nad"]
                st.session_state['ocr_sob'] = stats["sob"]
                st.session_state['ocr_nie'] = stats["nie"]

                st.success("✅ Gotowe! Wróć do zakładki 'Obliczenia'.")
                st.write(stats)

            except Exception as e:
                st.error(f"Błąd analizy: {e}")

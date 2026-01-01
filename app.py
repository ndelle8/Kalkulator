import streamlit as st
import pandas as pd
import holidays
import calendar
import os
import numpy as np
import easyocr
import re
from datetime import datetime, date
from PIL import Image

# --- KONFIGURACJA I INICJALIZACJA ---
st.set_page_config(page_title="Kalkulator Zarobków PRO", page_icon="💰", layout="wide")

@st.cache_resource
def load_ocr():
    # Model 'pl' jest wymagany do rozpoznawania polskich znaków
    return easyocr.Reader(['pl'], gpu=False) # gpu=False jest bezpieczniejsze na Streamlit Cloud

# --- FUNKCJE POMOCNICZE ---
def get_working_hours_pl(year, month):
    pl_holidays = holidays.Poland(years=year)
    working_days = 0
    num_days = calendar.monthrange(year, month)[1]
    for day in range(1, num_days + 1):
        curr_date = date(year, month, day)
        if curr_date.weekday() < 5 and curr_date not in pl_holidays:
            working_days += 1
    return working_days * 8

# --- BOCZNY PANEL ---
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

st.title("💰 Kalkulator Wypłaty")

tab1, tab2, tab3 = st.tabs(["🧮 Obliczenia", "📊 Historia", "📸 Skanuj Grafik"])

# --- TAB 1: OBLICZENIA ---
with tab1:
    h_etat = get_working_hours_pl(wybrany_rok, m_idx)
    st.info(f"Wymiar czasu pracy w {wybrany_m_nazwa} {wybrany_rok}: **{h_etat}h**")
    
    # Inicjalizacja wartości z OCR jeśli istnieją
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

# --- TAB 3: SKANOWANIE (POPRAWIONE) ---
with tab3:
    st.subheader("Automatyczna analiza zdjęcia")
    plik_foto = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik_foto:
        image = Image.open(plik_foto)
        # Zmniejszamy obraz, aby nie przepełnić pamięci RAM
        image.thumbnail((1000, 1000)) 
        st.image(image, caption="Podgląd zdjęcia", width=400)
        
        if st.button("🚀 Analizuj grafik"):
            try:
                with st.spinner("Uruchamiam silnik OCR..."):
                    reader = load_ocr()
                    img_array = np.array(image)
                    wyniki_ocr = reader.readtext(img_array)

                # 1. Szukamy kolumny "Ilość godzin"
                header_x = None
                for (bbox, tekst, prob) in wyniki_ocr:
                    t = tekst.lower()
                    if "ilo" in t or "godz" in t:
                        header_x = (bbox[0][0] + bbox[1][0]) / 2
                        st.write(f"✅ Znaleziono kolumnę: {tekst}")
                        break

                if header_x is None:
                    st.error("❌ Nie znalazłem nagłówka 'Ilość godzin'. Zrób wyraźniejsze zdjęcie górnej części tabeli.")
                else:
                    # 2. Zbieramy liczby pod nagłówkiem
                    data_points = []
                    for (bbox, tekst, prob) in wyniki_ocr:
                        # Szukamy cyfr, ale ignorujemy kreski i napisy
                        cyfry = "".join(filter(str.isdigit, tekst))
                        if cyfry:
                            liczba = int(cyfry)
                            x_center = (bbox[0][0] + bbox[1][0]) / 2
                            y_center = (bbox[0][1] + bbox[2][1]) / 2
                            
                            # Filtrujemy tylko to, co jest w kolumnie i jest sensowną liczbą godzin
                            if abs(x_center - header_x) < 70 and 1 <= liczba <= 24:
                                data_points.append({'y': y_center, 'val': liczba})

                    # Sortujemy od góry do dołu
                    data_points.sort(key=lambda x: x['y'])

                    # 3. Rozliczanie
                    pl_holidays = holidays.Poland(years=wybrany_rok)
                    dni_w_miesiacu = calendar.monthrange(wybrany_rok, m_idx)[1]
                    stats = {"std": 0.0, "nad": 0.0, "sob": 0.0, "nie": 0.0}

                    for i, p in enumerate(data_points[:dni_w_miesiacu]):
                        dzien = i + 1
                        h = float(p['val'])
                        curr_d = date(wybrany_rok, m_idx, dzien)
                        
                        if curr_d.weekday() == 5: stats["sob"] += h
                        elif curr_d.weekday() == 6 or curr_d in pl_holidays: stats["nie"] += h
                        else:
                            if h > 8:
                                stats["std"] += 8
                                stats["nad"] += (h - 8)
                            else: stats["std"] += h

                    # Zapisujemy do sesji, by Tab 1 mógł to odczytać
                    st.session_state['ocr_std'] = stats["std"]
                    st.session_state['ocr_nad'] = stats["nad"]
                    st.session_state['ocr_sob'] = stats["sob"]
                    st.session_state['ocr_nie'] = stats["nie"]

                    st.success("✅ Analiza zakończona pomyślnie!")
                    st.columns(4)[0].metric("Standard", f"{stats['std']}h")
                    st.columns(4)[1].metric("Nadgodziny", f"{stats['nad']}h")
                    st.columns(4)[2].metric("Soboty", f"{stats['sob']}h")
                    st.columns(4)[3].metric("Nd/Święta", f"{stats['nie']}h")
                    st.balloons()

            except Exception as e:
                st.error(f"⚠️ Wystąpił błąd podczas analizy: {e}")
                st.info("Spróbuj wgrać mniejsze zdjęcie lub odświeżyć stronę.")

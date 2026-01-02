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
    # Pobieranie modelu przy starcie - to może chwilę potrwać za pierwszym razem
    return easyocr.Reader(['pl'], gpu=False, download_enabled=True)

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

# --- 3. BOCZNY PANEL ---
with st.sidebar:
    st.header("⚙️ Ustawienia")
    wybrany_rok = st.selectbox("Rok:", [2024, 2025, 2026], index=2) # Domyślnie 2026
    miesiace = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
                "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    wybrany_m_nazwa = st.selectbox("Miesiąc:", miesiace, index=datetime.now().month-1)
    m_idx = miesiace.index(wybrany_m_nazwa) + 1
    
    st.divider()
    stawka_podst = st.number_input("Stawka podstawowa (zł/h):", value=25.0)
    dodatek_nadg = st.number_input("Dodatek za nadgodzinę (+ zł):", value=30.0)

# --- 4. GŁÓWNY INTERFEJS ---
st.title("💰 Kalkulator Wypłaty")

tab1, tab2, tab3 = st.tabs(["🧮 Obliczenia", "📊 Historia", "📸 Skanuj Grafik"])

# --- TAB 1: OBLICZENIA ---
with tab1:
    h_etat = get_working_hours_pl(wybrany_rok, m_idx)
    st.info(f"Wymiar czasu pracy: **{h_etat}h** ({wybrany_m_nazwa} {wybrany_rok})")
    
    h_std = st.number_input("Godziny standardowe:", value=st.session_state.get('ocr_std', float(h_etat)))
    h_nad = st.number_input("Nadgodziny:", value=st.session_state.get('ocr_nad', 0.0))
    h_sob = st.number_input("Soboty (+50%):", value=st.session_state.get('ocr_sob', 0.0))
    h_nie = st.number_input("Niedziele (+100%):", value=st.session_state.get('ocr_nie', 0.0))

    # Obliczenie sumy z użyciem formatowania LaTeX dla przejrzystości wzoru
    # $$Suma = (h_{std} \cdot stawka) + (h_{nad} \cdot (stawka + dodatek)) + (h_{sob} \cdot stawka \cdot 1.5) + (h_{nie} \cdot stawka \cdot 2.0)$$
    total = (h_std * stawka_podst) + (h_nad * (stawka_podst + dodatek_nadg)) + \
            (h_sob * stawka_podst * 1.5) + (h_nie * stawka_podst * 2.0)
    
    st.divider()
    st.metric("Suma do wypłaty (Brutto)", f"{total:,.2f} zł")

# --- TAB 2: HISTORIA ---
with tab2:
    if 'historia_df' in st.session_state and not st.session_state['historia_df'].empty:
        st.dataframe(st.session_state['historia_df'], width="stretch")
    else:
        st.info("Brak wpisów w historii.")

# --- TAB 3: SKANOWANIE ---
with tab3:
    st.subheader("📸 Skaner Grafiku")
    plik = st.file_uploader("Wgraj zdjęcie:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        img_raw = Image.open(plik)
        img_raw = ImageOps.exif_transpose(img_raw)
        img_gray = ImageOps.grayscale(img_raw)
        img_gray = ImageOps.autocontrast(img_gray, cutoff=2)
        
        # Nowy parametr width="stretch" zgodny z wersją 2026
        st.image(img_gray, caption="Obraz przygotowany dla AI", width="stretch")

        if st.button("🚀 ANALIZUJ ZDJĘCIE"):
            try:
                with st.spinner("Pobieranie modeli i analiza... (to może potrwać do 2 minut przy pierwszym razie)"):
                    reader = load_ocr()
                    wyniki = reader.readtext(np.array(img_gray))
                
                header_x = None
                for (bbox, tekst, prob) in wyniki:
                    if any(x in tekst.lower() for x in ["ilo", "godz"]):
                        header_x = (bbox[0][0] + bbox[1][0]) / 2
                        break

                if header_x is None:
                    header_x = np.array(img_gray).shape[1] * 0.7

                dni_temp = []
                for (bbox, tekst, prob) in wyniki:
                    x_c = (bbox[0][0] + bbox[1][0]) / 2
                    y_c = (bbox[0][1] + bbox[2][1]) / 2
                    t_mod = tekst.upper().replace('O', '0').replace('B', '8').replace('S', '5')
                    cyfry = "".join(filter(str.isdigit, t_mod))
                    
                    if cyfry:
                        val = int(cyfry)
                        if abs(x_c - header_x) < 150 and 1 <= val <= 24:
                            dni_temp.append({'y': y_c, 'val': val})
                
                dni_temp.sort(key=lambda x: x['y'])
                st.session_state['dni_lista'] = [d['val'] for d in dni_temp[:31]]
                st.success("✅ Odczytano dane! Popraw je poniżej jeśli trzeba.")
                
            except Exception as e:
                st.error(f"Błąd silnika OCR: {e}")

        # Sekcja korekty
        if 'dni_lista' in st.session_state:
            poprawione = []
            cols = st.columns(7)
            for i in range(31):
                with cols[i % 7]:
                    d_val = st.session_state['dni_lista'][i] if i < len(st.session_state['dni_lista']) else 0.0
                    v = st.number_input(f"Dzień {i+1}", value=float(d_val), key=f"d26_{i}")
                    poprawione.append(v)
            
            if st.button("✅ POTWIERDŹ"):
                stats = {"std": 0.0, "nad": 0.0, "sob": 0.0, "nie": 0.0}
                pl_hols = holidays.Poland(years=wybrany_rok)
                for i, h in enumerate(poprawione):
                    if h <= 0: continue
                    curr_d = date(wybrany_rok, m_idx, i + 1)
                    if curr_d.weekday() == 5: stats["sob"] += h
                    elif curr_d.weekday() == 6 or curr_d in pl_hols: stats["nie"] += h
                    else:
                        if h > 8:
                            stats["std"] += 8
                            stats["nad"] += (h - 8)
                        else: stats["std"] += h
                
                st.session_state['ocr_std'] = stats["std"]
                st.session_state['ocr_nad'] = stats["nad"]
                st.session_state['ocr_sob'] = stats["sob"]
                st.session_state['ocr_nie'] = stats["nie"]
                st.rerun()

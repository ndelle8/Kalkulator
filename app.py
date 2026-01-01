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

# --- KONFIGURACJA ---
st.set_page_config(page_title="Kalkulator Zarobków PRO", page_icon="💰", layout="wide")

@st.cache_resource
def load_ocr():
    # Ustawienie download_enabled=True pomaga w instalacji na Streamlit Cloud
    return easyocr.Reader(['pl'], gpu=False)

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

st.title("💰 Inteligentny Kalkulator Wypłaty")

tab1, tab2, tab3 = st.tabs(["🧮 Obliczenia", "📊 Historia", "📸 Skanuj Grafik"])

# --- TAB 1: OBLICZENIA ---
with tab1:
    h_etat = get_working_hours_pl(wybrany_rok, m_idx)
    st.info(f"Wymiar czasu pracy: **{h_etat}h** ({wybrany_m_nazwa} {wybrany_rok})")
    
    # Pobieranie danych z sesji (po skanowaniu)
    h_std = st.number_input("Godziny standardowe:", value=st.session_state.get('ocr_std', float(h_etat)))
    h_nad = st.number_input("Nadgodziny:", value=st.session_state.get('ocr_nad', 0.0))
    h_sob = st.number_input("Soboty (+50%):", value=st.session_state.get('ocr_sob', 0.0))
    h_nie = st.number_input("Niedziele (+100%):", value=st.session_state.get('ocr_nie', 0.0))

    total = (h_std * stawka_podst) + (h_nad * (stawka_podst + dodatek_nadg)) + \
            (h_sob * stawka_podst * 1.5) + (h_nie * stawka_podst * 2.0)
    st.metric("Suma do wypłaty (Brutto)", f"{total:,.2f} zł")

# --- TAB 3: SKANOWANIE ---
with tab3:
    st.subheader("📸 Skanowanie tabeli grafiku")
    plik = st.file_uploader("Wgraj zdjęcie:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        img = Image.open(plik)
        # Poprawa kontrastu dla lepszego OCR
        img = ImageOps.exif_transpose(img)
        img.thumbnail((1200, 1200))
        st.image(img, width=400)
        
        if st.button("🚀 Rozpocznij analizę"):
            try:
                with st.spinner("Przetwarzam zdjęcie..."):
                    reader = load_ocr()
                    wyniki = reader.readtext(np.array(img))
                
                # DIAGNOSTYKA: Pokaż co widzi OCR
                with st.expander("🔍 Zobacz co odczytał program (Diagnostyka)"):
                    for res in wyniki: st.write(f"Tekst: {res[1]} (Pewność: {res[2]:.2d})")

                # SZUKANIE KOLUMNY
                header_x = None
                for (bbox, tekst, prob) in wyniki:
                    t = tekst.lower()
                    if any(x in t for x in ["ilo", "godz", "ilos", "god"]):
                        header_x = (bbox[0][0] + bbox[1][0]) / 2
                        st.success(f"📍 Znaleziono nagłówek: {tekst}")
                        break
                
                # Jeśli nie znalazł nagłówka, szukaj po prawej stronie
                if header_x is None:
                    st.warning("Nie znalazłem napisu 'Ilość godzin'. Szukam najliczniejszej kolumny po prawej...")
                    img_width = np.array(img).shape[1]
                    header_x = img_width * 0.6  # Założenie, że kolumna jest w 60-70% szerokości

                # ZBIERANIE DANYCH
                dni_godziny = []
                for (bbox, tekst, prob) in wyniki:
                    x_c = (bbox[0][0] + bbox[1][0]) / 2
                    y_c = (bbox[0][1] + bbox[2][1]) / 2
                    
                    # Czyścimy tekst - szukamy tylko cyfr
                    clean_txt = "".join(filter(str.isdigit, tekst))
                    if clean_txt:
                        val = int(clean_txt)
                        # Sprawdzamy czy liczba jest w kolumnie 'ilość godzin'
                        if abs(x_c - header_x) < 100 and 1 <= val <= 24:
                            dni_godziny.append({'y': y_center, 'val': val})

                # Sortowanie i rozliczanie
                dni_godziny.sort(key=lambda x: x['y'])
                
                stats = {"std": 0.0, "nad": 0.0, "sob": 0.0, "nie": 0.0}
                pl_holidays = holidays.Poland(years=wybrany_rok)
                
                for i, d in enumerate(dni_godziny[:31]):
                    dzien_nr = i + 1
                    h = float(d['val'])
                    curr_d = date(wybrany_rok, m_idx, dzien_nr)
                    
                    if curr_d.weekday() == 5: stats["sob"] += h
                    elif curr_d.weekday() == 6 or curr_d in pl_holidays: stats["nie"] += h
                    else:
                        if h > 8:
                            stats["std"] += 8
                            stats["nad"] += (h - 8)
                        else: stats["std"] += h

                st.session_state['ocr_std'] = stats["std"]
                st.session_state['ocr_nad'] = stats["nad"]
                st.session_state['ocr_sob'] = stats["sob"]
                st.session_state['ocr_nie'] = stats["nie"]
                
                st.success("✅ Dane odczytane! Przejdź do zakładki 'Obliczenia'.")
                st.write(stats)

            except Exception as e:
                st.error(f"Błąd: {e}")

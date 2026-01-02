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

# --- 1. KONFIGURACJA ---
st.set_page_config(page_title="Kalkulator Zarobków PRO", page_icon="💰", layout="wide")

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['pl'], gpu=False)

def get_working_hours_pl(year, month):
    pl_holidays = holidays.Poland(years=year)
    working_days = 0
    num_days = calendar.monthrange(year, month)[1]
    for day in range(1, num_days + 1):
        curr_date = date(year, month, day)
        if curr_date.weekday() < 5 and curr_date not in pl_holidays:
            working_days += 1
    return working_days * 8

# --- 2. BOCZNY PANEL ---
with st.sidebar:
    st.header("⚙️ Ustawienia")
    wybrany_rok = st.selectbox("Rok:", [2024, 2025, 2026], index=2)
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
    st.info(f"Wymiar czasu pracy: **{h_etat}h** ({wybrany_m_nazwa} {wybrany_rok})")
    
    h_std = st.number_input("Godziny standardowe:", value=st.session_state.get('ocr_std', float(h_etat)))
    h_nad = st.number_input("Nadgodziny:", value=st.session_state.get('ocr_nad', 0.0))
    h_sob = st.number_input("Soboty (+50%):", value=st.session_state.get('ocr_sob', 0.0))
    h_nie = st.number_input("Niedziele (+100%):", value=st.session_state.get('ocr_nie', 0.0))

    total = (h_std * stawka_podst) + (h_nad * (stawka_podst + dodatek_nadg)) + \
            (h_sob * stawka_podst * 1.5) + (h_nie * stawka_podst * 2.0)
    st.metric("Suma do wypłaty (Brutto)", f"{total:,.2f} zł")

# --- TAB 3: SKANOWANIE (LOGIKA 4. KOLUMNY) ---
with tab3:
    st.subheader("📸 Inteligentne skanowanie 4. kolumny")
    plik = st.file_uploader("Wgraj zdjęcie wypełnionego grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        img_raw = Image.open(plik)
        img_raw = ImageOps.exif_transpose(img_raw)
        img_raw.thumbnail((1000, 1000)) # Oszczędność RAM
        img_gray = ImageOps.grayscale(img_raw)
        img_gray = ImageOps.autocontrast(img_gray, cutoff=2)
        
        st.image(img_gray, caption="Obraz przygotowany do analizy", width=500)

        if st.button("🚀 ANALIZUJ KOLUMNĘ 'ILOŚĆ GODZIN'"):
            try:
                with st.spinner("Lokalizuję kolumny..."):
                    reader = load_ocr()
                    wyniki = reader.readtext(np.array(img_gray))
                
                # 1. SZUKANIE NAGŁÓWKÓW I SORTOWANIE
                naglowki = []
                for (bbox, tekst, prob) in wyniki:
                    y_center = (bbox[0][1] + bbox[2][1]) / 2
                    # Szukamy tylko w górnej części obrazu (nagłówki)
                    if y_center < np.array(img_gray).shape[0] * 0.25:
                        naglowki.append({
                            'x': (bbox[0][0] + bbox[1][0]) / 2,
                            'tekst': tekst
                        })
                
                # Sortujemy nagłówki od lewej do prawej
                naglowki.sort(key=lambda x: x['x'])
                
                # Próbujemy znaleźć "Ilość godzin" po tekście LUB po prostu bierzemy 4. nagłówek
                header_x = None
                for i, h in enumerate(naglowki):
                    t = h['tekst'].lower()
                    if "ilo" in t or "god" in t:
                        header_x = h['x']
                        st.success(f"📍 Wykryto kolumnę na podstawie tekstu: '{h['tekst']}'")
                        break
                
                # Fallback: Jeśli OCR źle odczytał tekst, bierzemy 4-ty wykryty blok tekstu od lewej
                if header_x is None and len(naglowki) >= 4:
                    header_x = naglowki[3]['x']
                    st.warning(f"⚠️ Niepewny tekst, celuję w 4. kolumnę od lewej (pozycja x: {int(header_x)})")

                if header_x:
                    # 2. ZBIERANIE LICZB POD WYZNACZONYM X
                    dni_temp = []
                    for (bbox, tekst, prob) in wyniki:
                        x_c = (bbox[0][0] + bbox[1][0]) / 2
                        y_c = (bbox[0][1] + bbox[2][1]) / 2
                        
                        # Czyścimy tekst i szukamy cyfr
                        t_mod = tekst.upper().replace('O', '0').replace('B', '8').replace('S', '5')
                        cyfry = "".join(filter(str.isdigit, t_mod))
                        
                        if cyfry:
                            val = int(cyfry)
                            # Szukamy w pionowym tunelu o szerokości 120px
                            if abs(x_c - header_x) < 120 and 1 <= val <= 24:
                                dni_temp.append({'y': y_c, 'val': val})

                    # Sortujemy od góry do dołu
                    dni_temp.sort(key=lambda x: x['y'])
                    st.session_state['dni_lista'] = [d['val'] for d in dni_temp[:31]]
                    st.success(f"✅ Odczytano {len(st.session_state['dni_lista'])} wartości. Sprawdź je poniżej.")
                else:
                    st.error("Nie udało się zlokalizować kolumn. Zrób zdjęcie tak, aby góra tabeli była wyraźna.")

            except Exception as e:
                st.error(f"Błąd: {e}")

        # --- SEKCJA KOREKTY ---
        if 'dni_lista' in st.session_state:
            st.divider()
            poprawione = []
            cols = st.columns(7)
            for i in range(31):
                with cols[i % 7]:
                    d_val = st.session_state['dni_lista'][i] if i < len(st.session_state['dni_lista']) else 0.0
                    v = st.number_input(f"Dz {i+1}", value=float(d_val), key=f"korekta_{i}")
                    poprawione.append(v)
            
            if st.button("✅ ZATWIERDŹ I PRZEŚLIJ DO OBLICZEŃ"):
                stats = {"std": 0.0, "nad": 0.0, "sob": 0.0, "nie": 0.0}
                pl_hols = holidays.Poland(years=wybrany_rok)
                for i, h in enumerate(poprawione):
                    if h <= 0: continue
                    try:
                        curr_d = date(wybrany_rok, m_idx, i + 1)
                        if curr_d.weekday() == 5: stats["sob"] += h
                        elif curr_d.weekday() == 6 or curr_d in pl_hols: stats["nie"] += h
                        else:
                            if h > 8:
                                stats["std"] += 8
                                stats["nad"] += (h - 8)
                            else: stats["std"] += h
                    except: continue
                
                st.session_state['ocr_std'] = stats["std"]
                st.session_state['ocr_nad'] = stats["nad"]
                st.session_state['ocr_sob'] = stats["sob"]
                st.session_state['ocr_nie'] = stats["nie"]
                st.success("Dane gotowe! Wróć do zakładki 'Obliczenia'.")

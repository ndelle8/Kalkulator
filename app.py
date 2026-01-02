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
    # Inicjalizacja EasyOCR (bez GPU dla stabilności na Streamlit Cloud)
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

# --- 3. BOCZNY PANEL ---
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
st.title("💰 Kalkulator Wypłaty z Inteligentnym Skanerem")

tab1, tab2, tab3 = st.tabs(["🧮 Obliczenia", "📊 Historia", "📸 Skanuj Grafik"])

# --- TAB 1: OBLICZENIA ---
with tab1:
    h_etat = get_working_hours_pl(wybrany_rok, m_idx)
    st.info(f"Wymiar czasu pracy: **{h_etat}h** ({wybrany_m_nazwa} {wybrany_rok})")
    
    # Dane pobierane z sesji (po skanowaniu) lub wartości domyślne
    h_std = st.number_input("Godziny standardowe:", value=st.session_state.get('ocr_std', float(h_etat)))
    h_nad = st.number_input("Nadgodziny:", value=st.session_state.get('ocr_nad', 0.0))
    h_sob = st.number_input("Soboty (+50%):", value=st.session_state.get('ocr_sob', 0.0))
    h_nie = st.number_input("Niedziele (+100%):", value=st.session_state.get('ocr_nie', 0.0))

    # Wzór na wynagrodzenie brutto
    # $$Total = (h_{std} \cdot stawka) + (h_{nad} \cdot (stawka + dodatek)) + (h_{sob} \cdot stawka \cdot 1.5) + (h_{nie} \cdot stawka \cdot 2.0)$$
    total = (h_std * stawka_podst) + (h_nad * (stawka_podst + dodatek_nadg)) + \
            (h_sob * stawka_podst * 1.5) + (h_nie * stawka_podst * 2.0)
    
    st.divider()
    st.metric("Suma do wypłaty (Brutto)", f"{total:,.2f} zł")
    
    if st.button("💾 Zapisz ten miesiąc do historii"):
        nowy_wpis = {
            "Data": f"{wybrany_m_nazwa} {wybrany_rok}",
            "Standard": h_std,
            "Nadgodziny": h_nad,
            "Soboty": h_sob,
            "Niedziele": h_nie,
            "Suma PLN": round(total, 2)
        }
        if 'historia_df' not in st.session_state:
            st.session_state['historia_df'] = pd.DataFrame(columns=["Data", "Standard", "Nadgodziny", "Soboty", "Niedziele", "Suma PLN"])
        
        st.session_state['historia_df'] = pd.concat([st.session_state['historia_df'], pd.DataFrame([nowy_wpis])], ignore_index=True)
        st.success("Zapisano! Możesz pobrać historię w zakładce 'Historia'.")

# --- TAB 2: HISTORIA ---
with tab2:
    st.subheader("Twoja Historia Zarobków")
    if 'historia_df' in st.session_state and not st.session_state['historia_df'].empty:
        df = st.session_state['historia_df']
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Pobierz plik historii (CSV)", csv, "historia_zarobkow.csv", "text/csv")
        
        if st.button("🗑️ Wyczyść historię"):
            del st.session_state['historia_df']
            st.rerun()
    else:
        st.info("Brak zapisanych wpisów. Kliknij 'Zapisz' w zakładce Obliczenia.")

# --- TAB 3: SKANOWANIE (WERSJA PANCERNA) ---
with tab3:
    st.subheader("📸 Skaner Grafiku (Pismo Ręczne)")
    plik = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        img_raw = Image.open(plik)
        img_raw = ImageOps.exif_transpose(img_raw)
        img_gray = ImageOps.grayscale(img_raw)
        img_gray = ImageOps.autocontrast(img_gray, cutoff=2)
        
        c_img, c_ctrl = st.columns([1, 1])
        with c_img:
            st.image(img_gray, caption="Obraz przygotowany dla AI (czarno-biały)", use_container_width=True)
        with c_ctrl:
            margines = st.slider("Czułość kolumny (margines):", 50, 400, 150)
            st.info("Zwiększ czułość, jeśli Twoje pismo jest daleko od nagłówka.")

        if st.button("🚀 ANALIZUJ ZDJĘCIE"):
            try:
                with st.spinner("AI analizuje grafik..."):
                    reader = load_ocr()
                    wyniki = reader.readtext(np.array(img_gray))
                
                header_x = None
                for (bbox, tekst, prob) in wyniki:
                    t = tekst.lower()
                    if any(x in t for x in ["ilo", "godz", "ilos", "god"]):
                        header_x = (bbox[0][0] + bbox[1][0]) / 2
                        st.success(f"Znaleziono kolumnę: '{tekst}'")
                        break
                
                if header_x is None:
                    st.warning("Nie wykryto nagłówka. Ustawiam środek po prawej stronie...")
                    header_x = np.array(img_gray).shape[1] * 0.7

                dni_temp = []
                for (bbox, tekst, prob) in wyniki:
                    x_c = (bbox[0][0] + bbox[1][0]) / 2
                    y_c = (bbox[0][1] + bbox[2][1]) / 2
                    t_mod = tekst.upper().replace('O', '0').replace('B', '8').replace('S', '5').replace('G', '6')
                    cyfry = "".join(filter(str.isdigit, t_mod))
                    
                    if cyfry:
                        val = int(cyfry)
                        if abs(x_c - header_x) < margines and 1 <= val <= 24:
                            dni_temp.append({'y': y_c, 'val': val})
                
                dni_temp.sort(key=lambda x: x['y'])
                st.session_state['dni_lista'] = [d['val'] for d in dni_temp[:31]]
                
            except Exception as e:
                st.error(f"Błąd: {e}")

        if 'dni_lista' in st.session_state:
            st.divider()
            st.subheader("📝 Zweryfikuj i popraw odczytane godziny")
            
            poprawione_godziny = []
            cols = st.columns(7)
            for i in range(31):
                with cols[i % 7]:
                    domyslna = st.session_state['dni_lista'][i] if i < len(st.session_state['dni_lista']) else 0.0
                    val = st.number_input(f"Dzień {i+1}", value=float(domyslna), step=0.5, key=f"d_{i}")
                    poprawione_godziny.append(val)
            
            if st.button("✅ PRZEŚLIJ DO KALKULATORA"):
                stats = {"std": 0.0, "nad": 0.0, "sob": 0.0, "nie": 0.0}
                pl_holidays = holidays.Poland(years=wybrany_rok)
                for i, h in enumerate(poprawione_godziny):
                    if h <= 0: continue
                    curr_d = date(wybrany_rok, m_idx, i + 1)
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
                st.success("Dane przesłane! Sprawdź zakładkę 'Obliczenia'.")

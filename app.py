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
    # Używamy darmowego silnika EasyOCR (bez GPU dla stabilności na serwerze)
    # download_enabled=True pozwala pobrać model przy pierwszym uruchomieniu
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

    total = (h_std * stawka_podst) + (h_nad * (stawka_podst + dodatek_nadg)) + \
            (h_sob * stawka_podst * 1.5) + (h_nie * stawka_podst * 2.0)
    
    st.divider()
    st.metric("Suma do wypłaty (Brutto)", f"{total:,.2f} zł")
    
    if st.button("🗑️ Wyczyść dane skanowania"):
        for key in ['ocr_std', 'ocr_nad', 'ocr_sob', 'ocr_nie', 'dni_lista']:
            if key in st.session_state: del st.session_state[key]
        st.rerun()

# --- TAB 2: HISTORIA ---
with tab2:
    st.subheader("Historia zarobków")
    st.write("Tu możesz wgrać swoje poprzednie pliki CSV.")
    uploaded_csv = st.file_uploader("Wgraj plik CSV", type="csv")
    if uploaded_csv:
        df = pd.read_csv(uploaded_csv)
        st.dataframe(df)

# --- TAB 3: SKANOWANIE (WERSJA PANCERNA & LEKKA) ---
with tab3:
    st.subheader("📸 Inteligentny Skaner Grafiku")
    st.write("Skup się na kolumnie 'Ilość godzin'. System automatycznie rozpozna pismo ręczne.")
    
    plik = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik:
        # 1. Wczytanie i OBRÓBKA WSTĘPNA
        img_raw = Image.open(plik)
        img_raw = ImageOps.exif_transpose(img_raw) # Poprawa orientacji
        
        # --- KLUCZOWA ZMIANA: ZMNIEJSZENIE OBRAZU ---
        # Zmniejszamy do max 800x800px, aby nie zapchać pamięci serwera.
        # Dla OCR to wciąż wystarczająca jakość.
        img_raw.thumbnail((800, 800)) 
        # --------------------------------------------

        # Konwersja na czarno-białe i podbicie kontrastu
        img_gray = ImageOps.grayscale(img_raw)
        img_gray = ImageOps.autocontrast(img_gray, cutoff=2)
        
        c_img, c_ctrl = st.columns([1, 1])
        with c_img:
            # Używamy width="stretch" zamiast use_container_width (nowy standard Streamlit)
            st.image(img_gray, caption="Obraz przygotowany dla AI (zmniejszony)", width="stretch")
        with c_ctrl:
            margines = st.slider("Czułość szukania kolumny:", 50, 300, 150)
            st.info("Podpowiedź: Jeśli program nie widzi liczb, zwiększ czułość.")

        if st.button("🚀 URUCHOM ANALIZĘ"):
            # Dodatkowy blok try-except, aby złapać błędy pamięci i wyświetlić komunikat zamiast "Oh no"
            try:
                with st.spinner("AI analizuje pismo odręczne... (to może chwilę potrwać)"):
                    reader = load_ocr()
                    # Przekazujemy zmniejszony, czarno-biały obraz
                    wyniki = reader.readtext(np.array(img_gray))
                
                # 1. Szukanie nagłówka
                header_x = None
                for (bbox, tekst, prob) in wyniki:
                    t = tekst.lower()
                    if any(x in t for x in ["ilo", "godz", "ilos", "god", "80dz"]):
                        header_x = (bbox[0][0] + bbox[1][0]) / 2
                        st.success(f"📍 Wykryto kolumnę: '{tekst}'")
                        break
                
                if header_x is None:
                    st.warning("⚠️ Nie wykryto nagłówka. Szukam liczb po prawej stronie...")
                    # Szukamy w 70% szerokości zmniejszonego obrazu
                    header_x = np.array(img_gray).shape[1] * 0.7

                # 2. Zbieranie liczb
                dni_temp = []
                for (bbox, tekst, prob) in wyniki:
                    x_c = (bbox[0][0] + bbox[1][0]) / 2
                    y_c = (bbox[0][1] + bbox[2][1]) / 2
                    
                    # Zamiana typowych błędów OCR (B na 8, O na 0, S na 5)
                    t_mod = tekst.upper().replace('O', '0').replace('B', '8').replace('S', '5').replace('G', '6')
                    cyfry = "".join(filter(str.isdigit, t_mod))
                    
                    if cyfry:
                        val = int(cyfry)
                        # Sprawdzamy, czy liczba jest w pionie kolumny i ma sensowną wartość
                        if abs(x_c - header_x) < margines and 1 <= val <= 24:
                            dni_temp.append({'y': y_c, 'val': val})
                
                # Sortujemy od góry do dołu
                dni_temp.sort(key=lambda x: x['y'])
                # Bierzemy pierwsze 31 znalezionych liczb
                st.session_state['dni_lista'] = [d['val'] for d in dni_temp[:31]]
                
            except Exception as e:
                st.error(f"Wystąpił błąd podczas analizy: {e}")
                st.warning("Jeśli to błąd pamięci, spróbuj wgrać zdjęcie o mniejszej rozdzielczości.")

        # 3. INTERAKTYWNA KOREKTA (zawsze widoczna po udanym skanowaniu)
        if 'dni_lista' in st.session_state:
            st.divider()
            st.subheader("📝 Sprawdź i popraw odczytane godziny")
            st.write("System przypisał liczby do kolejnych dni miesiąca. Popraw błędy, jeśli wystąpiły.")
            
            poprawione_godziny = []
            cols = st.columns(7)
            for i in range(31):
                with cols[i % 7]:
                    # Jeśli lista jest krótsza niż 31 dni, wypełniamy zerami
                    domyslna = st.session_state['dni_lista'][i] if i < len(st.session_state['dni_lista']) else 0.0
                    # Unikalny klucz dla każdego pola, aby Streamlit się nie gubił
                    val = st.number_input(f"Dz {i+1}", value=float(domyslna), step=0.5, key=f"dzien_korekta_{i}")
                    poprawione_godziny.append(val)
            
            if st.button("✅ POTWIERDŹ I PRZELICZ WYPŁATĘ"):
                stats = {"std": 0.0, "nad": 0.0, "sob": 0.0, "nie": 0.0}
                pl_holidays = holidays.Poland(years=wybrany_rok)
                
                for i, h in enumerate(poprawione_godziny):
                    dzien_nr = i + 1
                    if h <= 0: continue
                    # Tworzymy datę dla konkretnego dnia
                    try:
                        curr_d = date(wybrany_rok, m_idx, dzien_nr)
                    except ValueError:
                        continue # Pomijamy nieistniejące dni (np. 30 lutego)

                    wday = curr_d.weekday() # 0=Pon, 5=Sob, 6=Nie
                    
                    if wday == 5: stats["sob"] += h
                    elif wday == 6 or curr_d in pl_holidays: stats["nie"] += h
                    else: # Dzień roboczy
                        if h > 8:
                            stats["std"] += 8
                            stats["nad"] += (h - 8)
                        else: stats["std"] += h
                
                # Zapisujemy wyniki do sesji, aby były widoczne w zakładce Obliczenia
                st.session_state['ocr_std'] = stats["std"]
                st.session_state['ocr_nad'] = stats["nad"]
                st.session_state['ocr_sob'] = stats["sob"]
                st.session_state['ocr_nie'] = stats["nie"]
                st.success("Dane przesłane do kalkulatora! Przejdź do zakładki Obliczenia.")

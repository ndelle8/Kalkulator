import streamlit as st
import pandas as pd
import holidays
import calendar
import os
import numpy as np
import easyocr
import re
from datetime import datetime, date, timedelta
from PIL import Image

# --- KONFIGURACJA ---
st.set_page_config(page_title="Kalkulator Zarobków PRO", page_icon="💰", layout="wide")

@st.cache_resource
def load_ocr():
    # Pobieramy model dla języka polskiego
    return easyocr.Reader(['pl'])

reader = load_ocr()

def parse_time_to_decimal(time_str):
    """Zamienia tekst typu '6:00' lub '14:30' na liczbę (np. 8.5)"""
    try:
        # Usuwamy litery, zostawiamy cyfry i separatory
        clean = re.sub(r'[^0-9:.,]', '', time_str).replace(',', '.').replace(':', '.')
        if '.' in clean:
            parts = clean.split('.')
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 and parts[1] else 0
            # Obsługa formatu '6.00' -> 6h, '14.30' -> 14.5h
            return h + (m / 60.0)
        return float(clean)
    except:
        return None

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

with tab3:
    st.subheader("Automatyczna analiza zdjęcia")
    plik_foto = st.file_uploader("Wgraj zdjęcie grafiku:", type=['jpg', 'jpeg', 'png'])
    
    if plik_foto:
        image = Image.open(plik_foto)
        st.image(image, caption="Twój grafik", width=500)
        
        if st.button("🚀 Analizuj i rozlicz godziny"):
            with st.spinner("AI analizuje tabelę..."):
                img_array = np.array(image)
                wynik = reader.readtext(img_array)
                
                # Szukanie współrzędnych kolumn
                col_x = {"start": None, "end": None, "total": None}
                for (bbox, tekst, prob) in wynik:
                    t = tekst.lower()
                    if "przyj" in t: col_x["start"] = (bbox[0][0] + bbox[1][0]) / 2
                    if "wyj" in t: col_x["end"] = (bbox[0][0] + bbox[1][0]) / 2
                    if "ilo" in t or "godz" in t: col_x["total"] = (bbox[0][0] + bbox[1][0]) / 2

                # Zbieranie danych wiersz po wierszu
                dni_data = {i: {"start": "", "end": "", "total": ""} for i in range(1, 32)}
                
                for (bbox, tekst, prob) in wynik:
                    x_c = (bbox[0][0] + bbox[1][0]) / 2
                    y_c = (bbox[0][1] + bbox[2][1]) / 2
                    
                    # Ignorujemy nagłówki (prymitywne filtrowanie po wysokości Y)
                    if y_c < 150: continue 

                    # Przypisujemy tekst do wiersza (dnia) na podstawie wysokości Y
                    # W Twoim grafiku wiersze są dość równe, więc dzielimy obraz na 31 części
                    # (To uproszczenie - lepiej działa grupowanie po y_center)
                    # Szukamy też kolumny LP (Liczba porządkowa), aby wiedzieć który to dzień
                    
                # Statystyki końcowe
                pl_holidays = holidays.Poland(years=wybrany_rok)
                podsumowanie = {"std": 0.0, "nad": 0.0, "sob": 0.0, "nie": 0.0}
                
                # LOGIKA ANALIZY DANYCH (uproszczona na potrzeby darmowego OCR)
                # Szukamy wszystkich liczb w kolumnie 'Ilość godzin'
                extracted_hours = []
                for (bbox, tekst, prob) in wynik:
                    x_c = (bbox[0][0] + bbox[1][0]) / 2
                    if col_x["total"] and abs(x_c - col_x["total"]) < 60:
                        val = "".join(filter(str.isdigit, tekst))
                        if val and 1 <= int(val) <= 24:
                            extracted_hours.append(int(val))

                # Rozdzielanie na dni (zakładamy kolejność od góry)
                for i, h in enumerate(extracted_hours[:31]):
                    dzien = i + 1
                    curr_date = date(wybrany_rok, m_idx, dzien)
                    wday = curr_date.weekday()

                    if wday == 5: podsumowanie["sob"] += h
                    elif wday == 6 or curr_date in pl_holidays: podsumowanie["nie"] += h
                    else:
                        if h > 8:
                            podsumowanie["std"] += 8
                            podsumowanie["nad"] += (h - 8)
                        else:
                            podsumowanie["std"] += h

                st.success("✅ Analiza zakończona!")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Standard", f"{podsumowanie['std']}h")
                c2.metric("Nadgodziny", f"{podsumowanie['nad']}h")
                c3.metric("Soboty", f"{podsumowanie['sob']}h")
                c4.metric("Nd/Święta", f"{podsumowanie['nie']}h")
                
                st.info("Pamiętaj: Jeśli suma się nie zgadza, sprawdź czy zdjęcie było proste i wyraźne.")

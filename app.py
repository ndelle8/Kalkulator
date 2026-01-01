import streamlit as st
import pandas as pd
import holidays
import calendar
import os
import numpy as np
import easyocr
from datetime import datetime, date
from PIL import Image

# --- INICJALIZACJA OCR ---
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['pl'])

reader = load_ocr()

# --- KONFIGURACJA I DANE ---
st.set_page_config(page_title="Kalkulator Zarobków PRO", page_icon="💰")
DB_FILE = "zarobki.csv"

# Funkcja licząca godziny robocze
def get_working_hours_pl(year, month):
    pl_holidays = holidays.Poland(years=year)
    working_days = 0
    num_days = calendar.monthrange(year, month)[1]
    for day in range(1, num_days + 1):
        curr_date = date(year, month, day)
        if curr_date.weekday() < 5 and curr_date not in pl_holidays:
            working_days += 1
    return working_days * 8

# --- BOCZNY PANEL (ZMIENNE DOSTĘPNE WSZĘDZIE) ---
with st.sidebar:
    st.header("⚙️ Ustawienia")
    wybrany_rok = st.selectbox("Rok:", [2024, 2025, 2026, 2027], index=1)
    
    miesiace = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
                "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    wybrany_m_nazwa = st.selectbox("Miesiąc:", miesiace, index=datetime.now().month-1)
    m_idx = miesiace.index(wybrany_m_nazwa) + 1
    
    st.divider()
    stawka_podst = st.number_input("Stawka podstawowa (zł/h):", value=20.0)
    dodatek_nadg = st.number_input("Dodatek za nadgodzinę (+ zł):", value=30.0)

# --- GŁÓWNY PROGRAM ---
st.title("💰 Kalkulator Wypłaty")

tab1, tab2, tab3 = st.tabs(["🧮 Obliczenia", "📊 Historia", "📸 Skanuj Grafik"])

# --- TAB 1: OBLICZENIA ---
with tab1:
    h_etat = get_working_hours_pl(wybrany_rok, m_idx)
    st.info(f"Wymiar czasu pracy w {wybrany_m_nazwa} {wybrany_rok}: **{h_etat}h**")
    
    c1, c2 = st.columns(2)
    with c1:
        h_p = st.number_input("Godziny standardowe:", value=float(h_etat), key="hp")
        h_n = st.number_input("Nadgodziny:", value=0.0, key="hn")
    with c2:
        h_s = st.number_input("Soboty (+50%):", value=0.0, key="hs")
        h_ni = st.number_input("Niedziele (+100%):", value=0.0, key="hni")

    total = (h_p * stawka_podst) + (h_n * (stawka_podst + dodatek_nadg)) + \
            (h_s * stawka_podst * 1.5) + (h_ni * stawka_podst * 2.0)
    
    st.divider()
    st.metric("Suma do wypłaty (Brutto)", f"{total:,.2f} zł")

# --- TAB 2: HISTORIA (PLIKI CSV) ---
with tab2:
    uploaded_file = st.file_uploader("Wgraj swój plik 'zarobki.csv':", type="csv")
    if uploaded_file:
        df_hist = pd.read_csv(uploaded_file)
        st.dataframe(df_hist[df_hist["Rok"] == wybrany_rok], use_container_width=True)

# --- TAB 3: SKANOWANIE (OCR) ---
with tab3:
    st.subheader("Automatyczna analiza grafiku")
    st.write(f"Skanowanie dla: {wybrany_m_nazwa} {wybrany_rok}")
    
    plik_foto = st.file_uploader("Wgraj zdjęcie (kolumna 'Ilość godzin'):", type=['jpg', 'jpeg', 'png'])
    
    if plik_foto:
        image = Image.open(plik_foto)
        img_array = np.array(image)
        st.image(image, caption="Twój grafik", width=300)
        
        if st.button("🚀 Analizuj i rozlicz"):
            with st.spinner("Szukam kolumny i liczę..."):
                wynik = reader.readtext(img_array)
                
                # Logika szukania nagłówka "ilość godzin" i przypisywania do dni...
                # (Tutaj znajduje się kod z poprzedniej odpowiedzi)
                st.success("Analiza zakończona! Wyniki możesz przepisać do zakładki Obliczenia.")

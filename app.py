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
    st.write(f"Skanowanie dla: **{wybrany_m_nazwa} {wybrany_rok}**")
    
    plik_foto = st.file_uploader("Wgraj zdjęcie (kolumna 'Ilość godzin'):", type=['jpg', 'jpeg', 'png'])
    
    if plik_foto:
        image = Image.open(plik_foto)
        img_array = np.array(image)
        st.image(image, caption="Twój grafik", width=300)
        
        if st.button("🚀 Analizuj i rozlicz"):
            with st.spinner("Przetwarzanie obrazu... to może potrwać chwilę"):
                wynik = reader.readtext(img_array)
                
                header_x = None
                # 1. Szukamy nagłówka "Ilość godzin"
                for (bbox, tekst, prob) in wynik:
                    t = tekst.lower()
                    if "ilo" in t or "godz" in t:
                        header_x = (bbox[0][0] + bbox[1][0]) / 2
                        st.write(f"📍 Znaleziono kolumnę: '{tekst}'")
                        break

                if not header_x:
                    st.error("Nie znaleziono nagłówka 'Ilość godzin'. Upewnij się, że jest widoczny na zdjęciu.")
                else:
                    # 2. Szukamy liczb w tej samej linii pionowej (pod nagłówkiem)
                    data_points = []
                    for (bbox, tekst, prob) in wynik:
                        # Usuwamy zbędne znaki, zostawiamy tylko cyfry
                        czysty_tekst = "".join(filter(str.isdigit, tekst))
                        if czysty_tekst:
                            liczba = int(czysty_tekst)
                            x_center = (bbox[0][0] + bbox[1][0]) / 2
                            y_center = (bbox[0][1] + bbox[2][1]) / 2
                            
                            # Jeśli liczba jest w pionie pod nagłówkiem (margines 60px)
                            if abs(x_center - header_x) < 60:
                                if 1 <= liczba <= 24: # Filtrujemy sensowne godziny pracy
                                    data_points.append({'y': y_center, 'val': liczba})

                    # Sortujemy od góry do dołu (wg osi Y)
                    data_points.sort(key=lambda x: x['y'])

                    # 3. Rozliczanie zgodnie z kalendarzem
                    pl_holidays = holidays.Poland(years=wybrany_rok)
                    dni_w_miesiacu = calendar.monthrange(wybrany_rok, m_idx)[1]
                    
                    wyniki = {"std": 0.0, "nad": 0.0, "sob": 0.0, "nie": 0.0}

                    # Przypisujemy odczytane liczby do kolejnych dni (1, 2, 3...)
                    for i, point in enumerate(data_points[:dni_w_miesiacu]):
                        dzien_nr = i + 1
                        h = float(point['val'])
                        curr_date = date(wybrany_rok, m_idx, dzien_nr)
                        weekday = curr_date.weekday() # 0=Pon, 5=Sob, 6=Nie

                        if weekday == 5: # Sobota
                            wyniki["sob"] += h
                        elif weekday == 6 or curr_date in pl_holidays: # Niedziela/Święto
                            wyniki["nie"] += h
                        else: # Dzień roboczy
                            if h > 8:
                                wyniki["std"] += 8
                                wyniki["nad"] += (h - 8)
                            else:
                                wyniki["std"] += h

                    # --- WYŚWIETLANIE WYNIKÓW ---
                    st.success("✅ Analiza zakończona!")
                    
                    st.markdown("### Odczytane wartości:")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Standard", f"{wyniki['std']}h")
                    c2.metric("Nadgodziny", f"{wyniki['nad']}h")
                    c3.metric("Soboty", f"{wyniki['sob']}h")
                    c4.metric("Nd/Święta", f"{wyniki['nie']}h")
                    
                    st.info("💡 Przepisz te wartości do zakładki 'Obliczenia', aby zobaczyć kwotę brutto.")
                    
                    # Opcjonalnie: podgląd tego, co program "widział" dzień po dniu
                    with st.expander("Zobacz szczegółowy wykaz dni"):
                        for i, p in enumerate(data_points[:dni_w_miesiacu]):
                            st.write(f"Dzień {i+1}: {p['val']}h")

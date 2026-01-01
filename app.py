import streamlit as st
import pandas as pd
import holidays
from datetime import datetime, date
import calendar
import os

# --- KONFIGURACJA ---
st.set_page_config(page_title="Kalkulator Zarobków PRO", page_icon="💰")
DB_FILE = "historia_zarobkow.csv"

# Funkcja licząca dokładne godziny robocze w Polsce (z uwzględnieniem świąt)
def get_working_hours_pl(year, month):
    pl_holidays = holidays.Poland(years=year)
    working_days = 0
    
    # Pobierz liczbę dni w miesiącu
    num_days = calendar.monthrange(year, month)[1]
    
    for day in range(1, num_days + 1):
        curr_date = date(year, month, day)
        # Jeśli to dzień roboczy (0-4 to Pon-Pt) i NIE jest to święto
        if curr_date.weekday() < 5 and curr_date not in pl_holidays:
            working_days += 1
            
    return working_days * 8

# Funkcja ładowania/zapisu danych
def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    return pd.DataFrame(columns=["Rok", "Miesiąc", "Zarobek"])

# --- BOCZNY PANEL ---
with st.sidebar:
    st.header("⚙️ Ustawienia")
    wybrany_rok = st.selectbox("Wybierz rok:", [2024, 2025, 2026, 2027], index=1)
    
    st.divider()
    st.subheader("Stawki")
    stawka_podst = st.number_input("Stawka podstawowa (zł/h):", value=20.0)
    dodatek_nadg = st.number_input("Dodatek za nadgodzinę (+ zł):", value=30.0)

# --- GŁÓWNY PROGRAM ---
st.title("💰 Kalkulator Wypłaty")

tab1, tab2 = st.tabs(["🧮 Obliczenia", "📊 Historia"])

miesiace = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
            "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]

with tab1:
    wybrany_m_nazwa = st.selectbox("Wybierz miesiąc:", miesiace, index=datetime.now().month-1)
    m_idx = miesiace.index(wybrany_m_nazwa) + 1
    
    # Tu dzieje się poprawna magia liczenia godzin
    h_etat = get_working_hours_pl(wybrany_rok, m_idx)
    
    st.info(f"Wymiar czasu pracy w {wybrany_m_nazwa} {wybrany_rok} to: **{h_etat}h**")
    
    c1, c2 = st.columns(2)
    with c1:
        h_p = st.number_input("Godziny standardowe:", value=float(h_etat))
        h_n = st.number_input("Nadgodziny:", value=0.0)
    with c2:
        h_s = st.number_input("Soboty (+50%):", value=0.0)
        h_ni = st.number_input("Niedziele (+100%):", value=0.0)

    # Obliczenia
    val_p = h_p * stawka_podst
    val_n = h_n * (stawka_podst + dodatek_nadg)
    val_s = h_s * (stawka_podst * 1.5)
    val_ni = h_ni * (stawka_podst * 2.0)
    total = val_p + val_n + val_s + val_ni

    st.divider()
    st.metric("Suma do wypłaty (Brutto)", f"{total:,.2f} zł")

    if st.button("💾 Zapisz wynik (Pobierz plik)"):
        # W Streamlit Cloud musimy pobrać plik, by go nie stracić
        df = load_data()
        df = df[~((df["Rok"] == wybrany_rok) & (df["Miesiąc"] == wybrany_m_nazwa))]
        nowy = pd.DataFrame([{"Rok": wybrany_rok, "Miesiąc": wybrany_m_nazwa, "Zarobek": total}])
        df = pd.concat([df, nowy], ignore_index=True)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Pobierz zaktualizowany plik historii", csv, "zarobki.csv", "text/csv")

with tab2:
    st.subheader("Twoje statystyki")
    uploaded_file = st.file_uploader("Wgraj swój plik 'zarobki.csv', aby zobaczyć historię:", type="csv")
    
    if uploaded_file:
        df_hist = pd.read_csv(uploaded_file)
        widok = df_hist[df_hist["Rok"] == wybrany_rok]
        st.dataframe(widok, use_container_width=True)
        st.bar_chart(widok.set_index("Miesiąc")["Zarobek"])

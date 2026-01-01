import streamlit as st
from datetime import datetime
import pandas as pd
import os
import calendar

# Ustawienia strony
st.set_page_config(page_title="System Zarobków Multi-Year", page_icon="🏦", layout="wide")

# --- KONFIGURACJA BAZY DANYCH ---
DB_FILE = "historia_zarobkow_v2.csv"

def load_data():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        # Upewnienie się, że kolumna Rok istnieje dla starych wpisów
        if "Rok" not in df.columns:
            df["Rok"] = 2026
        return df
    return pd.DataFrame(columns=["Rok", "Miesiąc", "Podstawowe", "Nadgodziny", "Soboty", "Niedziele", "Suma Brutto"])

def save_to_db(data_row):
    df = load_data()
    # Usuwamy stary wpis dla tego samego roku i miesiąca, jeśli istnieje
    df = df[~((df["Rok"] == data_row["Rok"]) & (df["Miesiąc"] == data_row["Miesiąc"]))]
    df = pd.concat([df, pd.DataFrame([data_row])], ignore_index=True)
    df.to_csv(DB_FILE, index=False)
    return df

# --- FUNKCJA OBLICZAJĄCA GODZINY ETATOWE ---
def get_working_hours(year, month):
    # Liczy dni robocze (Pn-Pt) w danym miesiącu
    cal = calendar.Calendar()
    working_days = len([d for d in cal.itermonthdays2(year, month) if d[0] != 0 and d[1] < 5])
    # Uwaga: Ten uproszczony model nie odejmuje świąt ustawowych (np. 1 maja), 
    # ale pozwala na ręczną korektę w formularzu.
    return working_days * 8

# --- PASEK BOCZNY ---
with st.sidebar:
    st.header("📅 Wybór Okresu")
    wybrany_rok = st.selectbox("Rok:", options=[2024, 2025, 2026, 2027, 2028], index=2) # Domyślnie 2026
    
    st.divider()
    st.header("⚙️ Ustawienia Stawek")
    stawka_podstawowa = st.number_input("Stawka podstawowa (zł/h):", min_value=0.0, value=20.0)
    dodatek_nadgodziny = st.number_input("Dodatek za nadgodzinę (+ zł):", min_value=0.0, value=30.0)
    
    st.divider()
    st.subheader(f"Wymiar czasu {wybrany_rok}")
    miesiace_nazwy = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
                      "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    
    for i, m in enumerate(miesiace_nazwy, 1):
        h = get_working_hours(wybrany_rok, i)
        is_current = (wybrany_rok == datetime.now().year and i == datetime.now().month)
        style = "**👉" if is_current else ""
        st.write(f"{style} {m}: {h}h")

# --- GŁÓWNY FORMULARZ ---
aktualny_m_idx = datetime.now().month if wybrany_rok == datetime.now().year else 1
nazwa_miesiaca = miesiace_nazwy[aktualny_m_idx - 1]
domyslne_godziny = get_working_hours(wybrany_rok, aktualny_m_idx)

st.title(f"💰 Kalkulator Zarobków: {nazwa_miesiaca} {wybrany_rok}")

tab1, tab2 = st.tabs(["🧮 Obliczenia", "📊 Statystyki i Historia"])

with tab1:
    # Wybór miesiąca do obliczeń (jeśli inny niż obecny)
    m_do_obliczen = st.selectbox("Wybierz miesiąc do wpisania danych:", miesiace_nazwy, index=aktualny_m_idx-1)
    h_etatowe_wybrane = get_working_hours(wybrany_rok, miesiace_nazwy.index(m_do_obliczen) + 1)

    col1, col2 = st.columns(2)
    with col1:
        h_podstawowe = st.number_input("Godziny standardowe:", value=float(h_etatowe_wybrane), key="h_p")
        h_nadgodziny = st.number_input("Nadgodziny:", value=0.0, key="h_n")
    with col2:
        h_soboty = st.number_input("Godziny Soboty (+50%):", value=0.0, key="h_s")
        h_niedziele = st.number_input("Godziny Niedziele (+100%):", value=0.0, key="h_ni")

    # Obliczenia
    val_podst = h_podstawowe * stawka_podstawowa
    val_nadg = h_nadgodziny * (stawka_podstawowa + dodatek_nadgodziny)
    val_sob = h_soboty * (stawka_podstawowa * 1.5)
    val_niedz = h_niedziele * (stawka_podstawowa * 2.0)
    total = val_podst + val_nadg + val_sob + val_niedz

    st.divider()
    st.metric(f"Suma Brutto za {m_do_obliczen}", f"{total:,.2f} zł")

    if st.button("💾 Zapisz dane do historii"):
        nowy_wpis = {
            "Rok": wybrany_rok,
            "Miesiąc": m_do_obliczen,
            "Podstawowe": val_podst,
            "Nadgodziny": val_nadg,
            "Soboty": val_sob,
            "Niedziele": val_niedz,
            "Suma Brutto": total
        }
        save_to_db(nowy_wpis)
        st.success(f"Zapisano dane za {m_do_obliczen} {wybrany_rok}!")

with tab2:
    st.header(f"📈 Historia zarobków")
    historia_df = load_data()
    
    if not historia_df.empty:
        # Filtrowanie po roku
        widok_roku = st.selectbox("Pokaż statystyki dla roku:", options=sorted(historia_df["Rok"].unique(), reverse=True))
        filtered_df = historia_df[historia_df["Rok"] == widok_roku]
        
        if not filtered_df.empty:
            st.dataframe(filtered_df.drop(columns=["Rok"]), use_container_width=True)
            
            suma_rok = filtered_df["Suma Brutto"].sum()
            st.info(f"💰 Łączne zarobki w roku {widok_roku}: **{suma_rok:,.2f} zł**")
            
            # Wykres
            st.bar_chart(filtered_df.set_index("Miesiąc")["Suma Brutto"])
        else:
            st.warning(f"Brak danych dla roku {widok_roku}.")
    else:
        st.write("Historia jest pusta. Zapisz pierwsze dane!")

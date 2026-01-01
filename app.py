import streamlit as st
from datetime import datetime
import pandas as pd
import os

# Ustawienia strony
st.set_page_config(page_title="System Zarobków 2026", page_icon="🏦", layout="wide")

# --- PLIK BAZY DANYCH ---
DB_FILE = "historia_zarobkow.csv"

def load_data():
    if os.path.exists(DB_FILE):
        return pd.read_csv(DB_FILE)
    return pd.DataFrame(columns=["Miesiąc", "Podstawowe", "Nadgodziny", "Soboty", "Niedziele", "Suma Brutto"])

def save_to_db(data_row):
    df = load_data()
    # Sprawdź czy miesiąc już istnieje - jeśli tak, zaktualizuj go
    df = df[df["Miesiąc"] != data_row["Miesiąc"]]
    df = pd.concat([df, pd.DataFrame([data_row])], ignore_index=True)
    df.to_csv(DB_FILE, index=False)
    return df

# --- DANE O GODZINACH PRACY 2026 ---
godziny_2026 = {
    1: ("Styczeń", 160), 2: ("Luty", 160), 3: ("Marzec", 176),
    4: ("Kwiecień", 168), 5: ("Maj", 160), 6: ("Czerwiec", 168),
    7: ("Lipiec", 184), 8: ("Sierpień", 160), 9: ("Wrzesień", 176),
    10: ("Październik", 176), 11: ("Listopad", 160), 12: ("Grudzień", 160)
}

aktualny_miesiac_idx = datetime.now().month
nazwa_miesiaca, domyslne_godziny = godziny_2026[aktualny_miesiac_idx]

# --- PASEK BOCZNY ---
with st.sidebar:
    st.header("⚙️ Ustawienia Stawek")
    stawka_podstawowa = st.number_input("Stawka podstawowa (zł/h):", min_value=0.0, value=20.0)
    dodatek_nadgodziny = st.number_input("Dodatek za nadgodzinę (+ zł):", min_value=0.0, value=30.0)
    
    st.divider()
    st.header("📅 Wymiar czasu 2026")
    for idx, (m, h) in godziny_2026.items():
        style = "**👉" if idx == aktualny_miesiac_idx else ""
        st.markdown(f"{style} {m}: {h}h")

# --- GŁÓWNY FORMULARZ ---
st.title(f"💰 Kalkulator za {nazwa_miesiaca}")

tab1, tab2 = st.tabs(["🧮 Obliczenia", "📊 Statystyki Roku"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        h_podstawowe = st.number_input("Godziny standardowe:", value=float(domyslne_godziny))
        h_nadgodziny = st.number_input("Nadgodziny:", value=0.0)
    with col2:
        h_soboty = st.number_input("Godziny Soboty (+50%):", value=0.0)
        h_niedziele = st.number_input("Godziny Niedziele (+100%):", value=0.0)

    # Obliczenia
    val_podst = h_podstawowe * stawka_podstawowa
    val_nadg = h_nadgodziny * (stawka_podstawowa + dodatek_nadgodziny)
    val_sob = h_soboty * (stawka_podstawowa * 1.5)
    val_niedz = h_niedziele * (stawka_podstawowa * 2.0)
    total = val_podst + val_nadg + val_sob + val_niedz

    st.divider()
    st.metric("Suma Brutto", f"{total:,.2f} zł")

    if st.button("💾 Zapisz dane za ten miesiąc"):
        nowy_wpis = {
            "Miesiąc": nazwa_miesiaca,
            "Podstawowe": val_podst,
            "Nadgodziny": val_nadg,
            "Soboty": val_sob,
            "Niedziele": val_niedz,
            "Suma Brutto": total
        }
        save_to_db(nowy_wpis)
        st.success(f"Pomyślnie zapisano dane za {nazwa_miesiaca}!")

with tab2:
    st.header("📈 Twoje zarobki w 2026")
    historia_df = load_data()
    
    if not historia_df.empty:
        # Tabela zbiorcza
        st.dataframe(historia_df, use_container_width=True)
        
        # Wykres i podsumowanie
        suma_rok = historia_df["Suma Brutto"].sum()
        st.info(f"💰 Suma zarobków w tym roku: **{suma_rok:,.2f} zł**")
        st.bar_chart(historia_df.set_index("Miesiąc")["Suma Brutto"])
        
        if st.button("🗑️ Wyczyść historię"):
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
                st.rerun()
    else:
        st.write("Brak zapisanych danych. Kliknij 'Zapisz' w zakładce Obliczenia.")

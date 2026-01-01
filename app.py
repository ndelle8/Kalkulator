import streamlit as st
from datetime import datetime

# Ustawienia strony
st.set_page_config(page_title="Kalkulator Wypłaty 2026", page_icon="📅")

# --- DANE O GODZINACH PRACY W 2026 ROKU ---
godziny_2026 = {
    1: ("Styczeń", 160), 2: ("Luty", 160), 3: ("Marzec", 176),
    4: ("Kwiecień", 168), 5: ("Maj", 160), 6: ("Czerwiec", 168),
    7: ("Lipiec", 184), 8: ("Sierpień", 160), 9: ("Wrzesień", 176),
    10: ("Październik", 176), 11: ("Listopad", 160), 12: ("Grudzień", 160)
}

# Pobieranie aktualnego miesiąca
aktualny_miesiac_idx = datetime.now().month
nazwa_miesiaca, domyslne_godziny = godziny_2026[aktualny_miesiac_idx]

# --- PASEK BOCZNY (SIDEBAR) ---
with st.sidebar:
    st.header("📅 Kalendarz 2026")
    st.write("Wymiar czasu pracy (etat):")
    
    # Wyświetlanie tabeli godzin w boku
    for idx, (m, h) in godziny_2026.items():
        # Wyróżnienie aktualnego miesiąca
        if idx == aktualny_miesiac_idx:
            st.markdown(f"**👉 {m}: {h}h**")
        else:
            st.text(f"{m}: {h}h")
    
    st.divider()
    st.header("⚙️ Ustawienia stawek")
    stawka_podstawowa = st.number_input("Stawka podstawowa (zł/h):", min_value=0.0, value=20.0, step=1.0)

# --- GŁÓWNA SEKCJA PROGRAMU ---
st.title(f"💰 Kalkulator za {nazwa_miesiaca}")
st.info(f"Automatycznie ustawiono **{domyslne_godziny}h** dla miesiąca {nazwa_miesiaca}.")

col1, col2 = st.columns(2)

with col1:
    # Program sam podstawia 'domyslne_godziny' wyciągnięte z kalendarza
    h_podstawowe = st.number_input("Godziny standardowe:", min_value=0.0, value=float(domyslne_godziny), step=1.0)
    h_nadgodziny = st.number_input("Nadgodziny (+30zł):", min_value=0.0, value=0.0, step=1.0)

with col2:
    h_soboty = st.number_input("Godziny w soboty (+50%):", min_value=0.0, value=0.0, step=1.0)
    h_niedziele = st.number_input("Godziny w niedziele (+100%):", min_value=0.0, value=0.0, step=1.0)

# --- OBLICZENIA ---
suma_h_podstawowe = h_podstawowe * stawka_podstawowa
suma_nadgodziny = h_nadgodziny * (stawka_podstawowa + 30)
suma_soboty = h_soboty * (stawka_podstawowa * 1.5)
suma_niedziele = h_niedziele * (stawka_podstawowa * 2.0)

total_brutto = suma_h_podstawowe + suma_nadgodziny + suma_soboty + suma_niedziele

# --- WYNIKI ---
st.divider()
st.metric("Twoja wypłata całkowita (Brutto)", f"{total_brutto:,.2f} zł")

with st.expander("Pokaż szczegółowe wyliczenia"):
    st.write(f"Standard: {h_podstawowe}h x {stawka_podstawowa}zł = {suma_h_podstawowe:.2f}zł")
    if h_nadgodziny > 0: st.write(f"Nadgodziny: {h_nadgodziny}h x {stawka_podstawowa+30}zł = {suma_nadgodziny:.2f}zł")
    if h_soboty > 0: st.write(f"Soboty: {h_soboty}h x {stawka_podstawowa*1.5}zł = {suma_soboty:.2f}zł")
    if h_niedziele > 0: st.write(f"Niedziele: {h_niedziele}h x {stawka_podstawowa*2.0}zł = {suma_niedziele:.2f}zł")

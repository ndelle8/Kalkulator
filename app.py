import streamlit as st

# Ustawienia strony
st.set_page_config(page_title="Kalkulator Wypłaty PRO", page_icon="📈")

st.title("📈 Zaawansowany Kalkulator Wypłaty")
st.write("Wprowadź liczbę godzin dla poszczególnych kategorii.")

# --- SEKCJA DANYCH ---
with st.sidebar:
    st.header("Ustawienia stawek")
    stawka_podstawowa = st.number_input("Stawka podstawowa (zł/h):", min_value=0.0, value=20.0, step=1.0)
    st.info(f"""
    **Twoje stawki:**
    - Nadgodzina: {stawka_podstawowa + 30} zł
    - Sobota (+50%): {stawka_podstawowa * 1.5} zł
    - Niedziela (+100%): {stawka_podstawowa * 2.0} zł
    """)

col1, col2 = st.columns(2)

with col1:
    h_podstawowe = st.number_input("Godziny standardowe:", min_value=0.0, value=160.0, step=1.0)
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

# --- PREZENTACJA WYNIKÓW ---
st.divider()
st.subheader("Podsumowanie wynagrodzenia")

# Wyświetlanie dużego wyniku
st.metric("Suma całkowita (Brutto)", f"{total_brutto:,.2f} zł")

# Szczegółowe rozbicie w rozwijanej liście
with st.expander("Zobacz szczegółowe rozbicie"):
    st.write(f"🏠 Godziny podstawowe: {h_podstawowe}h x {stawka_podstawowa}zł = **{suma_h_podstawowe:.2f} zł**")
    st.write(f"🚀 Nadgodziny: {h_nadgodziny}h x {stawka_podstawowa + 30}zł = **{suma_nadgodziny:.2f} zł**")
    st.write(f"📅 Soboty: {h_soboty}h x {stawka_podstawowa * 1.5}zł = **{suma_soboty:.2f} zł**")
    st.write(f"☀️ Niedziele: {h_niedziele}h x {stawka_podstawowa * 2.0}zł = **{suma_niedziele:.2f} zł**")

# Wykres kołowy (opcjonalnie, dla wizualizacji)
if total_brutto > 0:
    dane_wykres = {
        "Podstawowe": suma_h_podstawowe,
        "Nadgodziny": suma_nadgodziny,
        "Soboty": suma_soboty,
        "Niedziele": suma_niedziele
    }
    # Filtrujemy tylko te, które są większe od zera
    dane_wykres = {k: v for k, v in dane_wykres.items() if v > 0}
    st.bar_chart(dane_wykres)

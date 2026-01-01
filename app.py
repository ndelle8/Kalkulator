import streamlit as st

# Ustawienia strony
st.set_page_config(page_title="Kalkulator Wypłaty", page_icon="💰")

st.title("💰 Kalkulator Miesięcznej Wypłaty")
st.write("Wprowadź dane, aby obliczyć swoje wynagrodzenie.")

# Sekcja wprowadzania danych
with st.container():
    st.subheader("Dane podstawowe")
    stawka = st.number_input("Twoja stawka godzinowa (brutto):", min_value=0.0, value=28.10, step=0.5)
    godziny = st.number_input("Suma przepracowanych godzin w miesiącu:", min_value=0.0, value=160.0, step=1.0)

# Opcjonalnie: Typ umowy (uproszczony)
typ_umowy = st.selectbox(
    "Typ umowy (do wyliczenia netto):",
    ("Tylko kwota brutto", "Umowa Zlecenie (student do 26 lat)", "Umowa Zlecenie (z ZUS)")
)

# Logika obliczeń
brutto = stawka * godziny
netto = brutto # Domyślnie

if typ_umowy == "Umowa Zlecenie (student do 26 lat)":
    netto = brutto  # Brutto = Netto na tej uludze
elif typ_umowy == "Umowa Zlecenie (z ZUS)":
    netto = brutto * 0.75  # Przybliżony przelicznik (ok. 75%)

# Wyświetlanie wyników
st.divider()
col1, col2 = st.columns(2)

with col1:
    st.metric("Suma Brutto", f"{brutto:,.2f} zł")

with col2:
    st.metric("Szacunkowe Netto", f"{netto:,.2f} zł")

# Dodatek: Prosta tabela podsumowująca
if st.button("Generuj podsumowanie"):
    st.info(f"W tym miesiącu przepracowałeś {godziny}h przy stawce {stawka} zł/h.")
import streamlit as st
import pandas as pd
from datetime import datetime
import calendar

st.set_page_config(page_title="Prywatny Kalkulator", page_icon="💰")

# --- FUNKCJE ---
def get_working_hours(year, month):
    cal = calendar.Calendar()
    return len([d for d in cal.itermonthdays2(year, month) if d[0] != 0 and d[1] < 5]) * 8

st.title("💰 Prywatny Kalkulator Zarobków")
st.info("Twoje dane nie są nigdzie gromadzone. Wszystko dzieje się w Twojej przeglądarce.")

# --- KROK 1: WGRAJ SWOJE DANE ---
st.subheader("1. Wgraj swoją historię (opcjonalnie)")
uploaded_file = st.file_uploader("Jeśli masz już zapisany plik 'zarobki.csv', wgraj go tutaj:", type="csv")

if uploaded_file is not None:
    df_history = pd.read_csv(uploaded_file)
    st.success("Wczytano Twoją historię zarobków!")
else:
    df_history = pd.DataFrame(columns=["Rok", "Miesiąc", "Suma_Brutto"])

# --- KROK 2: OBLICZENIA ---
st.divider()
st.subheader("2. Dodaj nowy miesiąc")

with st.sidebar:
    st.header("⚙️ Stawki")
    stawka_p = st.number_input("Stawka podstawowa (zł/h):", value=20.0)
    dodatek_n = st.number_input("Dodatek za nadgodzinę (+ zł):", value=30.0)
    wybrany_rok = st.selectbox("Rok:", [2025, 2026, 2027], index=1)

miesiace = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
wybrany_m = st.selectbox("Wybierz miesiąc:", miesiace, index=datetime.now().month-1)

h_etat = get_working_hours(wybrany_rok, miesiace.index(wybrany_m)+1)

c1, c2 = st.columns(2)
h_p = c1.number_input("Godziny standardowe:", value=float(h_etat))
h_n = c1.number_input("Nadgodziny:", value=0.0)
h_s = c2.number_input("Soboty (+50%):", value=0.0)
h_ni = c2.number_input("Niedziele (+100%):", value=0.0)

total = (h_p * stawka_p) + (h_n * (stawka_p + dodatek_n)) + \
        (h_s * stawka_p * 1.5) + (h_ni * stawka_p * 2.0)

st.metric("Twoja wypłata", f"{total:.2f} zł")

# --- KROK 3: AKTUALIZACJA I POBIERANIE ---
if st.button("Dodaj ten miesiąc do tabeli"):
    nowy_wpis = pd.DataFrame([{"Rok": wybrany_rok, "Miesiąc": wybrany_m, "Suma_Brutto": total}])
    # Usuń duplikat jeśli ten miesiąc już był
    df_history = df_history[~((df_history["Rok"] == wybrany_rok) & (df_history["Miesiąc"] == wybrany_m))]
    df_history = pd.concat([df_history, nowy_wpis], ignore_index=True)
    st.session_state['data'] = df_history
    st.success("Dodano do widoku poniżej!")

st.divider()
st.subheader("3. Twoja aktualna tabela")

if 'data' in st.session_state:
    display_df = st.session_state['data']
else:
    display_df = df_history

st.dataframe(display_df, use_container_width=True)

# Przycisk do pobierania gotowego pliku
csv = display_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 Pobierz i zapisz plik na telefonie",
    data=csv,
    file_name=f"zarobki_historia.csv",
    mime="text/csv",
)

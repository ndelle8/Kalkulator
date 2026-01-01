import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from datetime import datetime
import calendar

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Prywatny Kalkulator Zarobków", page_icon="🛡️")

# --- PASEK BOCZNY: USTAWIANIE BAZY DANYCH ---
with st.sidebar:
    st.header("🔑 Twoja Prywatna Baza")
    st.info("Dane będą zapisywane w Twoim własnym arkuszu Google Sheets.")
    
    # Pole na link do arkusza
    sheet_url = st.text_input(
        "Wklej link do swojego arkusza Google:",
        help="Arkusz musi mieć uprawnienia 'Każda osoba mająca link może edytować'",
        type="password" # Aby link nie był widoczny na ekranie
    )
    
    st.divider()
    st.header("⚙️ Ustawienia Stawek")
    stawka_podst = st.number_input("Stawka podstawowa (zł/h):", value=20.0)
    dodatek_nadg = st.number_input("Dodatek za nadgodzinę (+ zł):", value=30.0)
    
    wybrany_rok = st.selectbox("Rok:", [2025, 2026, 2027], index=1)

# --- FUNKCJE ---
def get_working_hours(year, month):
    cal = calendar.Calendar()
    return len([d for d in cal.itermonthdays2(year, month) if d[0] != 0 and d[1] < 5]) * 8

# --- GŁÓWNA TREŚĆ ---
if not sheet_url:
    st.warning("👈 Proszę wkleić link do arkusza Google w panelu bocznym, aby zacząć.")
    st.markdown("""
    ### Jak przygotować swój arkusz?
    1. Stwórz nowy arkusz w **Google Sheets**.
    2. W pierwszym wierszu wpisz nagłówki: `Rok, Miesiac, Suma_Brutto`
    3. Kliknij **Udostępnij** -> Zmień na **'Każda osoba mająca link'** -> Ustaw **'Edytujący'**.
    4. Skopiuj link i wklej go po lewej stronie.
    """)
else:
    try:
        # Połączenie dynamiczne z arkuszem użytkownika
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        tab1, tab2 = st.tabs(["🧮 Obliczenia", "📊 Moja Historia"])
        
        miesiace = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", 
                    "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]

        with tab1:
            m_idx = st.selectbox("Wybierz miesiąc:", miesiace, index=datetime.now().month-1)
            h_etat = get_working_hours(wybrany_rok, miesiace.index(m_idx)+1)
            
            c1, c2 = st.columns(2)
            h_p = c1.number_input("Godziny standardowe:", value=float(h_etat))
            h_n = c1.number_input("Nadgodziny:", value=0.0)
            h_s = c2.number_input("Soboty (+50%):", value=0.0)
            h_ni = c2.number_input("Niedziele (+100%):", value=0.0)

            total = (h_p * stawka_podst) + (h_n * (stawka_podst + dodatek_nadg)) + \
                    (h_s * stawka_podst * 1.5) + (h_ni * stawka_podst * 2.0)

            st.divider()
            st.metric("Suma do wypłaty", f"{total:.2f} zł")

            if st.button("💾 Zapisz w moim arkuszu"):
                # Odczyt aktualnych danych
                df = conn.read(spreadsheet=sheet_url, ttl="0s")
                # Aktualizacja lub dodanie
                df = df[~((df["Rok"] == wybrany_rok) & (df["Miesiac"] == m_idx))]
                nowy = pd.DataFrame([{"Rok": wybrany_rok, "Miesiac": m_idx, "Suma_Brutto": total}])
                updated_df = pd.concat([df, nowy], ignore_index=True)
                # Zapis
                conn.update(spreadsheet=sheet_url, data=updated_df)
                st.success("Dane zapisane w Twoim prywatnym arkuszu!")

        with tab2:
            df_hist = conn.read(spreadsheet=sheet_url, ttl="0s")
            if not df_hist.empty:
                st.dataframe(df_hist[df_hist["Rok"] == wybrany_rok], use_container_width=True)
                st.bar_chart(df_hist.set_index("Miesiac")["Suma_Brutto"])
            else:
                st.info("Twój arkusz jest jeszcze pusty.")

    except Exception as e:
        st.error(f"Błąd połączenia z arkuszem. Sprawdź czy link jest poprawny i czy arkusz ma uprawnienia 'Edytujący'.")

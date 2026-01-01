import streamlit as st
from streamlit_gsheets import GSheetsConnection
import streamlit_authenticator as stauth
from datetime import datetime
import calendar

# --- KONFIGURACJA LOGOWANIA ---
# W prawdziwej aplikacji hasła powinny być zahashowane!
users = {
    "usernames": {
        "pracownik1": {"name": "Jan Kowalski", "password": "haslo123"},
        "pracownik2": {"name": "Anna Nowak", "password": "haslo456"}
    }
}

authenticator = stauth.Authenticate(
    users, "zarobki_cookie", "signature_key", cookie_expiry_days=30
)

name, authentication_status, username = authenticator.login("main")

if authentication_status:
    st.sidebar.write(f"Witaj, {name}!")
    authenticator.logout("Wyloguj", "sidebar")

    # --- POŁĄCZENIE Z GOOGLE SHEETS ---
    conn = st.connection("gsheets", type=GSheetsConnection)

    # Funkcja pobierająca dane tylko dla zalogowanego użytkownika
    def get_user_data(user):
        df = conn.read(ttl="0s") # ttl=0s wymusza odświeżenie danych za każdym razem
        if df.empty: return df
        return df[df["Uzytkownik"] == user]

    # --- LOGIKA KALENDARZA ---
    def get_working_hours(year, month):
        cal = calendar.Calendar()
        return len([d for d in cal.itermonthdays2(year, month) if d[0] != 0 and d[1] < 5]) * 8

    # --- INTERFEJS ---
    with st.sidebar:
        wybrany_rok = st.selectbox("Rok:", [2025, 2026, 2027], index=1)
        stawka_podstawowa = st.number_input("Stawka podstawowa (zł/h):", value=20.0)
        dodatek_nadgodziny = st.number_input("Dodatek za nadgodzinę (+ zł):", value=30.0)

    tab1, tab2 = st.tabs(["🧮 Oblicz i Zapisz", "📊 Moja Historia"])

    miesiace = ["Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    
    with tab1:
        wybrany_m = st.selectbox("Miesiąc:", miesiace, index=datetime.now().month-1)
        h_etat = get_working_hours(wybrany_rok, miesiace.index(wybrany_m)+1)
        
        c1, c2 = st.columns(2)
        h_p = c1.number_input("Godziny standardowe:", value=float(h_etat))
        h_n = c1.number_input("Nadgodziny:", value=0.0)
        h_s = c2.number_input("Soboty (+50%):", value=0.0)
        h_ni = c2.number_input("Niedziele (+100%):", value=0.0)

        # Obliczenia
        total = (h_p * stawka_podstawowa) + (h_n * (stawka_podstawowa + dodatek_nadgodziny)) + \
                (h_s * stawka_podstawowa * 1.5) + (h_ni * stawka_podstawowa * 2.0)

        st.metric("Suma Brutto", f"{total:.2f} zł")

        if st.button("💾 Wyślij dane do bazy"):
            # Pobieramy aktualne dane z arkusza, żeby dodać nowy wiersz
            current_df = conn.read(ttl="0s")
            
            nowy_wiersz = pd.DataFrame([{
                "Uzytkownik": username,
                "Rok": wybrany_rok,
                "Miesiac": wybrany_m,
                "Podstawowe": h_p * stawka_podstawowa,
                "Nadgodziny": h_n * (stawka_podstawowa + dodatek_nadgodziny),
                "Soboty": h_s * stawka_podstawowa * 1.5,
                "Niedziele": h_ni * stawka_podstawowa * 2.0,
                "Suma_Brutto": total
            }])
            
            updated_df = pd.concat([current_df, nowy_wiersz], ignore_index=True)
            conn.update(data=updated_df)
            st.success("Dane zostały bezpiecznie zapisane w chmurze!")

    with tab2:
        st.subheader(f"Historia zarobków: {name}")
        history = get_user_data(username)
        if not history.empty:
            st.dataframe(history.drop(columns=["Uzytkownik"]), use_container_width=True)
            st.bar_chart(history.set_index("Miesiac")["Suma_Brutto"])
        else:
            st.info("Nie masz jeszcze żadnych zapisanych danych.")

elif authentication_status == False:
    st.error("Błędny login lub hasło.")
elif authentication_status == None:
    st.warning("Zaloguj się, aby kontynuować.")

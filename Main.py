import time
import pandas as pd
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ==========================================
#  KONFIGURATION
# ==========================================
URL = "https://booking.roadsurfer.com/rally/?currency=EUR"

# True  = Browser ist unsichtbar (Hintergrund) -> Empfohlen
# False = Du siehst den Browser arbeiten
HEADLESS_MODE = True

# True = Testmodus (nur erste 3 Städte pro Land werden geprüft)
# False = ALLES wird geprüft (für den echten Einsatz!)
TEST_MODE = True

OUTPUT_FOLDER = "Roadsurfer_Ergebnisse"


# ==========================================
#  HELPER FUNKTIONEN
# ==========================================

def format_date_de(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    except:
        return date_str


def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    if HEADLESS_MODE:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        print(">>> Browser startet im HINTERGRUND (Headless)...")
    else:
        print(">>> Browser startet sichtbar...")

    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def scan_available_countries_and_cities(driver):
    print(">>> Lade Webseite und scanne Struktur...")
    driver.get(URL)
    time.sleep(4)

    try:
        shadow = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "usercentrics-root"))).shadow_root
        btn = shadow.find_element(By.CSS_SELECTOR, "button[data-testid='uc-accept-all-button']")
        driver.execute_script("arguments[0].click();", btn)
    except:
        pass

    WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "search-input"))).click()
    time.sleep(2)

    data_map = {}
    headers = driver.find_elements(By.CSS_SELECTOR, "h6.country-name")

    for h in headers:
        country = h.text.strip()
        if not country: continue
        cities = []
        try:
            ul = driver.execute_script("return arguments[0].nextElementSibling;", h)
            if ul:
                items = ul.find_elements(By.CSS_SELECTOR, "li.station-item span.flex-none")
                cities = [item.text.strip() for item in items if item.text.strip()]
        except:
            continue

        if cities:
            data_map[country] = sorted(list(set(cities)))

    return data_map


def ask_user_for_countries(data_map):
    sorted_countries = sorted(data_map.keys())
    print("\n" + "=" * 50)
    print(" SCHRITT 1: LÄNDER AUSWAHL")
    print("=" * 50)
    for i, country in enumerate(sorted_countries, 1):
        print(f" [{i}] {country}")

    print("\nGib die Nummern ein (z.B. '1, 3') oder 'ALL' für alle.")
    user_input = input("DEINE LÄNDER: ").strip()

    selected_countries = []
    if user_input.upper() == "ALL": return sorted_countries

    try:
        parts = [p.strip() for p in user_input.split(",")]
        for p in parts:
            if p.isdigit():
                idx = int(p) - 1
                if 0 <= idx < len(sorted_countries):
                    selected_countries.append(sorted_countries[idx])
    except:
        pass
    return selected_countries


def ask_user_for_cities_in_country(country, city_list):
    print("\n" + "-" * 50)
    print(f" SCHRITT 2: STÄDTE IN {country.upper()}")
    print("-" * 50)

    for i, city in enumerate(city_list, 1):
        print(f" [{i}] {city}")

    print("\nGib die Nummern ein (z.B. '1, 2') für bestimmte Städte.")
    print("Drücke einfach [ENTER], um ALLE Städte in diesem Land zu prüfen.")

    user_input = input(f"Auswahl für {country}: ").strip()

    if not user_input or user_input.upper() == "ALL":
        if TEST_MODE:
            print(f"   -> Nehme alle (Test-Modus: nur die ersten 3)")
            return city_list[:3]
        else:
            print(f"   -> Nehme alle {len(city_list)} Städte.")
            return city_list

    selected_cities = []
    try:
        parts = [p.strip() for p in user_input.split(",")]
        for p in parts:
            if p.isdigit():
                idx = int(p) - 1
                if 0 <= idx < len(city_list):
                    selected_cities.append(city_list[idx])
    except:
        pass

    if not selected_cities:
        print("   -> Keine gültige Auswahl, nehme alle (Fallback).")
        return city_list

    print(f"   -> {len(selected_cities)} Städte ausgewählt.")
    return selected_cities


def ask_user_for_start_date():
    print("\n" + "=" * 50)
    print(" SCHRITT 3: AB WANN REISEN?")
    print("=" * 50)
    print("Format: TT.MM.JJJJ (z.B. 01.06.2026)")
    print("Drücke [ENTER] für Suche ab HEUTE.")

    while True:
        user_input = input("DATUM: ").strip()
        if not user_input:
            return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            return datetime.strptime(user_input, "%d.%m.%Y")
        except ValueError:
            print(">> Falsches Format!")


def run():
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    driver = setup_driver()

    try:
        # 1. Alles scannen
        available_data = scan_available_countries_and_cities(driver)
    except Exception as e:
        print(f"Fehler: {e}")
        driver.quit();
        return

    # 2. Länder wählen
    target_countries = ask_user_for_countries(available_data)
    if not target_countries: driver.quit(); return

    # 3. Städte wählen
    final_check_list = []
    for country in target_countries:
        all_cities = available_data[country]
        chosen_cities = ask_user_for_cities_in_country(country, all_cities)
        for city in chosen_cities:
            final_check_list.append({"city": city, "country": country})

    if not final_check_list:
        print("Keine Städte ausgewählt. Ende.")
        driver.quit();
        return

    # 4. Datum wählen
    min_start_date = ask_user_for_start_date()

    print(f"\n" + "#" * 50)
    print(f" STARTE SUCHE... ({len(final_check_list)} Stationen)")
    print(f" Ab Datum: {min_start_date.strftime('%d.%m.%Y')}")
    print(f" Modus: {'HEADLESS (Unsichtbar)' if HEADLESS_MODE else 'SICHTBAR'}")
    print("#" * 50)
    time.sleep(2)

    results = []

    try:
        driver.get(URL)

        for i, entry in enumerate(final_check_list, 1):
            start_node = entry['city']
            country = entry['country']

            print(f"\n=== [{i}/{len(final_check_list)}] PRÜFE: {start_node} ({country}) ===")
            driver.get(URL)
            time.sleep(3.5)

            try:
                # A. Start
                inp = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "search-input")))
                driver.execute_script("arguments[0].click();", inp[0])
                ActionChains(driver).send_keys(start_node).pause(1).perform()

                xpath = f"//li//span[contains(text(), '{start_node}')]"
                start_item = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                driver.execute_script("arguments[0].click();", start_item)

                time.sleep(1)
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()

                # B. One-Way Button
                oneway_btn = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".search-return .cursor-pointer")))
                driver.execute_script("arguments[0].click();", oneway_btn)
                time.sleep(2)

                # C. Ziele
                inp = driver.find_elements(By.CLASS_NAME, "search-input")
                driver.execute_script("arguments[0].click();", inp[1])
                time.sleep(2)

                all_dest = driver.find_elements(By.CSS_SELECTOR, "li.station-item span.flex-none")
                valid_destinations = sorted(list(set([s.text.strip() for s in all_dest if s.text.strip()])))
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()

                print(f"   -> {len(valid_destinations)} Ziele gefunden.")

                for end_node in valid_destinations:
                    if end_node == start_node: continue
                    print(f"      -> {end_node}...", end="", flush=True)

                    try:
                        inp = WebDriverWait(driver, 5).until(lambda d: d.find_elements(By.CLASS_NAME, "search-input"))
                        driver.execute_script("arguments[0].click();", inp[1])
                        time.sleep(0.5)
                        ActionChains(driver).send_keys(end_node).pause(1).perform()

                        xpath_end = f"//li//span[contains(text(), '{end_node}')]"
                        end_item = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath_end)))
                        driver.execute_script("arguments[0].click();", end_item)

                        time.sleep(0.5)
                        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                        driver.execute_script("document.body.click();")

                        # Prüfen ob Kalender da ist
                        try:
                            WebDriverWait(driver, 6).until_not(
                                EC.presence_of_element_located((By.CSS_SELECTOR, ".search-dates .disabled")))
                        except:
                            print(" (Nicht verfügbar)", end="")
                            continue

                        date_input = driver.find_element(By.CSS_SELECTOR, ".search-dates .search-input")
                        driver.execute_script("arguments[0].click();", date_input)

                        time.sleep(2.5)

                        all_dates_raw = []
                        for _ in range(4):
                            js_find = "return Array.from(document.querySelectorAll('div[data-testid=\"calendar-day\"]:not(.is-disabled)')).map(d => d.getAttribute('data-date')).filter(d => d !== null);"
                            found = driver.execute_script(js_find)
                            if found: all_dates_raw.extend(found)
                            try:
                                next_btn = driver.find_elements(By.CSS_SELECTOR,
                                                                "button.calendar__month-pfeil-rechts, .modal__window header button")[
                                    -1]
                                driver.execute_script("arguments[0].click();", next_btn)
                                time.sleep(0.8)
                            except:
                                break

                        if all_dates_raw:
                            all_dates_raw = sorted(list(set(all_dates_raw)))
                            first_date_str = all_dates_raw[0]
                            last_date_str = all_dates_raw[-1]

                            first_date_obj = datetime.strptime(first_date_str, "%Y-%m-%d")

                            if first_date_obj >= min_start_date:
                                von_fmt = format_date_de(first_date_str)
                                bis_fmt = format_date_de(last_date_str)

                                # Anzeige im Terminal ohne Tage
                                print(f" TREFFER! ({von_fmt} - {bis_fmt})")

                                results.append({
                                    "Land": country,
                                    "Start": start_node,
                                    "Ziel": end_node,
                                    "Von": von_fmt,
                                    "Bis": bis_fmt
                                })
                            else:
                                print(f" (Zu früh: {format_date_de(first_date_str)})")
                        else:
                            print(" (Keine Termine)", end="")

                        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                        time.sleep(0.5)

                    except Exception:
                        print(" Fehler.")
                        ActionChains(driver).send_keys(Keys.ESCAPE).perform()

            except Exception:
                print(f"   [!] Fehler bei {start_node}.")

            if results:
                pd.DataFrame(results).to_excel(os.path.join(OUTPUT_FOLDER, "rally_backup.xlsx"), index=False)

    finally:
        driver.quit()
        if results:
            date_part = min_start_date.strftime("%Y-%m-%d")

            if len(target_countries) == 1:
                name_part = target_countries[0]
            elif len(target_countries) <= 3:
                name_part = "_".join(target_countries).replace(" ", "")
            else:
                name_part = "Mehrere_Laender"

            filename = f"Roadsurfer_{name_part}_ab_{date_part}.xlsx"
            full_path = os.path.join(OUTPUT_FOLDER, filename)

            pd.DataFrame(results).to_excel(full_path, index=False)
            print(f"\nFERTIG! {len(results)} Routen gefunden.")
            print(f"Datei gespeichert: {full_path}")
        else:
            print("\nKeine passenden Routen gefunden.")


if __name__ == "__main__":
    run()
import time
import pandas as pd
import os  # <--- NEU: Für Ordner-Erstellung
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
TEST_MODE = True  # True = Prüft nur die ersten 3 Städte pro Land

# Name des Ordners, in dem die Dateien landen sollen
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
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def scan_available_countries_and_cities(driver):
    print(">>> Öffne Webseite zum Scannen der Länder...")
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
    print("\n" + "=" * 40)
    print(" VERFÜGBARE LÄNDER")
    print("=" * 40)
    for i, country in enumerate(sorted_countries, 1):
        print(f" [{i}] {country} ({len(data_map[country])} Stationen)")

    print("\nGib die Nummern ein (z.B. '1, 3') oder 'ALL' für alle.")
    user_input = input("DEINE LÄNDER-WAHL: ").strip()

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


def ask_user_for_start_date():
    print("\n" + "=" * 40)
    print(" FRÜHESTES ABHOL-DATUM")
    print("=" * 40)
    print("Ab wann möchtest du reisen? (Format: TT.MM.JJJJ)")
    print("Drücke einfach [ENTER], um ab HEUTE zu suchen.")

    while True:
        user_input = input("DATUM: ").strip()
        if not user_input:
            return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            return datetime.strptime(user_input, "%d.%m.%Y")
        except ValueError:
            print(">> Falsches Format! Bitte benutze TT.MM.JJJJ")


def run():
    # --- 0. ORDNER ERSTELLEN ---
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)
        print(f">>> Ordner '{OUTPUT_FOLDER}' erstellt.")
    else:
        print(f">>> Speichere in Ordner: '{OUTPUT_FOLDER}'")

    # 1. INITIALISIERUNG
    driver = setup_driver()
    try:
        available_data = scan_available_countries_and_cities(driver)
    except Exception as e:
        print(f"Fehler: {e}")
        driver.quit();
        return

    # 2. USER INTERACTION
    target_countries = ask_user_for_countries(available_data)
    if not target_countries: driver.quit(); return

    min_start_date = ask_user_for_start_date()
    print(f"\n>>> Suche ab dem: {min_start_date.strftime('%d.%m.%Y')}")

    final_check_list = []
    for country in target_countries:
        cities = available_data[country]
        if TEST_MODE: cities = cities[:3]
        for city in cities:
            final_check_list.append({"city": city, "country": country})

    print(f">>> {len(final_check_list)} Stationen werden geprüft.")
    time.sleep(2)

    # 3. SUCHE
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

                # B. One-Way
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

                        try:
                            WebDriverWait(driver, 6).until_not(
                                EC.presence_of_element_located((By.CSS_SELECTOR, ".search-dates .disabled")))
                        except:
                            print(" (Keine Rally)", end="")
                            continue

                        date_input = driver.find_element(By.CSS_SELECTOR, ".search-dates .search-input")
                        driver.execute_script("arguments[0].click();", date_input)
                        time.sleep(2)

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
                            first_date_obj = datetime.strptime(all_dates_raw[0], "%Y-%m-%d")

                            if first_date_obj >= min_start_date:
                                von_fmt = format_date_de(all_dates_raw[0])
                                bis_fmt = format_date_de(all_dates_raw[-1])
                                print(f" TREFFER! ({von_fmt})")
                                results.append({
                                    "Land": country,
                                    "Start": start_node,
                                    "Ziel": end_node,
                                    "Von": von_fmt,
                                    "Bis": bis_fmt
                                })
                            else:
                                print(f" (Zu früh: {format_date_de(all_dates_raw[0])})")
                        else:
                            print(" -")

                        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                        time.sleep(0.5)

                    except Exception:
                        print(" Fehler.")
                        ActionChains(driver).send_keys(Keys.ESCAPE).perform()

            except Exception:
                print(f"   [!] Fehler bei {start_node}.")

            # --- BACKUP IN ORDNER SPEICHERN ---
            if results:
                backup_path = os.path.join(OUTPUT_FOLDER, "rally_backup.xlsx")
                pd.DataFrame(results).to_excel(backup_path, index=False)

    finally:
        driver.quit()
        if results:
            date_part = min_start_date.strftime("%Y-%m-%d")
            if len(target_countries) > 3:
                country_part = "Mehrere_Laender"
            else:
                country_part = "_".join(target_countries).replace(" ", "")

            filename = f"Roadsurfer_{country_part}_ab_{date_part}.xlsx"

            # --- FINALEN PFAD ZUSAMMENBAUEN ---
            full_path = os.path.join(OUTPUT_FOLDER, filename)

            pd.DataFrame(results).to_excel(full_path, index=False)
            print(f"\nFERTIG! {len(results)} Routen gefunden.")
            print(f"Datei gespeichert unter: {full_path}")
        else:
            print("\nKeine passenden Routen gefunden.")


if __name__ == "__main__":
    run()
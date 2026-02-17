import time
import pandas as pd
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
TEST_MODE = True  # True = Nur erste 3 Treffer testen

# WÄHLE DEINE LÄNDER (Namen genau wie in der h6-Überschrift):
# ["Deutschland"] -> Nur deutsche Städte
# ["USA", "Kanada"] -> Nordamerika
# ["ALL"] -> Alles weltweit
TARGET_COUNTRIES = ["USA"]


def format_date_de(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    except:
        return date_str


def get_stations_from_popup(driver):
    """
    Liest die Stationen direkt aus dem Overlay-Popup, gruppiert nach Ländern.
    """
    stations_to_check = []

    try:
        # Popup öffnen (falls noch nicht offen)
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "search-input"))).click()
        time.sleep(1.5)

        # Wir suchen alle Länder-Container
        # Die Struktur ist: h6.country-name -> ul.stations-list -> li.station-item

        # Finde alle Länder-Überschriften
        country_headers = driver.find_elements(By.CSS_SELECTOR, "h6.country-name")

        print("\n--- Gefundene Länder im Popup ---")
        for header in country_headers:
            country_name = header.text.strip()
            print(f"• {country_name}")

            # Prüfen ob wir das Land wollen
            if "ALL" in TARGET_COUNTRIES or country_name in TARGET_COUNTRIES:
                # Finde die dazugehörige Liste (das nächste Sibling-Element)
                # XPath: Finde das ul, das direkt nach diesem h6 kommt
                try:
                    # Wir nutzen JavaScript, um das nächste Element zu finden (stabiler als XPath Sibling)
                    ul_element = driver.execute_script("return arguments[0].nextElementSibling;", header)

                    if ul_element and ul_element.tag_name == "ul":
                        items = ul_element.find_elements(By.CSS_SELECTOR, "li.station-item span.flex-none")
                        for item in items:
                            city = item.text.strip()
                            if city:
                                stations_to_check.append(city)
                except Exception as e:
                    print(f"  [!] Fehler beim Lesen von {country_name}: {e}")

        # Popup wieder schließen
        driver.execute_script("document.body.click();")

        return sorted(list(set(stations_to_check)))

    except Exception as e:
        print(f"[!] Fehler beim Stations-Scan: {e}")
        return []


def run():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    results = []

    try:
        print(">>> Starte Browser...")
        driver.get(URL)
        time.sleep(5)

        # 1. Cookie Banner
        try:
            shadow = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "usercentrics-root"))).shadow_root
            shadow.find_element(By.CSS_SELECTOR, "button[data-testid='uc-accept-all-button']").click()
            print(">>> Cookies akzeptiert.")
        except:
            pass

        # 2. Stationen scannen
        print(">>> Analysiere verfügbare Stationen...")
        check_list = get_stations_from_popup(driver)

        print(f"--------------------------------------------------")
        print(f"AUSWAHL: {', '.join(TARGET_COUNTRIES)}")
        print(f"GEFUNDEN: {len(check_list)} Stationen.")
        print(f"--------------------------------------------------")

        if not check_list:
            print("[!] Keine Stationen gefunden. Prüfe die Schreibweise der Länder.")
            return

        if TEST_MODE: check_list = check_list[:3]

        # --- HAUPTSCHLEIFE ---
        for i, start_node in enumerate(check_list, 1):
            print(f"\n=== [{i}/{len(check_list)}] PRÜFE AB: {start_node} ===")
            driver.get(URL)
            time.sleep(4)

            try:
                # A. Startort setzen
                inp = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "search-input")))
                driver.execute_script("arguments[0].click();", inp[0])
                ActionChains(driver).send_keys(start_node).pause(1).perform()

                # Gezielter Klick auf das Element im Popup
                try:
                    xpath = f"//li[contains(@class, 'station-item')]//span[contains(text(), '{start_node}')]"
                    start_item = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                    driver.execute_script("arguments[0].click();", start_item)
                except:
                    # Fallback
                    ActionChains(driver).send_keys(Keys.ENTER).perform()

                time.sleep(1)
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()

                # B. One-Way Button
                oneway_btn = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".search-return .cursor-pointer")))
                driver.execute_script("arguments[0].click();", oneway_btn)
                time.sleep(2)

                # C. Ziele auslesen (Alle möglichen, da man auch ins Ausland fahren kann)
                inp = driver.find_elements(By.CLASS_NAME, "search-input")
                driver.execute_script("arguments[0].click();", inp[1])
                time.sleep(2)

                # Wir holen ALLE Ziele aus dem Popup
                all_destinations_raw = driver.find_elements(By.CSS_SELECTOR, "li.station-item span.flex-none")
                valid_destinations = sorted(list(set([s.text.strip() for s in all_destinations_raw if s.text.strip()])))

                ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                print(f"   -> {len(valid_destinations)} Ziele gefunden.")

                for end_node in valid_destinations:
                    if end_node == start_node: continue

                    print(f"      -> Check {end_node}...", end="", flush=True)

                    try:
                        # D. Zielort setzen
                        inp = WebDriverWait(driver, 5).until(lambda d: d.find_elements(By.CLASS_NAME, "search-input"))
                        driver.execute_script("arguments[0].click();", inp[1])
                        time.sleep(0.5)

                        ActionChains(driver).send_keys(end_node).pause(1).perform()

                        # Klick auf Ziel
                        xpath_end = f"//li[contains(@class, 'station-item')]//span[contains(text(), '{end_node}')]"
                        end_item = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath_end)))
                        driver.execute_script("arguments[0].click();", end_item)

                        time.sleep(0.5)
                        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                        driver.execute_script("document.body.click();")

                        # Check ob Rally verfügbar (disabled weg?)
                        try:
                            WebDriverWait(driver, 6).until_not(
                                EC.presence_of_element_located((By.CSS_SELECTOR, ".search-dates .disabled")))
                        except:
                            print(" (Keine Rally)", end="")
                            continue

                        # E. Kalender öffnen
                        date_input = driver.find_element(By.CSS_SELECTOR, ".search-dates .search-input")
                        driver.execute_script("arguments[0].click();", date_input)
                        time.sleep(2)

                        # F. Daten sammeln
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
                            von_fmt = format_date_de(all_dates_raw[0])
                            bis_fmt = format_date_de(all_dates_raw[-1])

                            print(f" TREFFER! ({von_fmt} - {bis_fmt})")
                            results.append({
                                "Start-Land": TARGET_COUNTRIES[0] if len(TARGET_COUNTRIES) == 1 else "Mix",
                                "Start": start_node,
                                "Ziel": end_node,
                                "Von": von_fmt,
                                "Bis": bis_fmt
                            })
                        else:
                            print(" -")

                        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                        time.sleep(0.5)

                    except Exception:
                        print(" Fehler.")
                        ActionChains(driver).send_keys(Keys.ESCAPE).perform()

            except Exception:
                print(f"   [!] Fehler bei {start_node}.")

            if results: pd.DataFrame(results).to_excel("rally_backup.xlsx", index=False)

    finally:
        driver.quit()
        if results:
            fname = "roadsurfer_results.xlsx"
            if "ALL" not in TARGET_COUNTRIES:
                fname = f"roadsurfer_{'_'.join(TARGET_COUNTRIES)}.xlsx"
            pd.DataFrame(results).to_excel(fname, index=False)
            print(f"\nFERTIG! Datei: {fname}")


if __name__ == "__main__":
    run()
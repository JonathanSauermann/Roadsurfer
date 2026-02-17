import time
import pandas as pd
from datetime import datetime  # Neu für die Formatierung
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- KONFIGURATION ---
URL = "https://booking.roadsurfer.com/rally/?currency=EUR"
TEST_MODE = True


def format_date_de(date_str):
    """Wandelt YYYY-MM-DD in DD.MM.YYYY um."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
    except:
        return date_str


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
        except:
            pass

        # 2. Stationen scannen
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CLASS_NAME, "search-input"))).click()
        time.sleep(2)
        all_stations = sorted(list(
            set([s.text for s in driver.find_elements(By.CSS_SELECTOR, "li.station-item span.flex-none") if
                 s.text.strip()])))
        driver.execute_script("document.body.click();")

        check_list = all_stations if TEST_MODE else all_stations

        for start_node in check_list:
            print(f"\n=== PRÜFE AB: {start_node} ===")
            driver.get(URL)
            time.sleep(4)

            try:
                # A. Startort setzen
                inp = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CLASS_NAME, "search-input")))
                driver.execute_script("arguments[0].click();", inp[0])
                ActionChains(driver).send_keys(start_node).pause(1).perform()

                start_item = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, f"//li//span[contains(text(), '{start_node}')]")))
                driver.execute_script("arguments[0].click();", start_item)
                time.sleep(1)
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()

                # B. One-Way Button
                oneway_btn = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".search-return .cursor-pointer")))
                driver.execute_script("arguments[0].click();", oneway_btn)
                time.sleep(2)

                # C. Ziele auslesen
                inp = driver.find_elements(By.CLASS_NAME, "search-input")
                driver.execute_script("arguments[0].click();", inp[1])
                time.sleep(2)
                valid_destinations = sorted(list(
                    set([s.text for s in driver.find_elements(By.CSS_SELECTOR, "li.station-item span.flex-none") if
                         s.text.strip()])))
                ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                print(f"   -> {len(valid_destinations)} Ziele gefunden.")

                for end_node in valid_destinations:
                    if end_node == start_node: continue
                    print(f"      -> Check {end_node}...", end="", flush=True)

                    try:
                        # D. Zielort setzen
                        inp = driver.find_elements(By.CLASS_NAME, "search-input")
                        driver.execute_script("arguments[0].click();", inp[1])
                        time.sleep(0.5)
                        ActionChains(driver).send_keys(end_node).pause(1).perform()

                        end_item = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, f"//li//span[contains(text(), '{end_node}')]")))
                        driver.execute_script("arguments[0].click();", end_item)

                        time.sleep(0.5)
                        ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                        driver.execute_script("document.body.click();")

                        WebDriverWait(driver, 8).until_not(
                            EC.presence_of_element_located((By.CSS_SELECTOR, ".search-dates .disabled")))
                        time.sleep(1)

                        # E. Kalender öffnen
                        date_input = driver.find_element(By.CSS_SELECTOR, ".search-dates .search-input")
                        driver.execute_script("arguments[0].click();", date_input)
                        time.sleep(2)

                        # F. Daten sammeln & Formatieren
                        js_find = "return Array.from(document.querySelectorAll('div[data-testid=\"calendar-day\"]:not(.is-disabled)')).map(d => d.getAttribute('data-date')).filter(d => d !== null);"
                        all_dates_raw = driver.execute_script(js_find)

                        if all_dates_raw:
                            all_dates_raw = sorted(list(set(all_dates_raw)))

                            # DATUM FORMATIEREN (TT.MM.JJJJ)
                            von_formatted = format_date_de(all_dates_raw[0])
                            bis_formatted = format_date_de(all_dates_raw[-1])

                            print(f" TREFFER! ({von_formatted} bis {bis_formatted})")
                            results.append({
                                "Start": start_node,
                                "Ziel": end_node,
                                "Von": von_formatted,
                                "Bis": bis_formatted
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
            pd.DataFrame(results).to_excel("roadsurfer_final.xlsx", index=False)
            print("\nFERTIG! Daten wurden im Format TT.MM.JJJJ gespeichert.")


if __name__ == "__main__":
    run()
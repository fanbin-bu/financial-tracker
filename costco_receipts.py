import csv
import os
import pathlib
import re
import time
from datetime import datetime
from typing import List

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEBUGGER_ADDRESS = "127.0.0.1:9222"
DOWNLOAD_DIR = pathlib.Path.cwd() / "csv"
PAUSE = 1.2
CLOSE_RECEIPT_BUTTON_CSS = (
    "body > div.MuiDialog-root.MuiModal-root.css-fwbj8o > "
    "div.MuiDialog-container.MuiDialog-scrollBody.css-oxi3kn > "
    "div > div.MuiBox-root.css-10x6yif > button"
)
MODAL_SELECTOR = "#dataToPrint"


def attach_to_running_chrome() -> webdriver.Chrome:
    opts = Options()
    opts.debugger_address = DEBUGGER_ADDRESS
    driver = webdriver.Chrome(options=opts)
    driver.implicitly_wait(2)
    return driver


def go_orders_purchases(driver: webdriver.Chrome):
    url = os.getenv("COSTCO_ORDERS_URL")
    driver.get(url)
    time.sleep(PAUSE)


def try_switch_tab(driver: webdriver.Chrome, tab_text: str):
    try:
        el = driver.find_element(
            By.XPATH,
            f"//button[normalize-space()='{tab_text}'] | //a[normalize-space()='{tab_text}']",
        )
        driver.execute_script("arguments[0].click();", el)
        time.sleep(PAUSE)
    except Exception:
        pass


def get_receipt_button_container_ids(driver: webdriver.Chrome) -> List[str]:
    view_btn_containers = driver.find_elements(By.CSS_SELECTOR, "[id^='viewRecieptBtn_']")
    return [el.get_attribute("id") for el in view_btn_containers if el.get_attribute("id")]


def extract_transactions_from_page(driver: webdriver.Chrome, csv_filename: str = "costco_transactions.csv"):
    transactions = []

    try:
        # Wait for the modal to be present
        modal_element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, MODAL_SELECTOR)))

        date_spans = modal_element.find_elements(By.CSS_SELECTOR, ".date")
        receipt_date = ""
        if date_spans:
            date_text = date_spans[0].text.strip()
            try:
                parsed_date = datetime.strptime(date_text, "%m/%d/%Y")
                receipt_date = parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                receipt_date = date_text

        barcode_element = modal_element.find_element(By.CSS_SELECTOR, ".barcode .MuiBox-root:last-child")
        barcode = barcode_element.text.strip() if barcode_element else ""

        table_rows = modal_element.find_elements(By.CSS_SELECTOR, "tbody .MuiTableRow-root")

        for row in table_rows:
            cells = row.find_elements(By.CSS_SELECTOR, ".MuiTableCell-root")

            if len(cells) < 4:
                continue

            item_number_cell = cells[1].text.strip()
            if not item_number_cell or item_number_cell == "****" or not item_number_cell.isdigit():
                continue

            description = cells[2].text.strip()
            amount_text = cells[3].text.strip()

            if description.upper() in ["SUBTOTAL", "TAX", "TOTAL", "TOTAL TAX"]:
                continue

            amount = ""
            if amount_text:
                amount_clean = re.sub(r"[NY\s]", "", amount_text)
                is_refund = amount_clean.endswith("-")
                if is_refund:
                    amount_clean = amount_clean[:-1]

                try:
                    numeric_amount = float(amount_clean)
                    if is_refund:
                        numeric_amount = -numeric_amount
                    amount = f"{numeric_amount:.2f}"
                except ValueError:
                    amount = "0.00"

            if description:
                transactions.append(
                    {
                        "date": receipt_date,
                        "barcode": barcode,
                        "description": description,
                        "amount": amount,
                    }
                )

    except Exception as e:
        print(f"[error] Failed to extract transactions: {e}")

    if transactions:
        file_exists = os.path.exists(csv_filename)

        with open(csv_filename, "a", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["date", "barcode", "description", "amount"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            for transaction in transactions:
                writer.writerow(transaction)

        print(f"[info] Saved {len(transactions)} transactions to {csv_filename}")
    else:
        print("[warning] No transactions found to save")

    return transactions


def extract_receipt_transactions(driver: webdriver.Chrome, container_id: str) -> str:
    print(f"[info] Processing receipt button container id='{container_id}'")

    # Re-query to avoid stale references
    btn_css = f"#{container_id} button"
    btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, btn_css)))
    driver.execute_script("arguments[0].click();", btn)
    time.sleep(PAUSE)

    close_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, CLOSE_RECEIPT_BUTTON_CSS)))
    extract_transactions_from_page(driver, csv_filename=DOWNLOAD_DIR / "costco_transactions.csv")
    driver.execute_script("arguments[0].click();", close_btn)


def main():
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    driver = attach_to_running_chrome()

    go_orders_purchases(driver)

    try_switch_tab(driver, "Warehouse")
    for receipt_id in get_receipt_button_container_ids(driver):
        extract_receipt_transactions(driver, receipt_id)

    print("Done.")


if __name__ == "__main__":
    main()

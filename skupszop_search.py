import csv
import urllib.parse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from difflib import SequenceMatcher

# checking similarity between titles in csv and store results
def is_similar(a, b, threshold=0.8):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold

def run_skupszop_search(input_csv="books.csv", output_csv="skupszop_prices.csv", max_price=20):
    # [0] clearing the output csv
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Title", "Author", "Price", "Condition", "Link"])

    # [1] loading books from CSV
    books = []
    with open(input_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            books.append(row)

    # [2] initialize Chrome WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--window-size=1920,1080")
    # options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    results = []

    for book in books:
        title = book["Title"]
        author = book["Author"]
        print(f"Searching: {title} - {author}")

        # [3] building search URL with price filter (dynamiczne max_price)
        encoded_title = urllib.parse.quote(title)
        search_url = f"https://skupszop.pl/wyszukaj?keyword={encoded_title}&price_to={max_price}"
        driver.get(search_url)

        # [4] accepting cookies
        try:
            cookies_button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Zezwól na wszystkie')]"))
            )
            cookies_button.click()
        except TimeoutException:
            pass

        # [5] getting product titles and links from search results
        try:
            product_elements = WebDriverWait(driver, 5).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.product-card__title a"))
            )
            product_candidates = [(elem.text.strip(), elem.get_attribute("href")) for elem in product_elements]
        except TimeoutException:
            print(f"No results found for: {title}")
            continue

        # [6] filtering results by title similarity
        matching_links = [
            link for candidate_title, link in product_candidates
            if is_similar(candidate_title, title)
        ]
        if not matching_links:
            continue

        # [7] visiting matching product pages and collecting all available prices
        for link_url in matching_links:
            driver.get(link_url)
            try:
                condition_boxes = WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.condition-box"))
                )

                try:
                    product_title = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".product-right-title h1"))
                    ).text
                except TimeoutException:
                    product_title = title

                try:
                    product_author = driver.find_element(By.CSS_SELECTOR, ".product-right-title .author").text
                except:
                    product_author = author

                # iterate over condition boxes to extract prices
                for box in condition_boxes:
                    try:
                        price_element = box.find_element(By.CSS_SELECTOR, ".condition-box-head-text .price span")
                        price = price_element.text.strip()
                    except:
                        try:
                            price = box.find_element(By.CSS_SELECTOR, ".condition-box-head-text .not-available").text.strip()
                        except:
                            continue

                    if price.lower() == "brak":
                        continue

                    # checking if price <= max_price
                    try:
                        numeric_price = float(price.replace("zł", "").replace(",", ".").strip())
                        if numeric_price > max_price:
                            continue
                    except ValueError:
                        continue

                    try:
                        condition = box.find_element(By.CSS_SELECTOR, ".condition-box-head-text .condition").text.strip()
                    except:
                        condition = "unknown"

                    results.append([product_title, product_author, price, condition, link_url])

            except TimeoutException:
                continue

    # [8] saving results to CSV
    if results:
        with open(output_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(results)

    driver.quit()
    return output_csv

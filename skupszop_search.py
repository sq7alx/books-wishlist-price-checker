import csv
import urllib.parse
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from difflib import SequenceMatcher

# normalizing and matching author names (e.g. "J.K. Rowling" = "Joanne Rowling")
def normalize_name(name):
    name = name.lower()
    name =re.sub(r"[.,.]","",name)
    parts = name.split()
    return parts

def is_author_match(csv_author, skupszop_authors, threshold = 0.7):
    #authors_csv is the author name from the csv file
    #skupszop_authors is a list of possible matching authors on SkupSzop
    csv_parts = normalize_name(csv_author)
    for skupszop_author in skupszop_authors:
        skupszop_author_parts=normalize_name(skupszop_author)
        
        if set(csv_parts) == set(skupszop_author_parts):
            return True
        
        similarity = SequenceMatcher(None," ".join(csv_parts)," ".join(skupszop_author_parts)).ratio()
        if similarity>=threshold:
            return True
    return False

def is_title_similar(a, b, threshold=0.8):
    return SequenceMatcher(None, a.casefold(), b.casefold()).ratio() >= threshold

def run_skupszop_search(
    input_csv="books.csv", 
    output_csv="skupszop_prices.csv", 
    min_price=0, max_price=20, progress_callback=None, 
    result_callback=None
):
    
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

    total = len(books)

    # [2] initialize Chrome WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--headless")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    for idx, book in enumerate(books):
        title = book["Title"]
        author = book["Author"]

        # inform Streamlit which book is processing
        if progress_callback:
            try:
                progress_callback(idx + 1, total if total else 1, title, author)
            except Exception:
                pass

        print(f"Searching: {title} - {author}")

        # [3] building search URL with price filter (dynamic max_price)
        encoded_title = urllib.parse.quote(title)
        search_url = f"https://skupszop.pl/wyszukaj?keyword={encoded_title}&price_to={max_price}"
        driver.get(search_url)

        # [4] accepting cookies
        try:
            cookies_button = WebDriverWait(driver, 1).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Zezwól na wszystkie')]"))
            )
            cookies_button.click()
        except TimeoutException:
            pass

        # [5] getting product titles, authors and links from search results
        try:
            product_elements = WebDriverWait(driver, 1).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.product-card"))
            )
            product_candidates = []
            for elem in product_elements:
                try:
                    title_elem = elem.find_element(By.CSS_SELECTOR, "div.product-card__title a")
                    candidate_title = title_elem.text.strip()
                    link = title_elem.get_attribute("href")
                except:
                    continue
                try:
                    author_elems = elem.find_elements(By.CSS_SELECTOR, "div.product-card__author .author")
                    candidate_authors = [a.text.strip() for a in author_elems]
                except:
                    candidate_authors = []
                product_candidates.append((candidate_title, candidate_authors, link))
        except TimeoutException:
            print(f"No results found for: {title}")
            continue

        # [6] filtering results by title & author similarity
        matching_links = []
        for candidate_title, candidate_authors, link in product_candidates:
            if is_title_similar(candidate_title, title):
                if not candidate_authors or is_author_match(author, candidate_authors):
                    matching_links.append(link)

        if not matching_links:
            continue

        # [7] visiting matching product pages and collecting all available prices
        for link_url in matching_links:
            driver.get(link_url)
            try:
                condition_boxes = WebDriverWait(driver, 1).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.condition-box"))
                )

                try:
                    product_title = WebDriverWait(driver, 1).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".product-right-title h1"))
                    ).text
                except TimeoutException:
                    product_title = title

                try:
                    author_elems_page = driver.find_elements(By.CSS_SELECTOR, ".product-author-box .authors span.author")
                    product_authors_page = [a.text.strip() for a in author_elems_page]
                    if not is_author_match(author, product_authors_page):
                        continue
                except:
                    product_authors_page = [author]

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

                    if price.lower() == "not found":
                        continue

                    # checking if price <= max_price
                    try:
                        numeric_price = float(price.replace("PLN", "").replace(",", ".").strip())
                        if numeric_price > max_price or numeric_price < min_price:
                            continue
                    except ValueError:
                        continue

                    try:
                        condition = box.find_element(By.CSS_SELECTOR, ".condition-box-head-text .condition").text.strip()
                    except:
                        condition = "unknown"

                    row = [product_title, product_authors_page, price, condition, link_url]

                    # [8] saving results to CSV
                    with open(output_csv, "a", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow(row)
                        
                    # [9] sending result to Streamlit via callback
                    if result_callback:
                        try:
                            result_callback(row)
                        except Exception:
                            pass
                        
            except TimeoutException:
                continue

    driver.quit()
    print("Search ended")
    return output_csv

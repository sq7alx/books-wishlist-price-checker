import csv
import urllib.parse
import re
import time
import logging
import asyncio
from difflib import SequenceMatcher
from playwright.async_api import async_playwright
from app import paths as p

AUTHOR_MATCH_THRESHOLD = 0.7
TITLE_SIMILARITY_THRESHOLD = 0.8

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def normalize_name(name):
    name = name.lower()
    name = re.sub(r"[.,.]", "", name)
    return name.split()

def is_author_match(csv_author, skupszop_authors, threshold=AUTHOR_MATCH_THRESHOLD):
    #authors_csv is the author name from the csv file
    #skupszop_authors is a list of possible matching authors on SkupSzop
    csv_parts = normalize_name(csv_author)
    for skupszop_author in skupszop_authors:
        skupszop_author_parts = normalize_name(skupszop_author)
        if set(csv_parts) == set(skupszop_author_parts):
            return True
        similarity = SequenceMatcher(None, " ".join(csv_parts), " ".join(skupszop_author_parts)).ratio()
        if similarity >= threshold:
            return True
    return False

def is_title_similar(a, b, threshold=TITLE_SIMILARITY_THRESHOLD):
    return SequenceMatcher(None, a.casefold(), b.casefold()).ratio() >= threshold

async def process_book(page, book, min_price, max_price, output_csv, idx, total, progress_callback=None, result_callback=None):
    title, author = book["Title"], book["Author"]

    if progress_callback:
        try:
            progress_callback(idx + 1, total if total else 1, title, author)
        except Exception:
            pass

    logger.info(f"Searching: {title} - {author}")
    encoded_title = urllib.parse.quote(title)
    search_url = f"https://skupszop.pl/wyszukaj?keyword={encoded_title}&price_to={max_price}"

    try:
        await page.goto(search_url, timeout=15000)
    except Exception:
        logger.warning(f"Timeout for: {title}")
        return

    # zaakceptuj cookies
    try:
        await page.click("button:has-text('Zezwól na wszystkie')", timeout=5000)
    except Exception:
        pass

    try:
        product_elements = page.locator("div.product-card")
        await product_elements.first.wait_for(timeout=15000)
    except Exception:
        logger.warning(f"No results found for: {title}")
        return

    product_candidates = []
    count = await product_elements.count()
    for i in range(count):
        title_elem = product_elements.nth(i)
        try:
            candidate_title = (await title_elem.locator("div.product-card__title a").inner_text()).strip()
            link = await title_elem.locator("div.product-card__title a").get_attribute("href")
        except:
            continue
        candidate_authors = [ (await a.inner_text()).strip() for a in await title_elem.locator("div.product-card__author .author").all() ]
        product_candidates.append((candidate_title, candidate_authors, link))

    matching_links = []
    for candidate_title, candidate_authors, link in product_candidates:
        if is_title_similar(candidate_title, title):
            if not candidate_authors or is_author_match(author, candidate_authors):
                matching_links.append(link)

    if not matching_links:
        return

    for link_url in matching_links:
        product = page.locator(f'a[href="{link_url}"]').first.locator("..").locator("..")
        try:
            product_title = (await product.locator("div.product-card__title a").inner_text()).strip()
        except:
            product_title = title

        try:
            product_authors_page = [ (await a.inner_text()).strip() for a in await product.locator("div.product-card__author .author").all() ]
            if not is_author_match(author, product_authors_page):
                continue
        except:
            product_authors_page = [author]

        prices, conditions = [], []
        cond_count = await product.locator(".product-dropdown-condition-list li").count()
        for j in range(cond_count):
            li = product.locator(".product-dropdown-condition-list li").nth(j)
            try:
                price = (await li.locator(".dropdown-list-price span").inner_text()).strip()
                condition = (await li.locator(".dropdown-list-condition").inner_text()).strip()
                prices.append(price)
                conditions.append(condition)
            except:
                continue
            
        # save results to csv
        for price, condition in zip(prices, conditions):
            try:
                numeric_price = float(price.replace(",", "."))
                if numeric_price < min_price or numeric_price > max_price:
                    continue
            except ValueError:
                continue

            row = [product_title, product_authors_page, price, condition, link_url]
            with open(output_csv, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(row)
                
            # send result to Streamlit via callback
            if result_callback:
                try:
                    result_callback(row)
                except Exception:
                    pass

# main async function
async def run_skupszop_search_async(
    input_csv=p.BOOKS_CSV,
    output_csv=p.SKUPSZOP_CSV,
    min_price=0,
    max_price=20,
    progress_callback=None,
    result_callback=None,
    max_concurrent_pages=10,
):
    start_time = time.time()
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Title", "Author", "Price", "Condition", "Link"])

    with open(input_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        books = list(reader)

    total = len(books)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-animations",
                "--disable-translate",
                "--disable-background-networking",
                "--disable-application-cache",
                "--disable-software-rasterizer"
            ]
        )
        context = await browser.new_context()

        semaphore = asyncio.Semaphore(max_concurrent_pages)

        async def sem_task(book, idx):
            async with semaphore:
                page = await context.new_page()
                await process_book(page, book, min_price, max_price, output_csv, idx, total, progress_callback, result_callback)
                await page.close()

        tasks = [sem_task(book, idx) for idx, book in enumerate(books)]
        await asyncio.gather(*tasks)

        await browser.close()

    elapsed = time.time() - start_time
    logger.info(f"Search ended (elapsed: {elapsed:.2f} seconds)")
    return output_csv

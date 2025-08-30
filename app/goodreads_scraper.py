#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import csv
import time
from typing import List, Dict
import random

# [0] removing series name from book title
def extract_main_title(title_element) -> str:
    """Extract main title by removing darkGreyText span content"""
    if not title_element:
        return ""
    for span in title_element.find_all('span', class_='darkGreyText'):
        span.decompose()
    
    return title_element.get_text(strip=True)

# [1] scraping Goodreads shelf given by user (URL)
def scrape_goodreads_shelf(url: str, delay: float = 1.5, debug: bool = True, max_pages: int = 100) -> List[Dict[str, str]]:
    books = []
    page = 1

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'DNT': '1',
        'Connection': 'keep-alive'
    }

    session = requests.Session()
    session.headers.update(headers)

    # iterating pages
    while page <= max_pages:
        current_url = url if page == 1 else f"{url}&page={page}"
        if debug:
            print(f"\nFetching page {page}: {current_url}")

        try:
            response = session.get(current_url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching page {page}: {e}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')
        book_rows = soup.select('tr[id^="review_"]')

        # if no results
        if not book_rows:
            if debug:
                print(f"No books found on page {page}.")
            break
        
        # parsing
        for row in book_rows:
            book_data = extract_book_info(row)
            if book_data:
                books.append(book_data)

        next_button = soup.find('a', class_='next_page')
        if not next_button or 'disabled' in next_button.get('class', []):
            break

        time.sleep(delay + random.uniform(0.01, 0.05))
        page += 1

    return books

# [2] extracting title & author
def extract_book_info(element) -> Dict[str, str]:
    book_info = {}

    title_selectors = [
        'td.field.title a',
        'td.title a',
        '.title a',
        'a[href*="/book/show/"]',
        '.bookTitle'
    ]

    for selector in title_selectors:
        title_elem = element.select_one(selector)
        if title_elem:
            book_info['title'] = extract_main_title(title_elem)  # Extract main title only
            break

    author_selectors = [
        'td.field.author a',
        'td.author a',
        '.author a',
        'a[href*="/author/show/"]',
        '.authorName'
    ]

    for selector in author_selectors:
        author_elem = element.select_one(selector)
        if author_elem:
            book_info['author'] = author_elem.get_text(strip=True)
            break

    return book_info if 'title' in book_info else None

# [3] saving results to csv
def save_to_csv(books: List[Dict[str, str]], filename: str = 'books.csv'):
    if not books:
        return 0

    books = list(reversed(books))

    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ['Title', 'Author']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for book in books:
            writer.writerow({
                'Title': book.get('title', 'Unknown title'),
                'Author': book.get('author', 'Unknown')
            })
    return len(books)

# [4] main function used by streamlit_app.py
def run_goodreads_scraper(url: str, output_csv: str = "books.csv") -> int:
    books = scrape_goodreads_shelf(url, delay=1.5, max_pages=100, debug=False)
    if not books:
        return 0
    return save_to_csv(books, filename=output_csv)
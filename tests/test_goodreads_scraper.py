import pytest
from bs4 import BeautifulSoup
from app import goodreads_scraper as gs


# extract_main_title
def test_extract_main_title_none_returns_empty():
    assert gs.extract_main_title(None) == ""

def test_extract_main_title_strips_darkgreytext():
    html = '<a>My Book <span class="darkGreyText">(Series #1)</span></a>'
    el = BeautifulSoup(html, "html.parser").a
    assert gs.extract_main_title(el) == "My Book"

def test_extract_main_title_trims_whitespace():
    html = '<a>   Book With Spaces   </a>'
    el = BeautifulSoup(html, "html.parser").a
    assert gs.extract_main_title(el) == "Book With Spaces"


# extract_book_info
def test_extract_book_info_with_title_and_author():
    html = """
    <tr id="review_1">
        <td class="field title"><a href="/book/show/1">Book Title</a></td>
        <td class="field author"><a href="/author/show/2">Jane Doe</a></td>
    </tr>
    """
    el = BeautifulSoup(html, "html.parser")
    result = gs.extract_book_info(el)
    assert result == {"title": "Book Title", "author": "Jane Doe"}

def test_extract_book_info_without_title_returns_none():
    html = '<tr id="review_1"><td class="field author"><a>John Doe</a></td></tr>'
    el = BeautifulSoup(html, "html.parser")
    assert gs.extract_book_info(el) is None


# save_to_csv
def test_save_to_csv_creates_file(tmp_path):
    books = [
        {"title": "Book A", "author": "Author A"},
        {"title": "Book B", "author": "Author B"},
    ]
    out_file = tmp_path / "books.csv"

    count = gs.save_to_csv(books, out_file)
    assert count == 2
    content = out_file.read_text(encoding="utf-8-sig")
    assert "Book A" in content
    assert "Author B" in content

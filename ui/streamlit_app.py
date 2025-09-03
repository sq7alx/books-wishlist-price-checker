import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# Windows-only event loop setup
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


import pandas as pd
import streamlit as st
from urllib.parse import urlparse
from app import paths as p
from app.goodreads_scraper import scrape_goodreads_shelf, save_to_csv
from app.skupszop_search import run_skupszop_search


st.set_page_config(page_title="SkupSzop Books Prices", layout="wide")
st.title("Goodreads wishlist -> SkupSzop price checker")
st.caption("Find your favorite books second-hand at SkupSzop")

# https prefix
def normalize_goodreads_url(url: str) -> str:
    if not url.startswith(("https://")):
        url = "https://" + url
    return url

# check Goodreads shelf
def is_goodreads_shelf(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return "goodreads.com" in parsed.netloc and parsed.path.startswith("/review/list/")
    except:
        return False

# session state
if "running" not in st.session_state:
    st.session_state.running = False
if "stop" not in st.session_state:
    st.session_state.stop = False
if "results_df" not in st.session_state:
    st.session_state.results_df = pd.DataFrame(columns=["Title", "Author", "Price", "Condition", "Link"])

def stop_scraping():
    st.session_state.stop = True

# layout: left = controls/messages, right = table
col_left, col_right = st.columns([1, 1], gap="medium")

with col_right:
    st.subheader("Results")
    results_placeholder = st.empty()

with col_left:
    #DEFAULT_GOODREADS_URL = "https://www.goodreads.com/review/list/26367680?shelf=read"
    DEFAULT_GOODREADS_URL = "https://www.goodreads.com/review/list/149269739-ola?shelf=test"
    
    url = st.text_input("Enter the Goodreads shelf link:", placeholder=DEFAULT_GOODREADS_URL)
    min_price, max_price = st.slider("Max price (PLN):", min_value=0, max_value=100, value=(0,20))

    if not url:
        url = DEFAULT_GOODREADS_URL

    btn_col1, btn_col2 = st.columns([1, 1], gap="small")

    with btn_col1:
        # submit button
        if st.button("Submit", use_container_width=True, key="submit_btn"):
            url = normalize_goodreads_url(url)
            if not is_goodreads_shelf(url):
                st.error("Please enter a valid Goodreads shelf link!")
            else:
                st.session_state.stop = False
                st.session_state.running = True
                st.session_state.url = url
                st.session_state.min_price = min_price
                st.session_state.max_price = max_price
                st.session_state.results_df = pd.DataFrame(columns=["Title", "Author", "Price", "Condition", "Link"])

    with btn_col2:
        # stop button
        if st.session_state.running:
            st.button("Stop", on_click=stop_scraping, use_container_width=True, key="stop_btn")

    status_placeholder = st.empty()

    # scraping/searching
    if st.session_state.running and not st.session_state.stop:
        try:
            books = []
            with st.spinner("Loading your Goodreads shelf..."):
                # load books from Goodreads shelf
                shelf_books = list(scrape_goodreads_shelf(st.session_state.url, delay=1.5, max_pages=100, debug=False))
                for i, book in enumerate(shelf_books):
                    if st.session_state.stop:
                        status_placeholder.warning("Interrupted by user")
                        break
                    books.append(book)

                if not books:
                    status_placeholder.warning("No books loaded")
                else:
                    # save to CSV
                    save_to_csv(books, p.BOOKS_CSV)
                    status_placeholder.success(f"Successfully fetched {len(books)} books from Goodreads")

            if books and not st.session_state.stop:
                with st.spinner("Searching for prices on SkupSzop..."):
                    progress_bar = st.progress(0, text="SkupSzop search")

                    def update_skupszop_progress(current, total, title, author):
                        # inform Streamlit which book is processing
                        progress_bar.progress(current / total, text=f"SkupSzop search {current}/{total}: {title} ({author})")

                    # results in table
                    def update_skupszop_result(row):
                        if isinstance(row[1], list):
                            row[1] = row[1][0] if row[1] else "Unknown"
                        st.session_state.results_df.loc[len(st.session_state.results_df)] = row
                        temp_df = st.session_state.results_df.copy()
                        temp_df["Link"] = temp_df["Link"].apply(
                            lambda x: f'<a href="{x}" target="_blank" style="color:#1E90FF; text-decoration:none; font-weight:bold;">Page</a>'
                        )

                        # convert DataFrame to styled HTML table
                        table_html = temp_df.to_html(escape=False, index=False)
                        table_html = table_html.replace(
                            "<table",
                            '<table style="background-color:#1d232f; color:#ffffff; '
                            'border-radius:8px; border-collapse:separate; border-spacing:0; overflow:hidden;"',
                            1,
                        ).replace('border="1"', 'border="0"', 1) \
                         .replace("<td", '<td style="padding:8px 12px;"')

                        results_html = f'<div style="overflow-x:auto;">{table_html}</div>'
                        results_placeholder.markdown(results_html, unsafe_allow_html=True)

                    run_skupszop_search(
                        p.BOOKS_CSV,
                        p.SKUPSZOP_CSV,
                        min_price=st.session_state.min_price,
                        max_price=st.session_state.max_price,
                        progress_callback=update_skupszop_progress,
                        result_callback=update_skupszop_result
                    )

                    if st.session_state.results_df.empty:
                        progress_bar.empty()
                        status_placeholder.warning(
                            f"No books found under {st.session_state.max_price} PLN on SkupSzop."
                        )
                    else:
                        progress_bar.empty()
                        status_placeholder.success("Search ended")


        except Exception as e:
            status_placeholder.error(f"An error occurred: {e}")
        finally:
            st.session_state.running = False

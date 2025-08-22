import pandas as pd
import streamlit as st
from urllib.parse import urlparse
from goodreads_list_to_csv import scrape_goodreads_shelf, save_to_csv
from skupszop_search import run_skupszop_search


st.set_page_config(page_title="SkupSzop Books Prices", layout="wide")
st.title("Goodreads wishlist -> SkupSzop price checker")
st.caption("Find your favorite books second-hand at SkupSzop")

# adding https prefix if missing
def normalize_goodreads_url(url: str) -> str:
        if not url.startswith(("https://")):
            url = "https://" + url
        return url

# checking if url is a goodreads shelf
def is_goodreads_shelf(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return "goodreads.com" in parsed.netloc and parsed.path.startswith("/review/list/")
    except:
        return False


if "running" not in st.session_state:
    st.session_state.running = False
if "stop" not in st.session_state:
    st.session_state.stop = False
if "results_df" not in st.session_state:
    st.session_state.results_df = pd.DataFrame(columns=["Title", "Author", "Price", "Condition", "Link"])


def stop_scraping():
    st.session_state.stop = True


col1, col2 = st.columns([1, 2])

with col1:
    DEFAULT_GOODREADS_URL = "https://www.goodreads.com/review/list/26367680?shelf=read"
    url = st.text_input("Enter the Goodreads shelf link:", placeholder=DEFAULT_GOODREADS_URL)
    max_price = st.slider("Max price (PLN):", min_value=1, max_value=100, value=20)

    if not url:
        url = DEFAULT_GOODREADS_URL

    if st.button("Submit", use_container_width=True):
        url = normalize_goodreads_url(url)
        if not is_goodreads_shelf(url):
            st.error("Please enter a valid Goodreads shelf link!")
        else:
            st.session_state.stop = False
            st.session_state.running = True
            st.session_state.url = url
            st.session_state.max_price = max_price
            st.session_state.results_df = pd.DataFrame(columns=["Title", "Author", "Price", "Condition", "Link"])

    if st.session_state.running:
        st.button("Stop", on_click=stop_scraping, use_container_width=True)

with col2:
    results_placeholder = st.empty()

if st.session_state.running and not st.session_state.stop:
    try:
        books = []
        with st.spinner("Loading your Goodreads shelf..."):
            shelf_books = list(scrape_goodreads_shelf(st.session_state.url, delay=1.5, max_pages=100, debug=False))
            status_text = st.empty()
            for i, book in enumerate(shelf_books):
                if st.session_state.stop:
                    st.warning("Interrupted by user")
                    break
                books.append(book)

            if not books:
                st.warning("No books loaded")
            else:
                save_to_csv(books, "books.csv")
                st.markdown(f"""
                    <div style="background-color:#d4edda; color:#155724; padding:15px; border-radius:10px; width:50%;">
                        Successfully fetched {len(books)} books from Goodreads
                    </div>
                """, unsafe_allow_html=True)

        if books and not st.session_state.stop:
            with st.spinner("Searching for prices on SkupSzop..."):
                progress_bar = st.progress(0)
                status_text = st.empty()

                def update_skupszop_progress(current, total, title):
                    progress_bar.progress(current / total)
                    status_text.text(f"SkupSzop search {current}/{total}: {title}")

                def update_skupszop_result(row):
                    if isinstance(row[1],list):
                        row[1] = row[1][0] if row[1] else "Unknown"
                    
                    st.session_state.results_df.loc[len(st.session_state.results_df)] = row
                    temp_df = st.session_state.results_df.copy()
                    temp_df["Link"] = temp_df["Link"].apply(lambda x: f'<a href="{x}" target="_blank">Book page</a>')
                    results_placeholder.write(temp_df.to_html(escape=False, index=False), unsafe_allow_html=True)

                run_skupszop_search(
                    "books.csv",
                    "skupszop_prices.csv",
                    max_price=st.session_state.max_price,
                    progress_callback=update_skupszop_progress,
                    result_callback=update_skupszop_result
                )

                if st.session_state.results_df.empty:
                    st.warning(f"No books found under {st.session_state.max_price} PLN on SkupSzop.")
                else:
                    st.success("Search ended")

    except Exception as e:
        st.error(f"An error occurred: {e}")
    finally:
        st.session_state.running = False

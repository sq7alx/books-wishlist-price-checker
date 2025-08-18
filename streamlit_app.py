import pandas as pd
import streamlit as st
from urllib.parse import urlparse
from goodreads_list_to_csv import scrape_goodreads_shelf, save_to_csv
from skupszop_search import run_skupszop_search

st.set_page_config(page_title="SkupSzop Books Prices", layout="wide")
st.title("Goodreads wishlist -> SkupSzop price checker")
st.caption("Find your favorite books second-hand at SkupSzop")

# validate Goodreads shelf URL
def is_goodreads_shelf(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return "goodreads.com" in parsed.netloc and parsed.path.startswith("/review/list/")
    except:
        return False

# session flags (running/stop)
if "running" not in st.session_state:
    st.session_state.running = False
if "stop" not in st.session_state:
    st.session_state.stop = False

def stop_scraping():
    st.session_state.stop = True

# layout (input, output)
col1, col2 = st.columns([1, 2])

with col1:
    DEFAULT_GOODREADS_URL = "https://www.goodreads.com/review/list/26367680?shelf=read"
    url = st.text_input("Enter the Goodreads shelf link:", placeholder=DEFAULT_GOODREADS_URL)
    max_price = st.slider("Max price (PLN):", min_value=1, max_value=100, value=20)

    if not url:
        url = DEFAULT_GOODREADS_URL
    # submit button
    if st.button("Submit", use_container_width=True):
        if not is_goodreads_shelf(url):
            st.error("Please enter a valid Goodreads shelf link!")
        else:
            st.session_state.stop = False
            st.session_state.running = True
            st.session_state.url = url
            st.session_state.max_price = max_price

    # stop button
    if st.session_state.running:
        st.button("Stop", on_click=stop_scraping, use_container_width=True)

with col2:
    results_placeholder = st.empty()

# scraping logic
if st.session_state.running and not st.session_state.stop:
    try:
        books = []
        # scraping shelf Goodreads (goodreads_list_to_csv.py)
        with st.spinner("Loading your Goodreads shelf..."):
            
             # TODO: implement proper stopping of Selenium driver if user clicks Stop
             
            for i, book in enumerate(scrape_goodreads_shelf(st.session_state.url, delay=1.5, max_pages=100, debug=False)):
                if st.session_state.stop:
                    st.warning("Interrupted by user")
                    break
                books.append(book)

            if not books:
                st.warning("No books loaded")
            else:
                save_to_csv(books, "books.csv")
                st.success(f"Successfully fetched {len(books)} books from Goodreads")
        # searching for prices on Skupszop (skupszop_search.py with Selenium)
        if books and not st.session_state.stop:
            with st.spinner("Searching for prices on SkupSzop..."):
                output_file = run_skupszop_search("books.csv", "skupszop_prices.csv", max_price=st.session_state.max_price)
                df = pd.read_csv(output_file)
                if df.empty:
                    st.warning(f"No books found under {st.session_state.max_price} PLN on SkupSzop.")
                else:
                    df["Link"] = df["Link"].apply(lambda x: f'<a href="{x}" target="_blank">Book page</a>')
                    results_placeholder.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)

    except Exception as e:
        st.error(f"An error occurred: {e}")
    finally:
        st.session_state.running = False

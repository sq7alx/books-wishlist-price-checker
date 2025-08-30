import os

# storing CSV files
DATA_DIR = os.path.join(os.path.dirname(__file__), "output_data")
os.makedirs(DATA_DIR, exist_ok=True)

# paths to CSV files
BOOKS_CSV = os.path.join(DATA_DIR, "books.csv")
SKUPSZOP_CSV = os.path.join(DATA_DIR, "skupszop_prices.csv")

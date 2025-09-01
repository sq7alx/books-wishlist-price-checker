import pytest
from app import skupszop_search as ss
from difflib import SequenceMatcher


# normalize_name
def test_normalize_name_lower_and_split():
    assert ss.normalize_name("John DOE.") == ["john", "doe"]

def test_normalize_name_removes_dots_and_commas():
    assert ss.normalize_name("J., K. Rowling") == ["j", "k", "rowling"]


# is_author_match
def test_is_author_match_exact_match():
    assert ss.is_author_match("Jane Doe", ["Jane Doe"])

def test_is_author_match_different_order():
    # swapped parts
    assert ss.is_author_match("Doe Jane", ["Jane Doe"])

def test_is_author_match_similar_enough():
    # dots
    assert ss.is_author_match("J. K. Rowling", ["JK Rowling"])

def test_is_author_match_below_threshold():
    assert not ss.is_author_match("John Smith", ["Jane Doe"])


# is_title_similar
def test_is_title_similar_exact():
    assert ss.is_title_similar("The Hobbit", "The Hobbit")

def test_is_title_similar_case_insensitive():
    assert ss.is_title_similar("The Hobbit", "the hobbit")

def test_is_title_similar_partial_low_similarity():
    assert not ss.is_title_similar("Harry Potter", "Lord of the Rings")

def test_is_title_similar_above_threshold():
    # "Hobbit" vs "The Hobbit" should be similar enough
    assert ss.is_title_similar("Hobbit", "The Hobbit", threshold=0.75)
    
# debug helper for is_title_similar
def test_debug_similarity():
    ratio = SequenceMatcher(None, "Hobbit".casefold(), "The Hobbit".casefold()).ratio()
    print("similarity =", ratio)
    # test always passes but shows results
    assert isinstance(ratio, float)

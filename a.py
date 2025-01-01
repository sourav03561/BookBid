import pandas as pd
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, RDFS, OWL

# Load the CSV file
csv_file = "random_books_df.csv"  # Replace with your CSV file path
df = pd.read_csv(csv_file)

# Define namespaces
BOOK_NS = Namespace("http://example.org/book/")
AUTHOR_NS = Namespace("http://example.org/author/")
GENRE_NS = Namespace("http://example.org/genre/")

# Create an RDF graph
g = Graph()

# Define OWL Classes
Book = URIRef("http://example.org/Book")
Author = URIRef("http://example.org/Author")
Genre = URIRef("http://example.org/Genre")

g.add((Book, RDF.type, OWL.Class))
g.add((Author, RDF.type, OWL.Class))
g.add((Genre, RDF.type, OWL.Class))

# Populate the RDF graph
for _, row in df.iterrows():
    book_uri = BOOK_NS[row['title'].replace(" ", "_")]
    g.add((book_uri, RDF.type, Book))
    g.add((book_uri, RDFS.label, Literal(row['title'])))
    
    genre_uri = GENRE_NS[row['genre'].replace(" ", "_")]
    g.add((genre_uri, RDF.type, Genre))
    g.add((book_uri, URIRef("http://example.org/hasGenre"), genre_uri))
    
    for author_col in ['a_1', 'a_2', 'a_3', 'a_4', 'a_5', 'a_6']:
        if pd.notna(row[author_col]):
            author_uri = AUTHOR_NS[row[author_col].replace(" ", "_")]
            g.add((author_uri, RDF.type, Author))
            g.add((book_uri, URIRef("http://example.org/hasAuthor"), author_uri))

# Save the graph to an OWL file
g.serialize("books.owl", format="xml")

# Function to get books by author and genre
def find_related_books(book_name):
    book_uri = BOOK_NS[book_name.replace(" ", "_")]
    
    # Find authors of the given book
    authors = set(g.objects(book_uri, URIRef("http://example.org/hasAuthor")))
    
    # Find genre of the given book
    genres = set(g.objects(book_uri, URIRef("http://example.org/hasGenre")))
    
    # Find books with the same author or genre
    same_author_books = set()
    for author in authors:
        same_author_books.update(g.subjects(URIRef("http://example.org/hasAuthor"), author))
    
    same_genre_books = set()
    for genre in genres:
        same_genre_books.update(g.subjects(URIRef("http://example.org/hasGenre"), genre))
    
    # Exclude the input book
    same_author_books.discard(book_uri)
    same_genre_books.discard(book_uri)
    
    # Get labels for books
    same_author_titles = [g.value(book, RDFS.label) for book in same_author_books]
    same_genre_titles = [g.value(book, RDFS.label) for book in same_genre_books]
    
    return same_author_titles, same_genre_titles

# Example usage
book_name = "Paul II"  # Replace with a book name from your CSV
same_author, same_genre = find_related_books(book_name)
print("Books by the same author:", same_author)
print("Books in the same genre:", same_genre)

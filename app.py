from flask import Flask, request, render_template, redirect, url_for, session, flash
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from sklearn.metrics.pairwise import cosine_similarity
import joblib
import os
from rdflib import Graph, Namespace, URIRef, RDFS


# Initialize Firebase
cred = credentials.Certificate('service.json')
firebase_admin.initialize_app(cred)

# Set up Firestore
db = firestore.client()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')  # Replace in production

# Load books from CSV into memory
df_books = pd.read_csv('random_books_df.csv')
books_list = df_books[['title', 'author', 'genre']].to_dict(orient='records')

# Load TF-IDF vectorizer and matrix



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Extract user information
        name = request.form['name']
        email = request.form['email']
        city = request.form['city']
        address = request.form['address']
        phone = request.form['phone']
        password = request.form['password']
        selected_books = request.form.getlist('selected_books[]')

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Store user data in Firestore
        db.collection("users").add({
            'name': name,
            'email': email,
            'city': city,
            'address': address,
            'phone': phone,
            'password': hashed_password,
            'books': selected_books,
        })

        flash("Registration successful!", "success")
        return redirect(url_for('success'))

    return render_template('register.html', books=books_list[:300])

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form['email']
        password = request.form['password']

        # Query Firestore for the user
        users_ref = db.collection("users")
        query = users_ref.where("email", "==", email).stream()

        user = next((doc.to_dict() for doc in query), None)

        if user and check_password_hash(user['password'], password):
            session['user'] = user
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password.", "danger")

    return render_template('login.html')

@app.route("/dashboard")
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    return render_template('dashboard.html', user=session['user'])

@app.route("/edit_books", methods=["GET", "POST"])
def edit_books():
    if 'user' not in session:
        return redirect(url_for('login'))

    current_user_email = session['user']['email']
    users_ref = db.collection("users")
    query = users_ref.where("email", "==", current_user_email).stream()

    user_doc = next(query, None)
    if not user_doc:
        flash("User not found.", "danger")
        return redirect(url_for('dashboard'))

    user_data = user_doc.to_dict()
    selected_books = user_data.get('books', [])

    if request.method == "POST":
        if 'add_book' in request.form:
            selected_book_index = int(request.form['selected_book'])
            print(selected_book_index)
            selected_book = books_list[selected_book_index]
            print(selected_book)
            if selected_book not in selected_books:
                selected_books.append(selected_book['title'])
            print(selected_books)
        elif 'remove_book' in request.form:
            book_index = int(request.form['book_index'])
            if 0 <= book_index < len(selected_books):
                selected_books.pop(book_index)

        users_ref.document(user_doc.id).update({'books': selected_books})
        flash("Books updated successfully.", "success")
        return redirect(url_for('edit_books'))

    return render_template('edit_books.html', books=selected_books, csv_books=books_list[0:300])

def get_similarities_with_target(target_book, book_list):
    random_books_df = pd.read_csv('random_books_df.csv')
    tfidf_vectorizer = joblib.load("tfidf_vectorizer.pkl")
    tfidf_matrix = joblib.load("tfidf_matrix.pkl")

    try:
        target_index = random_books_df[random_books_df['title'] == target_book].index[0]
    except IndexError:
        return {}

    target_vector = tfidf_matrix[target_index]

    similarity_scores = {}
    for book in book_list:
        try:
            book_index = random_books_df[random_books_df['title'] == book].index[0]
            book_vector = tfidf_matrix[book_index]
            similarity = cosine_similarity(target_vector, book_vector.reshape(1, -1))[0][0]
            similarity_scores[book] = similarity
        except IndexError:
            similarity_scores[book] = "Not found"
    return similarity_scores

@app.route("/exchange", methods=["GET", "POST"])
def exchange():
    if 'user' not in session:
        return redirect(url_for('login'))

    current_user_email = session['user']['email']
    current_user_books = session['user'].get('books', [])
    users_ref = db.collection("users")
    books_with_users = []

    # Retrieve all users except the current logged-in user
    for doc in users_ref.stream():
        user = doc.to_dict()
        if user['email'] != current_user_email and 'books' in user:
            for book in user['books']:
                books_with_users.append({
                    "user_name": user['name'],
                    "user_email": user['email'],
                    "user_city": user['city'],
                    "user_phone": user['phone'],
                    "book_title": book,
                })

    # Compute similarity scores and sort books
    sorted_books = []
    exchange_books = []
    for b in books_with_users:
        exchange_books.append(b['book_title'])
    #print("Current User books")
    #print(current_user_books)
    #print("Exchnage books")
    #print(exchange_books)
    #print("sim target")
    #for target in exchange_books:
    #    print(target)
    #    print(current_user_books)
    #    sim = get_similarities_with_target(target,current_user_books)
    #    print(sim)
    for target_book in current_user_books:
        similarity_scores = get_similarities_with_target(target_book, [b['book_title'] for b in books_with_users])
        for book_with_user in books_with_users:
            book_title = book_with_user['book_title']
            if book_title in similarity_scores:
                book_with_user['similarity'] = similarity_scores[book_title]
                #print(similarity_scores[book_title])
            else:
                book_with_user['similarity'] = 0.0
                #print(book_with_user['similarity'])

        # Sort books based on similarity scores (descending order)
        sorted_books = sorted(books_with_users, key=lambda x: x['similarity'], reverse=True)
    
      # Default to empty string if no search term
    if request.method == "POST":
        search_query = request.form['query']
        #if search_query:
            #print(search_query)
        book_name = search_query
        print(book_name)
        book_list = exchange_books
        print(book_list)
        ontology_file = "books.owl"  # Replace with your OWL file path
        g = Graph()
        g.parse(ontology_file, format="xml")
        BOOK_NS = Namespace("http://example.org/book/")
        AUTHOR_NS = Namespace("http://example.org/author/")
        GENRE_NS = Namespace("http://example.org/genre/")

        #print(book_list)
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
    
            
        # Get labels for books
        same_author_titles = [str(g.value(book, RDFS.label)) for book in same_author_books]
        same_genre_titles = [str(g.value(book, RDFS.label)) for book in same_genre_books]
    
        # Cross-reference with the available book list
        same_author_filtered = [book for book in same_author_titles if book in book_list]
        same_genre_filtered = [book for book in same_genre_titles if book in book_list]
        print(same_author_filtered)
        print(same_genre_filtered)
        # Define namespaces (match those in your ontology)
        filtered_books = set(same_author_filtered + same_genre_filtered)

        # Filter books based on the matched search query
        books_with_users_filtered = [book for book in books_with_users if book['book_title'] in filtered_books]

        return render_template('exchange.html', books_with_users=books_with_users_filtered, current_user_books=current_user_books)

    return render_template('exchange.html', books_with_users=sorted_books,current_user_books= current_user_books)

@app.route("/send_request", methods=["POST"])
def send_request():
    if 'user' not in session:
        flash("You need to log in to send an exchange request.", "danger")
        return redirect(url_for('login'))

    # Get form data
    requested_book = request.form['requested_book']
    owner_email = request.form['owner_email']
    offer_book = request.form['offer_book']
    current_user = session['user']

    # Store the exchange request in Firestore
    db.collection("exchange_requests").add({
        'from_user': current_user['email'],
        'to_user': owner_email,
        'requested_book': requested_book,
        'offered_book': offer_book,
        'status': 'pending',
        'timestamp': firestore.SERVER_TIMESTAMP,
    })

    flash("Exchange request sent successfully!", "success")
    return redirect(url_for('exchange'))

@app.route("/requests")
def requests():
    if 'user' not in session:
        return redirect(url_for('login'))

    current_user_email = session['user']['email']

    # Fetch incoming requests
    incoming_requests = [
        {**req.to_dict(), 'id': req.id}
        for req in db.collection("exchange_requests").where("to_user", "==", current_user_email).stream()
    ]

    # Fetch outgoing requests
    outgoing_requests = [
        {**req.to_dict(), 'id': req.id}
        for req in db.collection("exchange_requests").where("from_user", "==", current_user_email).stream()
    ]
    
    users_ref = db.collection('users')

    # Create a list of unique emails for incoming requests
    incoming_emails = {req['from_user'] for req in incoming_requests}

    # Fetch user details in a single batch
    users = {user.to_dict()['email']: user.to_dict() for user in users_ref.where('email', 'in', list(incoming_emails)).stream()}

    # Add only necessary user details to incoming requests
    for incoming_request in incoming_requests:
        email = incoming_request['from_user']
        user_details = users.get(email)
        if user_details:
            incoming_request['from_user_details'] = {
                'name': user_details.get('name'),
                'phone': user_details.get('phone'),
                'address': user_details.get('address')
            }
        else:
            incoming_request['from_user_details'] = {}  # Handle missing user details gracefully

    return render_template(
        'requests.html',
        incoming_requests=incoming_requests,
        outgoing_requests=outgoing_requests
    )

@app.route("/accept_request/<request_id>", methods=["POST"])
def accept_request(request_id):
    if 'user' not in session:
        flash("You need to log in to accept an exchange request.", "danger")
        return redirect(url_for('login'))

    # Fetch the request details from Firestore
    request_ref = db.collection("exchange_requests").document(request_id)
    request_doc = request_ref.get()

    if not request_doc.exists:
        flash("Exchange request not found.", "danger")
        return redirect(url_for('requests'))

    request_data = request_doc.to_dict()

    # Get the involved users and books
    from_user_email = request_data['from_user']
    to_user_email = request_data['to_user']
    offered_book = request_data['offered_book']
    requested_book = request_data['requested_book']

    if session['user']['email'] != to_user_email:
        flash("You are not authorized to accept this request.", "danger")
        return redirect(url_for('requests'))

    # Update the status to accepted
    request_ref.update({"status": "accepted"})
    flash("Exchange request accepted!", "success")

    # Update the users' book lists
    users_ref = db.collection("users")

    # Fetch and update the 'from_user' (request initiator)
    from_user_ref = users_ref.where("email", "==", from_user_email).stream()
    from_user_doc = next(from_user_ref, None)
    if from_user_doc:
        from_user_data = from_user_doc.to_dict()
        from_user_books = from_user_data.get('books', [])

        if offered_book in from_user_books:
            from_user_books.remove(offered_book)
            from_user_books.append(requested_book)
            users_ref.document(from_user_doc.id).update({'books': from_user_books})

    # Fetch and update the 'to_user' (current user)
    to_user_ref = users_ref.where("email", "==", to_user_email).stream()
    to_user_doc = next(to_user_ref, None)
    if to_user_doc:
        to_user_data = to_user_doc.to_dict()
        to_user_books = to_user_data.get('books', [])

        if requested_book in to_user_books:
            to_user_books.remove(requested_book)
            to_user_books.append(offered_book)
            users_ref.document(to_user_doc.id).update({'books': to_user_books})

    return redirect(url_for('requests'))

@app.route("/exchange_details/<user_id>")
def show_exchange_details(user_id):
    if 'user' not in session:
        return redirect(url_for('login'))

    # Fetch user details based on the user_id (FireStore Document ID)
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()

    if not user_doc.exists:
        flash("User not found.", "danger")
        return redirect(url_for('requests'))

    user_data = user_doc.to_dict()

    # Render the exchange details template
    return render_template('exchange_details.html', user=user_data)

@app.route("/logout")
def logout():
    session.pop('user', None)
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))

@app.route("/success")
def success():
    return "User registered successfully with book information!"

if __name__ == "__main__":
    app.run(debug=True)
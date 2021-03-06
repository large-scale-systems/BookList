""" Booklist App """
import unicodedata
from jinja2 import StrictUndefined 
from flask import Flask, render_template, request, flash, redirect, session, jsonify, url_for 
from flask_debugtoolbar import DebugToolbarExtension 
from model import connect_to_db, User, Lista, List_Book, Book, PL_Book, Public_List, db
import server_helper 

app = Flask(__name__)

# This is required to use my Flask sessions and the debug toolbar 
app.secret_key = "ABC"

#This is in case Jinja2 fails, it will raise an error, otherwise it fails silenty.
app.jinja_env.undefined = StrictUndefined
app.jinja_env.auto_reload = True 


#####################################################################
# App routes 

@app.route('/')
def home():
    """ Homepage - where user is asked to login or sign-up. """

    return render_template("homepage.html")

@app.route('/register_form', methods = ['GET'])
def register_form():
    """Show form for user signup."""

    return render_template("register_form.html")

@app.route('/register_form', methods=['POST'])
def register_process():
    """ Process registration."""

    # Get form variables
    name = request.form["name"]
    last = request.form["last"]
    email = request.form["email"]
    password = request.form["password"]

    new_user = User(name=name, last=last, email=email, password=password)
    db.session.add(new_user)
    db.session.commit()

    session['user_id'] = new_user.user_id 

    flash("User %s added, please login with your credentials" % name)
    return redirect("/users/%s" % new_user.user_id)

@app.route('/login', methods=['GET'])
def login_form():
    """Show login form."""

    return render_template("login.html")

@app.route('/login', methods=['POST'])
def login_process():
    """ Process login."""

    #Get form variables
    email = request.form["email"]
    password = request.form["password"]

    user = User.query.filter_by(email=email).first()

    if not user:
        flash("No such user")
        return redirect("/login")

    if user.password != password:
        flash("Incorrect password")
        return redirect("/login")

    session["user_id"] = user.user_id

    flash("Logged in")
    return redirect("/users/%s" % user.user_id)

@app.route('/logout')
def logout():
    """Log out."""

    del session["user_id"]
    flash("Logged Out.")
    return redirect("/")


@app.route("/users/<int:user_id>")
def user_details(user_id):
    """ Show info about user, displays reading lists, add book button and suggestions."""

    user = User.query.get(user_id)
    user_lists = Lista.query.filter(Lista.user_id == user_id).all()


    count = 0 
    for ind_list in user_lists:
        for book_item in ind_list.list_books:
            if book_item.book_read:
                count = count + 1
     
    return render_template("user.html", user=user, user_lists=user_lists, count=count)


@app.route('/results', methods=['POST'])
def process_book_in_list():
    """ Handles logic if book is found in the database, otherwise redirect to gr_results route."""

    user_id=session.get("user_id")

    user_input = request.form.get('user_input')
    list_name = request.form.get('list-name')
    key_words = user_input.split(" | ")

    try: 
        #Go ahead and process title & author   
        title = key_words[0]
        author = key_words[1]

        book_in_db = server_helper.check_books(title, author)

        if book_in_db:
            list_id = Lista.query.filter(Lista.list_name == '{}'.format(list_name)).first().list_id
            book_id = Book.query.filter(Book.book_title == '{}'.format(title)).first().book_id
            server_helper.add_to_list_book(list_id, book_id)
            return redirect("/users/%s" %user_id)

        else: 
            return redirect(url_for('view_gr_results', search_box=user_input))

    except IndexError: 
        return redirect(url_for('view_gr_results', search_box=user_input))



@app.route('/gr_results', methods=["GET"])
def view_gr_results():
    """ Query the goodreads API with the user_search key words."""

    user_id=session.get("user_id")
    
    user_search = request.args.get("search_box")
    search_result = server_helper.query_gr("%s" % user_search)
    user_lists = Lista.query.filter(Lista.user_id == user_id).all()

    return render_template("results.html", user_search=user_search, search_result=search_result, user_lists=user_lists)


@app.route('/add_list', methods=['POST'])
def process_list():
    """ If user is logged in, allow them to select a list."""

    user_id = session.get("user_id")

    if user_id:
        list_name = request.form["list_name"] 
        new_list = Lista(list_name=list_name, user_id=user_id)
        db.session.add(new_list)
        db.session.commit()

    else:
        list_name = None


    flash("List added")
    return redirect("/users/%s" %user_id)



@app.route('/view_list', methods=['GET'])
def select_list():
    """If user is logged in, allow them to select a list and collect the list name they select"""
    
    user_id = session.get("user_id") 
    list_id = request.args["list-id"] 
    # list_id = Lista.query.filter_by(list_id=list_name).first().list_id

    
    return redirect("/view_list/%s" % list_id)


@app.route("/view_list/<int:list_id>")
def list_details(list_id):
    """If user is logged and selection has been made, display the books contained in a list."""

    user_id = session.get("user_id")
    list_name = Lista.query.get(list_id).list_name
    all_books = List_Book.query.filter(List_Book.list_id=='{}'.format(list_id)).all()

    all_words = [word.encode('utf-8') for word in server_helper.split_title(list_name)]

    results = set()
    for word in all_words:
        result = Public_List.query.filter(Public_List.pl_name.like('%{}%'.format(word))).all()
        for item in result:
            results.add(item) 

    # all_objs in a list of each public_list object 
    all_objs = []
    for ind_obj in results:
        all_objs.append(ind_obj)

    
    return render_template("view_list.html", list_name=list_name, list_id=list_id, all_books=all_books, all_objs=all_objs)



@app.route('/book_read', methods=['POST'])
def book_read():
    """Updates the database when someone checks a book read/unread."""

    list_book_id = int(request.form.get('id').encode('utf-8'))
    read = request.form.get('read') == "true"

    update = List_Book.query.get(list_book_id)
    update.book_read = read 
    db.session.commit()

    return render_template("book_read.html")  


@app.route('/add_book', methods=['POST'])
def add_book():
    """ If user us logged in, allow them to add a book to a list."""
    user_id=session.get("user_id")

    if user_id:
        # Collect info from the API results 
        book_title = request.form.get("title")
        book_author = request.form.get("author")
        book_cover = request.form.get("cover")

        # Collect list information 
        list_name = request.form.get("list-name")
        list_id = Lista.query.filter(Lista.list_name == '{}'.format(list_name)).first().list_id

        book_in_db = server_helper.check_books(book_title, book_author)

        if book_in_db: 
            book_id = Book.query.filter(Book.book_title == '{}'.format(book_title)).first().book_id
            server_helper.add_to_list_book(list_id, book_id)

        else:  
            add_book = server_helper.add_to_books_table(book_title, book_author, book_cover)
            new_book_id = add_book.book_id
            server_helper.add_to_list_book(list_id, new_book_id)
    else:
        new_book = None 

    flash("Book added to [add list name]")
    return redirect("/users/%s" %user_id)


@app.route('/typeahead-data.json')
def typeahead_data():
    """ Allows us to view jsonified data, includes ALL books in the books table."""

    books = Book.query.all()
    data = []
    for book in books:
        title = book.book_title
        # title = book.book_title.strip('\n')
        author = book.book_author
        input = title + " | " + author
        data.append(input)
        # data.add(book.book_author)

    return jsonify(data) 


@app.route("/ind_book/<int:book_id>")
def view_ind_books(book_id):
    """ WIP - ideally, view an individual book and it's details."""

    # show_title = Book.query.filter(Book.book_id == book_id).first().book_title
    # show_author = Book.query.filter(Book.book_id == book_id).first().book_author
    book = Book.query.filter(Book.book_id == book_id).first()
    return render_template ("ind_books.html", book_id=book_id,show_title=book.book_title, show_author=book.book_author)


#####################################################################



if __name__ == "__main__":
# We have to set debug=True here, since it has to be True at the point
# that we invoke the DebugToolbarExtension
    app.debug = False

# NOTA: will set up connection to database later
    connect_to_db(app) 

# Use the DebugToolbar
    DebugToolbarExtension(app)


    app.run(host="0.0.0.0", debug=True)


  


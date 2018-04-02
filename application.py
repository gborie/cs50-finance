from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash


from helpers import apology, login_required, lookup, usd

# global variable quote
quote = ""

# Configure application
app = Flask(__name__)


# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # Query transactions database for shares grouped by symbol from current user
    stocks = db.execute("SELECT *, SUM(shares) as total_shares FROM transactions WHERE id = :id GROUP BY symbol",
                        id=session["user_id"])
    # Set total to 0
    total = 0
    # Loop to iterate through each stock from SQL dump and add last_price and total_current_value to db
    for stock in stocks:
        symbol = stock["symbol"]
        total_shares = stock["total_shares"]
        date = stock["date"]
        data = lookup(symbol)
        value = total_shares * data["price"]
        total += value
        db.execute("UPDATE transactions SET last_price=:last_price,total_current_value=:total_current_value WHERE id = :id AND date=:date",
                   last_price=usd(data["price"]),
                   total_current_value=usd(value),
                   id=session["user_id"],
                   date=date)

    # New dump from transactions after the db was updated above
    stocks = db.execute("SELECT symbol, last_price, total_current_value, SUM(shares) as total_shares FROM transactions WHERE id = :id GROUP BY symbol",
                        id=session["user_id"])

    # dump from the users db to get the cash from the current user
    results = db.execute("SELECT cash FROM users where id = :id",
                         id=session["user_id"])

    # update cash and total variables to display on index.html
    cash = results[0]["cash"]
    total += cash
    cash = usd(cash)
    total = usd(total)

    return render_template("index.html", stocks=stocks, total=total, cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Ensure Shares was submitted
        if not request.form.get("shares"):
            return apology("must provide number of shares", 400)

        # save symbol and shares from form to variables
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Make sure the number of shares is a round digit
        if not shares.isdigit() == True:
            return apology("shares must be a number", 400)

        shares = int(shares)

        # make sure the symbol exists
        if not lookup(symbol):
            return apology("stock does not exist", 400)

        # saved down name, current price and total amount of selected symbol for selected number of shares
        data = lookup(symbol)
        name = data["name"]
        price = data["price"]
        amount = shares * float(price)

        # Query users database for cash from current username
        results = db.execute("SELECT cash FROM users WHERE id = :id",
                             id=session["user_id"])

        # save cash variable
        cash = results[0]["cash"]

        # make sure enough cash to afford stock
        if float(cash) < amount:
            return apology("Not enough cash", 400)

        # update transactions db with stock bought
        db.execute("INSERT INTO transactions (direction, symbol, shares, id, price) VALUES(:direction, :symbol, :shares, :id, :price)",
                   direction="buy",
                   symbol=request.form.get("symbol").upper(),
                   shares=request.form.get("shares"),
                   id=session["user_id"],
                   price=price)

        # update users db with cash outlay
        db.execute("UPDATE users SET cash=:cash WHERE id = :id",
                   cash=cash - amount,
                   id=session["user_id"])

        # flash bought alert
        flash('Bought!')

        # Redirect user to index page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Query database for current username
    stocks = db.execute("SELECT * FROM transactions WHERE id = :id",
                        id=session["user_id"])

    return render_template("history.html", stocks=stocks)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/price")
@login_required
def price():
    """Show stock price."""
    # saved down name, and current price
    data = lookup(quote)
    name = data["name"]
    price = data["price"]
    price = usd(price)

    return render_template("price.html", name=name, price=price)


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        # Ensure quote was submitted
        if not request.form.get("symbol"):
            return apology("must provide quote", 400)

        # Save down symbol on global variable to be used in price() function as well
        global quote
        quote = request.form.get("symbol")

        # make sure the symbol exists
        if not lookup(quote):
            return apology("stock does not exist", 400)

        return redirect("/price")
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure confirmation password was submitted
        if not request.form.get("confirmation"):
            return apology("must provide password", 400)

        # Ensure passwords are matching
        if not request.form.get("password") == request.form.get("confirmation"):
            return apology("passwords don't match", 400)

        # Store hashed password
        hash_password = generate_password_hash(request.form.get("password"))

        # Query database with all username
        results = db.execute("SELECT username, id FROM users")

        # Ensure username unique
        for result in results:
            if request.form.get("username") == result["username"]:
                return apology("username already taken, try a different one", 400)

        # Insert username and password in database
        db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                   username=request.form.get("username"),
                   hash=hash_password)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/reset", methods=["GET", "POST"])
def reset():
    """Reset password"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure new password was submitted
        if not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure new password_check was submitted
        if not request.form.get("password_check"):
            return apology("must provide password", 400)

        # Ensure passwords are matching
        if not request.form.get("password") == request.form.get("password_check"):
            return apology("passwords don't match", 400)

        # Store hashed password
        hash_password = generate_password_hash(request.form.get("password"))

        # Update password in database
        db.execute("UPDATE users SET hash=:hash WHERE id = :id",
                   hash=hash_password,
                   id=session["user_id"])

        flash('Password updated')

        # Redirect user to home page
        return redirect("/")

    # Redirect user to login form
    else:
        return render_template("reset.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Ensure Shares was submitted
        if not request.form.get("shares"):
            return apology("must provide number of shares", 400)

        # saved down symbol and shares
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

        # Make sure the number of shares is a round digit
        if not shares.isdigit() == True:
            return apology("shares must be a number", 400)

        shares = int(shares)

        # make sure the symbol exists
        if not lookup(symbol):
            return apology("stock does not exist", 400)

        # saved down name, current price and total amount of symbol for selected number of shares
        data = lookup(symbol)
        name = data["name"]
        price = data["price"]
        amount = shares * float(price)

        # Query transactions database for shares grouped by symbol from current user
        stocks = db.execute("SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE id = :id and symbol = :symbol GROUP by symbol",
                            id=session["user_id"],
                            symbol=symbol)

        # Save down total shares owned for current symbol
        total_shares = stocks[0]["total_shares"]

        # Make sure we don't sell more shares that what we own
        if shares > int(total_shares):
            return apology("Trying to sell more shares than owned", 400)

        # Query users database for cash from current username
        results = db.execute("SELECT cash FROM users WHERE id = :id",
                             id=session["user_id"])

        # save cash variable
        cash = results[0]["cash"]

        # update transactions db with shares sold
        db.execute("INSERT INTO transactions (direction, symbol, shares, id, price, last_price) VALUES(:direction, :symbol, :shares, :id, :price, :last_price)",
                   direction="sell",
                   symbol=symbol.upper(),
                   shares=-shares,
                   id=session["user_id"],
                   price=price,
                   last_price=price)

        # update users db with cash inlay
        db.execute("UPDATE users SET cash=:cash WHERE id = :id",
                   cash=cash + amount,
                   id=session["user_id"])

        # flash sold alert
        flash('Sold!')

        # Redirect user to index page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        stocks = db.execute("SELECT *, SUM(shares) as total_shares FROM transactions WHERE id = :id GROUP BY symbol",
                            id=session["user_id"])

        return render_template("sell.html", stocks=stocks)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
import os
import sqlalchemy
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

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


class SQL(object):
    def __init__(self, url):
        try:
            self.engine = sqlalchemy.create_engine(url)
        except Exception as e:
            raise RuntimeError(e)

    def execute(self, text, *multiparams, **params):
        try:
            statement = sqlalchemy.text(
                text).bindparams(*multiparams, **params)
            result = self.engine.execute(
                str(statement.compile(compile_kwargs={"literal_binds": True})))
            # SELECT
            if result.returns_rows:
                rows = result.fetchall()
                return [dict(row) for row in rows]
            # INSERT
            elif result.lastrowid is not None:
                return result.lastrowid
            # DELETE, UPDATE
            else:
                return result.rowcount
        except sqlalchemy.exc.IntegrityError:
            return None
        except Exception as e:
            raise RuntimeError(e)


db = SQL("sqlite:///finance.db")
# conn = sqlite3.connect('finance.db')
# db = conn.cursor()


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Get user id, query for cash balance and assign to cash
    userid = session["user_id"]
    cash = db.execute(
        "SELECT cash FROM users WHERE id = :userid", userid=userid)
    cash = cash[0]["cash"]
    gtotal = cash

    # Query for portfolio
    stocks = db.execute("""SELECT symbol, shares FROM
        (SELECT symbol, sum(shares) AS \"shares\" FROM transactions WHERE id = :userid GROUP BY symbol)
        WHERE shares > 0""", userid=userid)

    # Reorganize stocks and append to list as a dict obj
    portfolio = []
    for i in stocks:
        stock = lookup(i["symbol"])
        price = usd(stock["price"])
        total = usd(stock["price"] * i["shares"])
        temp = {
            "symbol": stock["symbol"],
            "name": stock["name"],
            "shares": i["shares"],
            "price": price,
            "total": total
        }
        gtotal += (stock["price"] * i["shares"])
        portfolio.append(temp)

    # Convert to USD format
    cash = usd(cash)
    gtotal = usd(gtotal)

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("index.html", stocks=portfolio, cash=cash, gtotal=gtotal)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Get user id, query for cash balance and assign to cash
        userid = session["user_id"]
        cash = db.execute(
            "SELECT cash FROM users WHERE id = :userid", userid=userid)
        cash = cash[0]["cash"]

        # Query the stock
        stock = lookup(request.form.get("symbol"))

        # Ensure stock symbol is valid
        if not stock:
            return apology("must enter a valid stock symbol", 400)

        symbol = stock["symbol"]
        price = stock["price"]
        shares = request.form.get("shares")

        # Ensure shares is an integer
        if shares.isdigit() is False:
            return apology("must enter an integer", 400)

        # Convert shares to int and total to negative number
        shares = int(shares)
        total = price * shares * -1

        # Ensure shares is a positive integer
        if shares < 0:
            return apology("must enter a positive integer", 400)

        # Ensure stock symbol was entered
        if not request.form.get("symbol") or not request.form.get("shares"):
            return apology("must enter stock symbol and number of shares", 403)

        # Ensure the user can afford it
        if cash < total * -1:
            return apology("insufficient balance", 403)

        # Buy
        else:
            db.execute('INSERT INTO transactions (id, symbol, date, shares, price) VALUES (:userid, :symbol, datetime(), :shares, :price)',
                       userid=userid, symbol=symbol, shares=shares, price=price)
            db.execute('UPDATE users SET cash = :cash + :total WHERE id = :userid',
                       cash=cash, total=total, userid=userid)

            # Redirect user to home page
            return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Get user id, query for cash balance and assign to cash
    userid = session["user_id"]

    # Query for all transactions
    records = db.execute(
        "SELECT date, symbol, shares, price FROM transactions WHERE id = :userid ORDER BY date DESC", userid=userid)

    # Convert price to USD
    for record in records:
        record["price"] = usd(record["price"])

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("history.html", records=records)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

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


@app.route("/pwchange", methods=["GET", "POST"])
def pwchange():
    """Change password"""
    # Get user id, query for cash balance and assign to cash
    userid = session["user_id"]

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure passwords were submitted
        if not request.form.get("password") or not request.form.get("newpassword") or not request.form.get("confirmation"):
            return apology("must fill out all fields", 403)

        # Ensure new password and confirmation matches
        if request.form.get("newpassword") != request.form.get("confirmation"):
            return apology("passwords do not match", 403)

        # Query database for user info
        user = db.execute(
            "SELECT * FROM users WHERE id = :userid", userid=userid)

        # Ensure password is correct
        if not check_password_hash(user[0]["hash"], request.form.get("password")):
            return apology("invalid password", 403)

        # Encrypt password
        pw = request.form.get("newpassword")
        pwhash = generate_password_hash(pw)

        # Change password
        db.execute('UPDATE users SET hash = :pwhash WHERE id = :userid',
                   pwhash=pwhash, userid=userid)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("pwchange.html")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        stock = request.form.get("symbol")
        stock = lookup(stock)

        # Ensure stock symbol was entered
        if not request.form.get("symbol"):
            return apology("must enter stock symbol", 400)

        # Ensure stock symbol is valid
        if stock is None:
            return apology("must enter a valid stock symbol", 400)

        # Parse output from lookup() and return as POST
        name = stock["name"]
        symbol = stock["symbol"]
        price = usd(stock["price"])
        return render_template("quote.html", name=name, symbol=symbol, price=price)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username and password were submitted
        if not request.form.get("username") or not request.form.get("password"):
            return apology("must provide username and password", 400)

        # Ensure password and confirmation matches
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        # Encrypt password
        pw = request.form.get("password")
        pwhash = generate_password_hash(pw)

        # Create new user
        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :pwhash)",
                            username=request.form.get("username"), pwhash=pwhash)

        # If username is already in use
        if not result:
            return apology("Username is taken", 400)

        else:
            userid = db.execute("SELECT * FROM users WHERE username = :username",
                                username=request.form.get("username"))

            # Remember which user has logged in
            session["user_id"] = userid[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # Get user id, query for cash balance and assign to cash
    userid = session["user_id"]
    cash = db.execute(
        "SELECT cash FROM users WHERE id = :userid", userid=userid)
    cash = cash[0]["cash"]

    # Query for portfolio
    stocks = db.execute("""SELECT symbol, shares FROM
        (SELECT symbol, sum(shares) AS \"shares\" FROM transactions WHERE id = :userid GROUP BY symbol)
        WHERE shares > 0""", userid=userid)

    # Create empty list
    portfolio = []

    # Create dict objects and append to list
    for i in stocks:
        stock = lookup(i["symbol"])
        temp = {
            "symbol": stock["symbol"],
            "name": stock["name"],
            "shares": i["shares"],
            "price": stock["price"],
            "total": stock["price"] * i["shares"]}
        portfolio.append(temp)

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("sell.html", stocks=portfolio)

    # Store user input value, call lookup(), and parse output
    stock = request.form.get("symbol")
    stock = lookup(stock)
    symbol = stock["symbol"]
    price = stock["price"]
    shares = request.form.get("shares")

    # Ensure shares is an integer
    if shares.isdigit() is False:
        return apology("must enter an integer", 400)

    # Convert shares to integer
    shares = int(shares)

    # Calculate total price
    total = price * shares

    # Ensure positive number was entered for shares
    if shares < 0:
        return apology("must enter a positive integer", 400)

    # Ensure stock symbol was entered
    if not request.form.get("symbol") or not request.form.get("shares"):
        return apology("must enter stock symbol and number of shares", 400)

    # Ensure stock symbol is valid
    if not stock:
        return apology("must enter a valid stock symbol", 400)

    # Query for stock to be sold
    sell = db.execute("""SELECT * FROM (SELECT symbol, sum(shares) AS \"shares\"
        FROM transactions WHERE id = :userid GROUP BY symbol)
        WHERE symbol = :symbol""", userid=userid, symbol=symbol)

    # Ensure the entered number of shares is valid
    if sell[0]["shares"] < shares:
        return apology("too many shares", 400)

    # Convert shares to negative to enter into database
    shares *= -1

    db.execute('INSERT INTO transactions (id, symbol, date, shares, price) VALUES (:userid, :symbol, datetime(), :shares, :price)',
               userid=userid, symbol=symbol, shares=shares, price=price)
    db.execute('UPDATE users SET cash = :cash + :total WHERE id = :userid',
               cash=cash, total=total, userid=userid)

    # Redirect user to home page
    return redirect("/")


@app.route("/leaderboard")
@login_required
def leaderboard():
    """Top players"""
    # retrieve top 10 players
    players = db.execute(
        "SELECT users.username, users.cash FROM users INNER JOIN transactions ON transactions.id = users.id GROUP BY users.username ORDER BY users.cash DESC LIMIT 10;")

    # Reorganize stocks and append to list as a dict obj
    leaders = []
    num = 0
    for player in players:
        balance = usd(player["cash"])
        num = num + 1
        temp = {
            "rank": num,
            "name": player["username"],
            "balance": balance
        }
        leaders.append(temp)

    # User reached route via GET (as by clicking a link or via redirect)
    if request.method == "GET":
        return render_template("leaderboard.html", leaders=leaders)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)


if __name__ == '__main__':
    app.debug = True
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

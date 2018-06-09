import csv
import urllib.request
from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Renders message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
                         ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """Require log in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol, queryType):
    """Look up quote for symbol."""
    apikey = "TN3OWU38ZSMDF9WH"

    # reject symbol if it starts with caret
    if symbol.startswith("^"):
        return None

    # Reject symbol if it contains comma
    if "," in symbol:
        return None

    if queryType == "stock":
        # Query Alpha Vantage for quote instead
        # https://www.alphavantage.co/documentation/
        try:

            # GET CSV
            url = f"https://www.alphavantage.co/query?apikey={apikey}&datatype=csv&function=TIME_SERIES_INTRADAY&interval=1min&symbol={symbol}"
            webpage = urllib.request.urlopen(url)

            # Parse CSV
            datareader = csv.reader(
                webpage.read().decode("utf-8").splitlines())

            # Ignore first row
            next(datareader)

            # Parse second row
            row = next(datareader)

            # Ensure stock exists
            try:
                price = float(row[4])
            except:
                return None

            symbolU = symbol.upper()

            # Return stock's name (as a str), price (as a float), and (uppercased) symbol (as a str)
            return {
                "name": symbolU,  # for backward compatibility with Yahoo
                "price": price,
                "symbol": symbolU,
                "type": queryType
            }

        except:
            return None

    elif queryType == "crypto":
        # Query Alpha Vantage for quote instead
        # https://www.alphavantage.co/documentation/
        try:

            # GET CSV
            url = f"https://www.alphavantage.co/query?apikey={apikey}&datatype=csv&function=DIGITAL_CURRENCY_INTRADAY&market=USD&symbol={symbol}"

            webpage = urllib.request.urlopen(url)

            # Parse CSV
            datareader = csv.reader(
                webpage.read().decode("utf-8").splitlines())

            # Ignore first row
            next(datareader)

            # Parse second row
            row = next(datareader)

            # for backward compatibility with Yahoo
            symbolU = symbol.upper()

            # Ensure stock exists
            try:
                price = round(float(row[1]), 2)
            except:
                return None

            # Return stock's name (as a str), price (as a float), and (uppercased) symbol (as a str)
            return {
                "name": symbolU,
                "price": price,
                "symbol": symbolU,
                "type": queryType
            }

        except:
            return None
    else:
        return None


def usd(value):
    """Formats value as USD."""
    return f"${value:,.2f}"

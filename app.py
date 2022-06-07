import os
import datetime

from jinja2 import Environment, FileSystemLoader

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd



# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


app.jinja_env.globals.update(usd=usd)

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    if request.method == "POST":
        return redirect("/sell")

    else:
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        stocks = db.execute("SELECT * FROM account WHERE id = ?", session["user_id"])

        for i in stocks:
            s = i["symbol"]
            q = i["quantity"]
            p = lookup(s)
            current_price = p["price"]
            db.execute("UPDATE account SET current_price = ? WHERE id = ? AND symbol = ?", current_price, session["user_id"], s)
        nav = db.execute("SELECT total FROM account WHERE id=?", session["user_id"])
        return render_template("index.html", cash=cash, stocks=stocks, nav=nav)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        balance = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
        b = balance[0]["cash"]
        sym=request.form.get("symbol").upper()
        stock = lookup(sym)
        price=stock["price"]
        q=request.form.get("quantity", type=int)
        total=price*q
        if total <= b:
            y = db.execute("SELECT * FROM account WHERE symbol=? AND id=?", sym, session["user_id"])
            t = datetime.datetime.now()
            t = t.strftime("%x")
            if y:
                db.execute("UPDATE account SET quantity = quantity + ? WHERE symbol=? AND id=?", q, sym, session["user_id"])
                db.execute("UPDATE users SET cash = cash - ? WHERE id=?", total, session["user_id"])
                db.execute("INSERT INTO history (symbol, bought, day, price, id) VALUES(?, ?, ?, ?, ?)", sym, q, t, price, session["user_id"])
            else:
                db.execute("INSERT INTO account (symbol, quantity, id, current_price) VALUES (?, ?, ?, ?) ", sym, q, session["user_id"], price)
                db.execute("UPDATE users SET cash = cash - ? WHERE id=?", total, session["user_id"])
                db.execute("INSERT INTO history (symbol, bought, day, price, id) VALUES(?, ?, ?, ?, ?)", sym, q, t, price, session["user_id"])

        else:
            return apology("insufficient funds")
        return redirect("/")
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    rows = db.execute ("SELECT * FROM history WHERE id = ? ", session["user_id"])
    return render_template("history.html", rows=rows)


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
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "POST":
        symbol = request.form.get("symbol")
        q = lookup(symbol)
        return render_template("quoted.html", q=q)
    else:
        return render_template("quote.html")
    """Get stock quote."""
    return apology("TODO")

@app.route("/quoted", methods=["GET", "POST"])
@login_required
def quoted():
    if request.method == "POST":
        sym = request.form.get("symbol")
        price = request.form.get("price")
        return render_template("buy.html", sym=sym, price=price)
    else:
        return render_template("quoted.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not request.form.get("rusername"):
            return apology("USERNAME?")
        elif not request.form.get("rpassword"):
            return apology("password required")
        elif request.form.get("rpassword") != request.form.get("password_confirm"):
            return apology("password doesnt match")
        elif db.execute("SELECT * FROM users WHERE username = ? ", request.form.get("rusername")):
            return apology("username exists")
        else:
            pw = request.form.get("rpassword")
            h = generate_password_hash(pw)
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get("rusername"), h)
            rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("rusername"))
            session["user_id"] = rows[0]["id"]
            return redirect("/")

    else:
        return render_template("register.html")





@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "POST":
        quantity = request.form.get("quantity", type=int)
        symbol = request.form.get("symbol").upper()
        stock = db.execute("SELECT * from account WHERE id = ? AND symbol = ?", session["user_id"], symbol)
        q_real = stock[0]["quantity"]
        q_new = q_real - quantity
        current_price = lookup(symbol)
        p=current_price["price"]
        v = p*quantity
        t = datetime.datetime.now()
        t = t.strftime("%x")
        if quantity < q_real:
            db.execute("UPDATE account SET quantity = ?, current_price = ? WHERE id = ? AND symbol = ?", q_new, p, session["user_id"], symbol)
            db.execute("UPDATE users SET cash = cash + ? WHERE id=?", v, session["user_id"])
            db.execute("INSERT INTO history(symbol, day, price, sold, id) VALUES(?, ?, ?, ?, ?)", symbol, t, p, quantity, session["user_id"])
            return redirect ("/")
        elif quantity == q_real:
            db.execute("UPDATE users SET cash = cash + ? WHERE id=?", v, session["user_id"])
            db.execute("DELETE FROM account WHERE symbol = ?", symbol)
            db.execute("INSERT INTO history(symbol, day, price, sold, id) VALUES(?, ?, ?, ?, ?)", symbol, t, p, quantity, session["user_id"])
            return redirect ("/")
        else:
            return apology("quantity exceeds account balance")

    else:
        return render_template("sell.html")

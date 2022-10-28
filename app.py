from cs50 import SQL
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import cash_flow_report, is_strong, login_required, get_next_id, calculate_future_date, usd, percentage, cash_flow_report, Bank, Loan, Amortization

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd
app.jinja_env.filters["percentage"] = percentage


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///loMap.db")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# LOANS
@app.route("/")
@login_required
def index():
    user_id = session["user_id"]
    # Query database for username
    user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
    name = user["username"]
    # info for filters

    ids = db.execute("SELECT user_loan_id FROM loans WHERE user_id = ?", user_id)

    banks = db.execute("SELECT DISTINCT banks.bank FROM banks JOIN loans ON loans.bank_id = banks.id WHERE loans.user_id = ?", user_id)
    banks.sort(key=lambda x:x["bank"])

    frequencies =  db.execute("SELECT DISTINCT frequencies.frequency FROM frequencies JOIN loans ON loans.payment_frequency = frequencies.id where loans.user_id = ?", user_id)

    types = db.execute("SELECT DISTINCT types.type FROM types JOIN loans ON loans.interest_rate_type = types.id WHERE loans.user_id = ?", user_id)
    # Query database for loans to show
    loans = db.execute("""SELECT loans.id, 
                                 loans.user_id, 
                                 loans.user_loan_id, 
                                 loans.face_value, 
                                 loans.principal, 
                                 banks.bank, 
                                 loans.issue_date, 
                                 loans.loan_term, 
                                 loans.maturity_date, 
                                 loans.interest_rate, 
                                 pf.frequency AS payment_frequency,
                                 types.type AS interest_rate_type, 
                                 nrcp.frequency AS nominal_rate_compounding_period, 
                                 ipf.frequency AS interest_payment_frequency 
                                 FROM loans 
                                 JOIN banks JOIN types 
                                 ON loans.bank_id = banks.id AND loans.interest_rate_type = types.id 
                                 JOIN frequencies pf ON loans.payment_frequency = pf.id 
                                 JOIN frequencies ipf ON loans.interest_payment_frequency = ipf.id 
                                 JOIN frequencies nrcp ON loans.nominal_rate_compounding_period = nrcp.id
                                 WHERE loans.user_id = ?""", user_id)
    message = f"Welcome {name}"
    return render_template("index.html", name=name, view="loans", message=message, loans=loans, banks=banks, frequencies=frequencies, types=types, ids=ids)

#  AMORTIZATIONS
@app.route("/amortizations")
@login_required
def amortizations():
    user_id = session["user_id"]
    # Query database for username
    user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
    name = user["username"]

    # info for filters

    user_amortization_ids = db.execute("SELECT user_amortization_id FROM amortizations WHERE user_id = ?", user_id)
    user_loan_ids = db.execute("SELECT DISTINCT loans.user_loan_id FROM loans JOIN amortizations ON amortizations.loan_id = loans.id WHERE amortizations.user_id = ?", user_id)
    user_loan_ids.sort(key=lambda x: x["user_loan_id"])

    # Query database for loans to show
    amortizations = db.execute("""SELECT amortizations.id, 
                                 amortizations.user_id, 
                                 loans.user_loan_id,
                                 amortizations.loan_id, 
                                 amortizations.user_amortization_id,
                                 amortizations.amort_value, 
                                 amortizations.amort_date
                                 FROM amortizations 
                                 JOIN loans
                                 ON amortizations.loan_id = loans.id
                                 WHERE amortizations.user_id = ?""", user_id)
    message = f"Welcome {name}"
    return render_template("amortizations.html", name=name, view="amortizations", message=message, amortizations=amortizations, user_amortization_ids=user_amortization_ids, user_loan_ids=user_loan_ids)

#  BANKS
@app.route("/banks")
@login_required
def banks():
    user_id = session["user_id"]
    # Query database for username
    user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
    name = user["username"]

# info for filters
    ids = db.execute("SELECT user_bank_id FROM banks WHERE user_id = ?", user_id)


    # Query database for banks to show
    banks = db.execute("SELECT * FROM banks WHERE user_id = ?", user_id)
    message = f"Welcome {name}"
    return render_template("banks.html", name=name, view="banks", message = message, banks=banks, ids=ids)

#  ADD A LOAN
@app.route("/add_loans", methods = ["POST", "GET"])
@login_required
def add_loans():
    # Variables of interest for rendering the add loan page
    user_id = session["user_id"]
    user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
    name = user["username"]
    banks = db.execute("SELECT * FROM banks WHERE user_id = ?", user_id)
    banks.sort(key=lambda x:x["bank"])
    frequencies =  db.execute("SELECT * FROM frequencies")
    compounding_periods = db.execute("SELECT * FROM frequencies WHERE frequency != 'At maturity'")
    types = db.execute("SELECT * FROM types")
    # user got here via get
    if request.method == "GET":
        #  check if banks in database
        if len(banks) == 0:
            message = "No banks in database. A bank must be created before you can add loans"
            mtype = "error-"
            return render_template("index.html", name=name, view="loans", message = message, mtype = mtype) 
        # if there are banks in database go ahead and render the add loans page
        return render_template("add_loans.html", banks=banks, frequencies=frequencies, types=types, compounding_periods=compounding_periods, errors={}, data={})
    # user got here via post
    else:
        data = request.form
        errors, cleaned_data = Loan.validate(data, user_id, db, "add")
    # errors in form data
        if len(errors.keys()) != 0:
            return render_template("add_loans.html", banks=banks, frequencies=frequencies, types=types, compounding_periods=compounding_periods, errors=errors, data=data)
        # all went well
        # get the last id of user's loans
        next_id = get_next_id("loan", user_id, db)
        # save record
        # Getting data to save
        face_value = cleaned_data["face_value"]
        principal = cleaned_data["face_value"]
        bank = db.execute("SELECT * FROM banks WHERE user_id = ? AND bank = ?", user_id, cleaned_data["bank"])[0]["id"]
        issue_date = cleaned_data["issue_date"]
        loan_term = cleaned_data["loan_term"]
        maturity_date = calculate_future_date(issue_date, loan_term)
        interest_rate = cleaned_data["interest_rate"]
        payment_frequency = db.execute("SELECT * FROM frequencies WHERE frequency = ?", cleaned_data["payment_frequency"])[0]["id"]
        interest_rate_type = db.execute("SELECT * FROM types WHERE type = ?", cleaned_data["interest_rate_type"])[0]["id"]
        nominal_rate_compounding_period = db.execute("SELECT * FROM frequencies WHERE frequency = ?", cleaned_data["nominal_rate_compounding_period"])[0]["id"]
        interest_payment_frequency = db.execute("SELECT * FROM frequencies WHERE frequency = ?", cleaned_data["interest_payment_frequency"])[0]["id"]
        
        db.execute("INSERT INTO loans(user_id, user_loan_id, face_value, principal, bank_id, issue_date, loan_term, maturity_date, interest_rate, payment_frequency, interest_rate_type, nominal_rate_compounding_period, interest_payment_frequency) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", user_id, next_id,  face_value, principal, bank, issue_date, loan_term, maturity_date, interest_rate, payment_frequency, interest_rate_type,nominal_rate_compounding_period, interest_payment_frequency)
        return redirect("/")


# EDIT A LOAN
@app.route("/edit_loan", methods=["GET","POST"])
@login_required
def edit_loan():
    # Variables of interest for rendering the edit loan page
    user_id = session["user_id"]
    banks = db.execute("SELECT * FROM banks WHERE user_id = ?", user_id)
    banks.sort(key=lambda x:x["bank"])
    frequencies =  db.execute("SELECT * FROM frequencies")
    compounding_periods = db.execute("SELECT * FROM frequencies WHERE frequency != 'At maturity'")
    types = db.execute("SELECT * FROM types")
    # user got here via get
    if request.method == "GET":
        data = request.args
        user_loan_id = data.get("user_loan_id")
        # checking if user maliciously remove id from page
        if user_loan_id:
            # preventing user from editing info he does not owns
            try:
                data = db.execute("""SELECT loans.id, 
                                loans.user_id, 
                                loans.user_loan_id, 
                                loans.face_value, 
                                loans.principal, 
                                banks.bank, 
                                loans.issue_date, 
                                loans.loan_term, 
                                loans.maturity_date, 
                                loans.interest_rate, 
                                pf.frequency AS payment_frequency,
                                types.type AS interest_rate_type, 
                                nrcp.frequency AS nominal_rate_compounding_period, 
                                ipf.frequency AS interest_payment_frequency 
                                FROM loans 
                                JOIN banks JOIN types 
                                ON loans.bank_id = banks.id AND loans.interest_rate_type = types.id 
                                JOIN frequencies pf ON loans.payment_frequency = pf.id 
                                JOIN frequencies ipf ON loans.interest_payment_frequency = ipf.id 
                                JOIN frequencies nrcp ON loans.nominal_rate_compounding_period = nrcp.id
                                WHERE loans.user_id = ? AND loans.user_loan_id = ?""", user_id, user_loan_id)[0]
            except IndexError:
                pass
            else:
                return render_template("edit_loan.html", data=data, errors={}, banks=banks, frequencies=frequencies, types=types, compounding_periods=compounding_periods)
        return redirect("/")
    # user got here via post 
    else:
        # Ensure amortization was submitted
        data = request.form
        user_loan_id = data.get("user_loan_id")
        # Validate user's input
        # preventing user from editing info he does not owns
        try:
            errors, cleaned_data = Loan.validate(data, user_id, db, "edit")
        except IndexError:
            pass
        else:
            # errors in form data
            if len(errors.keys()) != 0:
                return render_template("edit_loan.html", errors=errors, data=data, banks=banks, frequencies=frequencies, types=types, compounding_periods=compounding_periods)
            # all went well
            # update record
            face_value = cleaned_data["face_value"]
            principal = cleaned_data["principal"]
            bank = db.execute("SELECT * FROM banks WHERE user_id = ? AND bank = ?", user_id, cleaned_data["bank"])[0]["id"]
            issue_date = cleaned_data["issue_date"]
            loan_term = cleaned_data["loan_term"]
            maturity_date = calculate_future_date(issue_date, loan_term)
            interest_rate = cleaned_data["interest_rate"]
            payment_frequency = db.execute("SELECT * FROM frequencies WHERE frequency = ?", cleaned_data["payment_frequency"])[0]["id"]
            interest_rate_type = db.execute("SELECT * FROM types WHERE type = ?", cleaned_data["interest_rate_type"])[0]["id"]
            nominal_rate_compounding_period = db.execute("SELECT * FROM frequencies WHERE frequency = ?", cleaned_data["nominal_rate_compounding_period"])[0]["id"]
            interest_payment_frequency = db.execute("SELECT * FROM frequencies WHERE frequency = ?", cleaned_data["interest_payment_frequency"])[0]["id"]
            
            db.execute("UPDATE loans SET face_value = ?, principal = ?, bank_id = ?, issue_date = ?, loan_term = ?, maturity_date = ?, interest_rate = ?, payment_frequency = ?, interest_rate_type = ?, nominal_rate_compounding_period = ?, interest_payment_frequency = ? WHERE user_id = ? AND user_loan_id = ?",face_value, principal, bank, issue_date, loan_term, maturity_date, interest_rate, payment_frequency, interest_rate_type,nominal_rate_compounding_period, interest_payment_frequency, user_id, user_loan_id)
        return redirect("/")


# DELETE A LOAN
@app.route("/delete_loan", methods=["POST"])
@login_required
def delete_loan():
    user_id = session["user_id"]
    user_loan_id = request.form.get("user_loan_id")
    # info for filters
    ids = db.execute("SELECT user_loan_id FROM loans WHERE user_id = ?", user_id)

    banks = db.execute("SELECT DISTINCT banks.bank FROM banks JOIN loans ON loans.bank_id = banks.id WHERE loans.user_id = ?", user_id)
    banks.sort(key=lambda x:x["bank"])

    frequencies =  db.execute("SELECT DISTINCT frequencies.frequency FROM frequencies JOIN loans ON loans.payment_frequency = frequencies.id where loans.user_id = ?", user_id)

    types = db.execute("SELECT DISTINCT types.type FROM types JOIN loans ON loans.interest_rate_type = types.id WHERE loans.user_id = ?", user_id)
    # checking if user maliciously remove id from page
    if user_loan_id:
        # preventing user from deleting info he does not owns
        try:
            loan_id = db.execute("SELECT id FROM loans WHERE user_id = ? AND user_loan_id = ?", user_id, user_loan_id )[0]["id"]
            #  checking if loan is in use by some amortization
            amortizations = db.execute("SELECT * FROM amortizations WHERE loan_id = ?", loan_id)
            if len(amortizations) != 0:
                message = "Can not delete loan because it is been used by some amortization."
                mtype = "error-"
                loans = db.execute("""SELECT loans.id, 
                                    loans.user_id, 
                                    loans.user_loan_id, 
                                    loans.face_value, 
                                    loans.principal, 
                                    banks.bank, 
                                    loans.issue_date, 
                                    loans.loan_term, 
                                    loans.maturity_date, 
                                    loans.interest_rate, 
                                    pf.frequency AS payment_frequency,
                                    types.type AS interest_rate_type, 
                                    nrcp.frequency AS nominal_rate_compounding_period, 
                                    ipf.frequency AS interest_payment_frequency 
                                    FROM loans 
                                    JOIN banks JOIN types 
                                    ON loans.bank_id = banks.id AND loans.interest_rate_type = types.id 
                                    JOIN frequencies pf ON loans.payment_frequency = pf.id 
                                    JOIN frequencies ipf ON loans.interest_payment_frequency = ipf.id 
                                    JOIN frequencies nrcp ON loans.nominal_rate_compounding_period = nrcp.id
                                    WHERE loans.user_id = ?""", user_id)
                return render_template("index.html", view="loans", message = message, mtype = mtype, loans=loans, banks=banks, frequencies=frequencies, types=types, ids=ids) 
            else:
                db.execute("DELETE FROM loans WHERE id = ?", loan_id)
        except IndexError:
            pass
        return redirect("/")


#  AMORTIZE
@app.route("/amortize", methods = ["POST", "GET"])
@login_required
def amortize():
    # Variables of interest for rendering the amortize page
    user_id = session["user_id"]

    # user got here via get
    if request.method == "GET":
        data = request.args
        user_loan_id = data.get("user_loan_id")
        # info for filters
        ids = db.execute("SELECT user_loan_id FROM loans WHERE user_id = ?", user_id)

        banks = db.execute("SELECT DISTINCT banks.bank FROM banks JOIN loans ON loans.bank_id = banks.id WHERE loans.user_id = ?", user_id)
        banks.sort(key=lambda x:x["bank"])

        frequencies =  db.execute("SELECT DISTINCT frequencies.frequency FROM frequencies JOIN loans ON loans.payment_frequency = frequencies.id where loans.user_id = ?", user_id)

        types = db.execute("SELECT DISTINCT types.type FROM types JOIN loans ON loans.interest_rate_type = types.id WHERE loans.user_id = ?", user_id)
        # checking if user maliciously remove id from page
        if user_loan_id:
            # prevent user from amortize a loan he does not owns
            try:
                # getting loan principal
                loan = db.execute("SELECT * FROM loans WHERE user_id = ? AND user_loan_id = ?", user_id, user_loan_id)[0]
                principal = loan["principal"]
                #  check if loans in database
                if principal == 0:
                    message = "Can not amortize loan. Loan balance is equal to $0.00"
                    mtype = "error-"
                    loans = db.execute("""SELECT loans.id, 
                                        loans.user_id, 
                                        loans.user_loan_id, 
                                        loans.face_value, 
                                        loans.principal, 
                                        banks.bank, 
                                        loans.issue_date, 
                                        loans.loan_term, 
                                        loans.maturity_date, 
                                        loans.interest_rate, 
                                        pf.frequency AS payment_frequency,
                                        types.type AS interest_rate_type, 
                                        nrcp.frequency AS nominal_rate_compounding_period, 
                                        ipf.frequency AS interest_payment_frequency 
                                        FROM loans 
                                        JOIN banks JOIN types 
                                        ON loans.bank_id = banks.id AND loans.interest_rate_type = types.id 
                                        JOIN frequencies pf ON loans.payment_frequency = pf.id 
                                        JOIN frequencies ipf ON loans.interest_payment_frequency = ipf.id 
                                        JOIN frequencies nrcp ON loans.nominal_rate_compounding_period = nrcp.id
                                        WHERE loans.user_id = ?""", user_id)
                    return render_template("index.html", view="loans", message = message, mtype = mtype, loans=loans, banks=banks, frequencies=frequencies, types=types, ids=ids)
                else:
                    return render_template("amortize.html", errors={}, data=data)
            except IndexError:
                pass
        return redirect("/")
    # user got here via post
    else:
        data = request.form
        errors, cleaned_data = Amortization.validate(data, user_id, db, "add")
    # errors in form data
        if len(errors.keys()) != 0:
            return render_template("amortize.html", errors=errors, data=data)
        # all went well
        # get the last id of user's loans
        next_id = get_next_id("amortization", user_id, db)
        # save record
        # Getting data to save
        loan_id = db.execute("SELECT * FROM loans WHERE user_id = ? AND user_loan_id = ?", user_id, cleaned_data["user_loan_id"])[0]["id"]
        amort_value = cleaned_data["amort_value"]
        amort_date = cleaned_data["amort_date"]
    
        db.execute("INSERT INTO amortizations(user_id, loan_id, user_amortization_id, amort_value, amort_date) VALUES (?, ?, ?, ?, ?)", user_id, loan_id, next_id,  amort_value, amort_date)
        # Update loan's balance
        principal = db.execute("SELECT principal FROM loans WHERE id = ?", loan_id)[0]["principal"]
        updated_principal = principal - amort_value
        db.execute("UPDATE loans SET principal = ? WHERE id = ?", updated_principal, loan_id)
        return redirect("/amortizations")

#  ADD AN AMORTIZATION
@app.route("/add_amortizations", methods = ["POST", "GET"])
@login_required
def add_amortizations():
    # Variables of interest for rendering the add amortization page
    user_id = session["user_id"]
    user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
    name = user["username"]
    loans = db.execute("SELECT * FROM loans WHERE user_id = ? AND principal != 0", user_id)
    

    # user got here via get
    if request.method == "GET":
        #  check if loans in database
        if len(loans) == 0:
            message = "No loans in database. A loan must be created before you can add amortizations"
            mtype = "error-"
            return render_template("amortizations.html", name=name, view="amortizations", message = message, mtype = mtype) 
        # if there are loans in database go ahead and render the add amortizations page
        return render_template("add_amortizations.html", loans=loans, errors={}, data={})
    # user got here via post
    else:
        data = request.form
        errors, cleaned_data = Amortization.validate(data, user_id, db, "add")
    # errors in form data
        if len(errors.keys()) != 0:
            return render_template("add_amortizations.html", loans=loans, errors=errors, data=data)
        # all went well
        # get the last id of user's loans
        next_id = get_next_id("amortization", user_id, db)
        # save record
        # Getting data to save
        loan_id = db.execute("SELECT * FROM loans WHERE user_id = ? AND user_loan_id = ?", user_id, cleaned_data["user_loan_id"])[0]["id"]
        amort_value = cleaned_data["amort_value"]
        amort_date = cleaned_data["amort_date"]
    
        db.execute("INSERT INTO amortizations(user_id, loan_id, user_amortization_id, amort_value, amort_date) VALUES (?, ?, ?, ?, ?)", user_id, loan_id, next_id,  amort_value, amort_date)
        # Update loan's balance
        principal = db.execute("SELECT principal FROM loans WHERE id = ?", loan_id)[0]["principal"]
        updated_principal = principal - amort_value
        db.execute("UPDATE loans SET principal = ? WHERE id = ?", updated_principal, loan_id)
        return redirect("/amortizations")


# EDIT AN AMORTIZATION
@app.route("/edit_amortization", methods=["GET","POST"])
@login_required
def edit_amortization():
    user_id = session["user_id"]
    # user got here via get
    if request.method == "GET":
        data = request.args
        user_amortization_id = data.get("user_amortization_id")
        # checking if user maliciously remove id from page
        if user_amortization_id:
            # preventing user from editing info he does not owns
            try:
                data = db.execute("SELECT * FROM amortizations WHERE user_id = ? AND user_amortization_id = ?", user_id, user_amortization_id)[0]
                loan_id = data["loan_id"]
                loan = db.execute("SELECT * FROM loans WHERE id = ?", loan_id)[0]
                user_loan_id = loan["user_loan_id"]
                data["user_loan_id"] = user_loan_id
            except IndexError:
                pass
            else:
                return render_template("edit_amortization.html", data=data, errors={})
        return redirect("/amortizations")
    # user got here via post 
    else:
        # Ensure amortization was submitted
        data = request.form
        user_amortization_id = data.get("user_amortization_id")
        # Validate user's input
        # preventing user from editing info he does not owns
        try:
            errors, cleaned_data = Amortization.validate(data, user_id, db, "edit")
        except IndexError:
            pass
        else:
            # errors in form data
            if len(errors.keys()) != 0:
                return render_template("edit_amortization.html", errors=errors, data=data)
            # all went well
            # update record
            amort_value = cleaned_data["amort_value"]
            amort_date = cleaned_data["amort_date"]
            db.execute("UPDATE amortizations SET amort_value = ?, amort_date = ? WHERE user_amortization_id = ? and user_id = ?", amort_value, amort_date, user_amortization_id, user_id)

            # update loan's balance
            updated_principal = cleaned_data["updated_principal"]
            # loan's id
            loan_id = cleaned_data["loan_id"]

            db.execute("UPDATE loans SET principal = ? WHERE id = ?", updated_principal, loan_id)
        return redirect("/amortizations")


# DELETE AN AMORTIZATION
@app.route("/delete_amortization", methods=["POST"])
@login_required
def delete_amortization():
    user_id = session["user_id"]
    user_amortization_id = request.form.get("user_amortization_id")
    # checking if user maliciously remove id from page
    if user_amortization_id:
        try:
            # preventing user from deleting info he does not owns
            amortization = db.execute("SELECT * FROM amortizations WHERE user_id = ? AND user_amortization_id = ?", user_id, user_amortization_id)[0]
            # Getting amortization and loan info
            amortization_id = amortization["id"]
            loan_id = amortization["loan_id"]
            amort_value = amortization["amort_value"]
            loan = db.execute("SELECT * FROM loans WHERE id = ?", loan_id)[0]
            #  Deleting an amortization is allowed always but make sure to update loan's balance
            principal = loan["principal"]
            updated_principal = principal + amort_value
            db.execute("UPDATE loans SET principal = ? WHERE id = ?", updated_principal, loan_id)
            # delete amortization from database
            db.execute("DELETE FROM amortizations WHERE id = ?", amortization_id)
        except IndexError:
            pass
    return redirect("/amortizations")




#  ADD A BANK
@app.route("/add_banks", methods=["GET", "POST"])
@login_required
def add_banks():
    user_id = session["user_id"]
    # user got here via get
    if request.method == "GET":
        return render_template("add_banks.html", data={}, errors={})
    # user got here via post
    else:
        # Ensure bank was submitted
        data = request.form
        # Validate user's input
        errors, cleaned_data = Bank.validate(data, user_id, db, "add")
        # errors in form data
        if len(errors.keys()) != 0:
            return render_template("add_banks.html", errors=errors, data=data)
        # all went well
        # get the last id of user's banks
        next_id = get_next_id("bank", user_id, db)
        # save record
        bank = cleaned_data["bank"]
        db.execute("INSERT INTO banks(user_id, user_bank_id, bank) VALUES (?, ?, ?)", user_id, next_id, bank)
        return redirect("/banks")
        

# EDIT A BANK
@app.route("/edit_bank", methods=["GET","POST"])
@login_required
def edit_bank():
    user_id = session["user_id"]
    # user got here via get
    if request.method == "GET":
        data = request.args
        user_bank_id = data.get("user_bank_id")
        # checking if user maliciously remove id from page
        if user_bank_id:
            # preventing user from editing info he does not owns
            try:
                data = db.execute("SELECT * FROM banks WHERE user_id = ? AND user_bank_id = ?", user_id, user_bank_id)[0]
            except IndexError:
                pass
            else:
                return render_template("edit_bank.html", data=data)
        return redirect("/banks")
    # user got here via post 
    else:
        # Ensure bank was submitted
        data = request.form
        user_bank_id = data.get("user_bank_id")
        # Validate user's input
        # preventing user from editing info he does not owns
        try:
            errors, cleaned_data = Bank.validate(data, user_id, db, "edit")
        except IndexError:
            pass
        else:
            # errors in form data
            if len(errors.keys()) != 0:
                return render_template("edit_bank.html", errors=errors, data=data)
            # all went well
            # update record
            bank = cleaned_data["bank"]
            db.execute("UPDATE banks SET bank = ? WHERE user_bank_id = ? and user_id = ?", bank, user_bank_id, user_id)
        return redirect("/banks")


# DELETE A BANK
@app.route("/delete_bank", methods=["POST"])
@login_required
def delete_bank():
    user_id = session["user_id"]
    user_bank_id = request.form.get("user_bank_id")
    # checking if user maliciously remove id from page
    if user_bank_id:
        try:
            # preventing user from deleting info he does not owns
            bank_id = db.execute("SELECT id FROM banks WHERE user_id = ? AND user_bank_id = ?", user_id, user_bank_id )[0]["id"]
            #  checking if bank is in use by some loan
            loans = db.execute("SELECT * FROM loans WHERE bank_id = ?", bank_id)
            if len(loans) != 0:
                message = "Can not delete bank because it is been used by some loan."
                mtype = "error-"
                banks = db.execute("SELECT * FROM banks WHERE user_id = ?", user_id)
                # info for filters
                ids = db.execute("SELECT user_bank_id FROM banks WHERE user_id = ?", user_id)
                return render_template("banks.html", view="banks", message = message, mtype = mtype, banks=banks, ids=ids) 
            else:
                db.execute("DELETE FROM banks WHERE id = ?", bank_id)
        except IndexError:
            pass
    return redirect("/banks")

# LOAN FILTERS
@app.route("/filter", methods=["GET"])
@login_required
def filter():
    user_id = session["user_id"]
    # Query database for username
    user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
    name = user["username"]
    data = request.args

    if user_loan_id := data.get("user_loan_id"):
        try:
            # Query database for loans to show
            loans = db.execute(f"""SELECT loans.id, 
                                    loans.user_id, 
                                    loans.user_loan_id, 
                                    loans.face_value, 
                                    loans.principal, 
                                    banks.bank, 
                                    loans.issue_date, 
                                    loans.loan_term, 
                                    loans.maturity_date, 
                                    loans.interest_rate, 
                                    pf.frequency AS payment_frequency,
                                    types.type AS interest_rate_type, 
                                    nrcp.frequency AS nominal_rate_compounding_period, 
                                    ipf.frequency AS interest_payment_frequency 
                                    FROM loans 
                                    JOIN banks JOIN types 
                                    ON loans.bank_id = banks.id AND loans.interest_rate_type = types.id 
                                    JOIN frequencies pf ON loans.payment_frequency = pf.id 
                                    JOIN frequencies ipf ON loans.interest_payment_frequency = ipf.id 
                                    JOIN frequencies nrcp ON loans.nominal_rate_compounding_period = nrcp.id
                                    WHERE loans.user_id = ? AND loans.user_loan_id = ?""", user_id, user_loan_id)
        except IndexError:
            return redirect("/")
    elif bank := data.get("bank"):
        try:
            bank_id = db.execute("SELECT * FROM banks WHERE bank = ? AND user_id = ?", data.get("bank"), user_id)[0]["id"]
        except IndexError:
            bank_id = ""
            # Query database for loans to show
        loans = db.execute(f"""SELECT loans.id, 
                                    loans.user_id, 
                                    loans.user_loan_id, 
                                    loans.face_value, 
                                    loans.principal, 
                                    banks.bank, 
                                    loans.issue_date, 
                                    loans.loan_term, 
                                    loans.maturity_date, 
                                    loans.interest_rate, 
                                    pf.frequency AS payment_frequency,
                                    types.type AS interest_rate_type, 
                                    nrcp.frequency AS nominal_rate_compounding_period, 
                                    ipf.frequency AS interest_payment_frequency 
                                    FROM loans 
                                    JOIN banks JOIN types 
                                    ON loans.bank_id = banks.id AND loans.interest_rate_type = types.id 
                                    JOIN frequencies pf ON loans.payment_frequency = pf.id 
                                    JOIN frequencies ipf ON loans.interest_payment_frequency = ipf.id 
                                    JOIN frequencies nrcp ON loans.nominal_rate_compounding_period = nrcp.id
                                    WHERE loans.user_id = ? AND loans.bank_id = ?""", user_id, bank_id)
    elif interest_rate_type := data.get("interest_rate_type"):
        try:
            interest_rate_type = db.execute("SELECT * FROM types WHERE type = ?", data.get("interest_rate_type"))[0]["id"]
        except IndexError:
            interest_rate_type = ""
        # Query database for loans to show
        loans = db.execute(f"""SELECT loans.id, 
                                loans.user_id, 
                                loans.user_loan_id, 
                                loans.face_value, 
                                loans.principal, 
                                banks.bank, 
                                loans.issue_date, 
                                loans.loan_term, 
                                loans.maturity_date, 
                                loans.interest_rate, 
                                pf.frequency AS payment_frequency,
                                types.type AS interest_rate_type, 
                                nrcp.frequency AS nominal_rate_compounding_period, 
                                ipf.frequency AS interest_payment_frequency 
                                FROM loans 
                                JOIN banks JOIN types 
                                ON loans.bank_id = banks.id AND loans.interest_rate_type = types.id 
                                JOIN frequencies pf ON loans.payment_frequency = pf.id 
                                JOIN frequencies ipf ON loans.interest_payment_frequency = ipf.id 
                                JOIN frequencies nrcp ON loans.nominal_rate_compounding_period = nrcp.id
                                WHERE loans.user_id = ? AND loans.interest_rate_type = ?""", user_id, interest_rate_type)

    elif payment_frequency := data.get("payment_frequency"):
        try:
            payment_frequency = db.execute("SELECT * FROM frequencies WHERE frequency = ?", data.get("payment_frequency"))[0]["id"]
        except IndexError:
            payment_frequency = ""
        # Query database for loans to show
        loans = db.execute(f"""SELECT loans.id, 
                                loans.user_id, 
                                loans.user_loan_id, 
                                loans.face_value, 
                                loans.principal, 
                                banks.bank, 
                                loans.issue_date, 
                                loans.loan_term, 
                                loans.maturity_date, 
                                loans.interest_rate, 
                                pf.frequency AS payment_frequency,
                                types.type AS interest_rate_type, 
                                nrcp.frequency AS nominal_rate_compounding_period, 
                                ipf.frequency AS interest_payment_frequency 
                                FROM loans 
                                JOIN banks JOIN types 
                                ON loans.bank_id = banks.id AND loans.interest_rate_type = types.id 
                                JOIN frequencies pf ON loans.payment_frequency = pf.id 
                                JOIN frequencies ipf ON loans.interest_payment_frequency = ipf.id 
                                JOIN frequencies nrcp ON loans.nominal_rate_compounding_period = nrcp.id
                                WHERE loans.user_id = ? AND loans.payment_frequency = ?""", user_id, payment_frequency)

    elif status := data.get("status"):
        if status == "paid":
            # Query database for loans to show
            loans = db.execute(f"""SELECT loans.id, 
                                    loans.user_id, 
                                    loans.user_loan_id, 
                                    loans.face_value, 
                                    loans.principal, 
                                    banks.bank, 
                                    loans.issue_date, 
                                    loans.loan_term, 
                                    loans.maturity_date, 
                                    loans.interest_rate, 
                                    pf.frequency AS payment_frequency,
                                    types.type AS interest_rate_type, 
                                    nrcp.frequency AS nominal_rate_compounding_period, 
                                    ipf.frequency AS interest_payment_frequency 
                                    FROM loans 
                                    JOIN banks JOIN types 
                                    ON loans.bank_id = banks.id AND loans.interest_rate_type = types.id 
                                    JOIN frequencies pf ON loans.payment_frequency = pf.id 
                                    JOIN frequencies ipf ON loans.interest_payment_frequency = ipf.id 
                                    JOIN frequencies nrcp ON loans.nominal_rate_compounding_period = nrcp.id
                                    WHERE loans.user_id = ? AND loans.principal = 0""", user_id)
        elif status == "due":
            # Query database for loans to show
            loans = db.execute(f"""SELECT loans.id, 
                                    loans.user_id, 
                                    loans.user_loan_id, 
                                    loans.face_value, 
                                    loans.principal, 
                                    banks.bank, 
                                    loans.issue_date, 
                                    loans.loan_term, 
                                    loans.maturity_date, 
                                    loans.interest_rate, 
                                    pf.frequency AS payment_frequency,
                                    types.type AS interest_rate_type, 
                                    nrcp.frequency AS nominal_rate_compounding_period, 
                                    ipf.frequency AS interest_payment_frequency 
                                    FROM loans 
                                    JOIN banks JOIN types 
                                    ON loans.bank_id = banks.id AND loans.interest_rate_type = types.id 
                                    JOIN frequencies pf ON loans.payment_frequency = pf.id 
                                    JOIN frequencies ipf ON loans.interest_payment_frequency = ipf.id 
                                    JOIN frequencies nrcp ON loans.nominal_rate_compounding_period = nrcp.id
                                    WHERE loans.user_id = ? AND loans.principal != 0""", user_id)
        else:
            # Query database for loans to show
            loans = db.execute(f"""SELECT loans.id, 
                                    loans.user_id, 
                                    loans.user_loan_id, 
                                    loans.face_value, 
                                    loans.principal, 
                                    banks.bank, 
                                    loans.issue_date, 
                                    loans.loan_term, 
                                    loans.maturity_date, 
                                    loans.interest_rate, 
                                    pf.frequency AS payment_frequency,
                                    types.type AS interest_rate_type, 
                                    nrcp.frequency AS nominal_rate_compounding_period, 
                                    ipf.frequency AS interest_payment_frequency 
                                    FROM loans 
                                    JOIN banks JOIN types 
                                    ON loans.bank_id = banks.id AND loans.interest_rate_type = types.id 
                                    JOIN frequencies pf ON loans.payment_frequency = pf.id 
                                    JOIN frequencies ipf ON loans.interest_payment_frequency = ipf.id 
                                    JOIN frequencies nrcp ON loans.nominal_rate_compounding_period = nrcp.id
                                    WHERE loans.user_id = ? AND loans.principal = '' """, user_id)
    elif issued_before := data.get("issued_before"):
            try:
                issued_before = datetime.strptime(issued_before, '%Y-%m-%d').date()
            except ValueError:
                issued_before = ""
            # Query database for loans to show
            loans = db.execute(f"""SELECT loans.id, 
                                    loans.user_id, 
                                    loans.user_loan_id, 
                                    loans.face_value, 
                                    loans.principal, 
                                    banks.bank, 
                                    loans.issue_date, 
                                    loans.loan_term, 
                                    loans.maturity_date, 
                                    loans.interest_rate, 
                                    pf.frequency AS payment_frequency,
                                    types.type AS interest_rate_type, 
                                    nrcp.frequency AS nominal_rate_compounding_period, 
                                    ipf.frequency AS interest_payment_frequency 
                                    FROM loans 
                                    JOIN banks JOIN types 
                                    ON loans.bank_id = banks.id AND loans.interest_rate_type = types.id 
                                    JOIN frequencies pf ON loans.payment_frequency = pf.id 
                                    JOIN frequencies ipf ON loans.interest_payment_frequency = ipf.id 
                                    JOIN frequencies nrcp ON loans.nominal_rate_compounding_period = nrcp.id
                                    WHERE loans.user_id = ? AND loans.issue_date < ?""", user_id, issued_before)
    elif issued_after := data.get("issued_after"):
            try:
                issued_after = datetime.strptime(issued_after, '%Y-%m-%d').date()
            except ValueError:
                issued_after = ""
            # Query database for loans to show
            loans = db.execute(f"""SELECT loans.id, 
                                    loans.user_id, 
                                    loans.user_loan_id, 
                                    loans.face_value, 
                                    loans.principal, 
                                    banks.bank, 
                                    loans.issue_date, 
                                    loans.loan_term, 
                                    loans.maturity_date, 
                                    loans.interest_rate, 
                                    pf.frequency AS payment_frequency,
                                    types.type AS interest_rate_type, 
                                    nrcp.frequency AS nominal_rate_compounding_period, 
                                    ipf.frequency AS interest_payment_frequency 
                                    FROM loans 
                                    JOIN banks JOIN types 
                                    ON loans.bank_id = banks.id AND loans.interest_rate_type = types.id 
                                    JOIN frequencies pf ON loans.payment_frequency = pf.id 
                                    JOIN frequencies ipf ON loans.interest_payment_frequency = ipf.id 
                                    JOIN frequencies nrcp ON loans.nominal_rate_compounding_period = nrcp.id
                                    WHERE loans.user_id = ? AND loans.issue_date > ?""", user_id, issued_after)
                    
    # info for filters
    ids = db.execute("SELECT user_loan_id FROM loans WHERE user_id = ?", user_id)

    banks = db.execute("SELECT DISTINCT banks.bank FROM banks JOIN loans ON loans.bank_id = banks.id WHERE loans.user_id = ?", user_id)
    banks.sort(key=lambda x:x["bank"])

    frequencies =  db.execute("SELECT DISTINCT frequencies.frequency FROM frequencies JOIN loans ON loans.payment_frequency = frequencies.id where loans.user_id = ?", user_id)

    types = db.execute("SELECT DISTINCT types.type FROM types JOIN loans ON loans.interest_rate_type = types.id WHERE loans.user_id = ?", user_id)

    message = f"Welcome {name}"
    return render_template("index.html", name=name, view="loans", message=message, loans=loans, banks=banks, frequencies=frequencies, types=types, ids=ids)

# AMORTIZATION FILTERS
@app.route("/amort_filter", methods=["GET"])
@login_required
def amort_filter():
    user_id = session["user_id"]
    # Query database for username
    user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
    name = user["username"]
    data = request.args

    if user_loan_id := data.get("user_loan_id"):
        try:
            # Query database for amortizations to show
            amortizations = db.execute("""SELECT amortizations.id, 
                            amortizations.user_id, 
                            loans.user_loan_id,
                            amortizations.loan_id, 
                            amortizations.user_amortization_id,
                            amortizations.amort_value, 
                            amortizations.amort_date
                            FROM amortizations 
                            JOIN loans
                            ON amortizations.loan_id = loans.id
                            WHERE amortizations.user_id = ? AND loans.user_loan_id = ?""", user_id, user_loan_id)
        except IndexError:
            return redirect("/amortizations")
    elif user_amortization_id := data.get("user_amortization_id"):
        try:
            # Query database for amortizations to show
            amortizations = db.execute("""SELECT amortizations.id, 
                            amortizations.user_id, 
                            loans.user_loan_id,
                            amortizations.loan_id, 
                            amortizations.user_amortization_id,
                            amortizations.amort_value, 
                            amortizations.amort_date
                            FROM amortizations 
                            JOIN loans
                            ON amortizations.loan_id = loans.id
                            WHERE amortizations.user_id = ? AND amortizations.user_amortization_id = ?""", user_id, user_amortization_id)
        except IndexError:
            return redirect("/amortizations")
    elif paid_before := data.get("paid_before"):
            try:
                paid_before = datetime.strptime(paid_before, '%Y-%m-%d').date()
            except ValueError:
                paid_before = ""
            # Query database for amortizations to show
            amortizations = db.execute("""SELECT amortizations.id, 
                            amortizations.user_id, 
                            loans.user_loan_id,
                            amortizations.loan_id, 
                            amortizations.user_amortization_id,
                            amortizations.amort_value, 
                            amortizations.amort_date
                            FROM amortizations 
                            JOIN loans
                            ON amortizations.loan_id = loans.id
                            WHERE amortizations.user_id = ? AND amortizations.amort_date < ?""", user_id, paid_before)
    elif paid_after := data.get("paid_after"):
            try:
                paid_after = datetime.strptime(paid_after, '%Y-%m-%d').date()
            except ValueError:
                paid_after = ""
            # Query database for loans to show
            amortizations = db.execute("""SELECT amortizations.id, 
                            amortizations.user_id, 
                            loans.user_loan_id,
                            amortizations.loan_id, 
                            amortizations.user_amortization_id,
                            amortizations.amort_value, 
                            amortizations.amort_date
                            FROM amortizations 
                            JOIN loans
                            ON amortizations.loan_id = loans.id
                            WHERE amortizations.user_id = ? AND amortizations.amort_date > ?""", user_id, paid_after)
                    
    # info for filters

    user_amortization_ids = db.execute("SELECT user_amortization_id FROM amortizations WHERE user_id = ?", user_id)
    user_loan_ids = db.execute("SELECT DISTINCT loans.user_loan_id FROM loans JOIN amortizations ON amortizations.loan_id = loans.id WHERE amortizations.user_id = ?", user_id)
    user_loan_ids.sort(key=lambda x: x["user_loan_id"])

    message = f"Welcome {name}"
    return render_template("amortizations.html", name=name, view="amortizations", message=message, amortizations=amortizations, user_amortization_ids=user_amortization_ids, user_loan_ids=user_loan_ids)
    

# BANK FILTERS
@app.route("/bank_filter", methods=["GET"])
@login_required
def bank_filter():
    user_id = session["user_id"]
    # Query database for username
    user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
    name = user["username"]
    data = request.args

    if user_bank_id := data.get("user_bank_id"):
        try:
            # Query database for amortizations to show
            banks = db.execute("SELECT * FROM banks WHERE user_id = ? AND user_bank_id = ?", user_id, user_bank_id)
        except IndexError:
            return redirect("/banks")
    # info for filters
    ids = db.execute("SELECT user_bank_id FROM banks WHERE user_id = ?", user_id)
    message = f"Welcome {name}"
    return render_template("banks.html", name=name, view="banks", message = message, banks=banks, ids=ids)
    
# REPORTS
@app.route("/report", methods=["GET"])
@login_required
def report():
    user_id = session["user_id"]
    # Query database for username
    user = db.execute("SELECT * FROM users WHERE id = ?", user_id)[0]
    name = user["username"]
    message = f"Welcome {name}"
    
    data = request.args
    user_loan_id = data.get("user_loan_id")
    # checking if user maliciously remove id from page
    if user_loan_id:
        # preventing user from viewing info he does not owns
        try:
            # Fetch loan from database
            data_loan = db.execute("""SELECT loans.user_loan_id as id, loans.face_value, banks.bank, loans.issue_date, loans.loan_term, pf.frequency AS payment_frequency, loans.interest_rate, types.type AS interest_rate_type, nrcp.frequency AS nominal_rate_compounding_period, ipf.frequency AS interest_payment_frequency FROM loans JOIN banks JOIN types ON loans.bank_id = banks.id AND loans.interest_rate_type = types.id JOIN frequencies pf ON loans.payment_frequency = pf.id JOIN frequencies ipf ON loans.interest_payment_frequency = ipf.id 
            JOIN frequencies nrcp ON loans.nominal_rate_compounding_period = nrcp.id WHERE   loans.user_id = ? AND loans.user_loan_id = ?""", user_id, user_loan_id)[0]
            # Loan object
            loan = Loan(**data_loan)
            
            #Fetch amortizations from database

            data_amortizations = db.execute("""SELECT amortizations.user_amortization_id as id, loans.user_loan_id as loan_id, amortizations.amort_value, amortizations.amort_date FROM amortizations JOIN loans ON amortizations.loan_id = loans.id WHERE loans.user_id = ? AND loans.user_loan_id = ?""", user_id, user_loan_id)

            for data_amortization in data_amortizations:
                amortization = Amortization(**data_amortization)
                loan.add_amortization(amortization)
            loan.update_sch()
            loan.update_act()
            report = cash_flow_report(loan)
            print(report)

        except IndexError:
            return redirect("/")


    return render_template("report.html", view="report", message=message, report=report)



    

# LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Getting inputs from the post request
        username = request.form.get("username")
        password = request.form.get("password")
        # Query database for username
        user = db.execute("SELECT * FROM users WHERE username = ?", username)
        message = ""
        # Ensure username was submitted:
        if not username:
            message ="Must provide username"
        # Ensure password was submitted
        elif not request.form.get("password"):
            message ="Must provide password"
        # Ensure username exists and password is correct
        elif len(user) != 1 or not check_password_hash(user[0]["hash"], password):
            message = "Invalid username and/or password"
        # If at least one input is not OK, render a message
        if message:
            return render_template("login.html", message=message, username=username, password=password, view="login")
        # Remember which user has logged in
        session["user_id"] = user[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html", view="login")


# LOGOUT
@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


# REGISTER USERS
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST
    if request.method == "POST":
        # Getting inputs from the post request
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Validates if user name is already taken
        user = db.execute("SELECT * FROM users WHERE username = ?", username)
        message = ""
        # Checking inputs
        # Ensures user was submitted
        if not username:
            message = "Must provide username"
        # Ensures password was submitted
        elif not password:
            message = "Must provide password"
        # Ensures confirmation was submitted
        elif not confirmation:
            message = "Must provide password confirmation"
        # Ensures user name doesn't exist already
        elif len(user) != 0:
            message = "Username already taken"
        # Ensures that both password and confirmation are the same
        elif password != confirmation:
            message = "Confirmation password must match password"
        # Ensures that password is strong
        elif not is_strong(password):
            message = "Password must be at least 8 characters long, must contain upper and lower letters, and at least one number"
        # If at least one input is not OK, render a message
        if message:
            return render_template("register.html", message=message, username=username, password=password, confirmation=confirmation, view="register")
        # All went well, register the new user and get his id. Doesn't store user's password in plain text
        db.execute("INSERT INTO users(username, hash) VALUES (?,?)", username, generate_password_hash(password))
        user = db.execute("SELECT * FROM users WHERE username = ?", username)[0]

        # Log user in and remeber him
        session["user_id"] = user["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html", view="register")


# CHANGE PASSWORD
@app.route("/passwordchange", methods=["GET", "POST"])
@login_required
def password_change():
    """Let user change his password"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        #Getting inputs from the post request
        old = request.form.get("old")
        new = request.form.get("new")
        confirmation = request.form.get("confirmation")
        user_id = session.get("user_id")
        # Query database for id
        user = db.execute("SELECT * FROM users WHERE id = ?", user_id)
        message = ""
        # Validating inputs
        # Ensure old password was submitted
        if not old:
            message = "Must submit current password"
        # Ensure new password was submitted
        elif not new:
            message = "Must submit new password"
        # Ensure confirmation was submitted
        elif not confirmation:
            message = "Must submit password confirmation"
        # Ensure old password is correct
        elif not check_password_hash(user[0]["hash"], old):
            message = "Wrong current password"
        # Ensure new password is the same as confirmation
        elif new != confirmation:
            message = "Confirmation password must match password"
        # Ensure new password is different from old password
        elif new == old:
            message = "New password must not match current password"
        # Ensure new password is strong
        elif not is_strong(new):
            message = "New password must be at least 8 characters long, must contain upper and lower letters, and at least one number"
        # If at least one input is not OK, render a message
        if message:
            return render_template("passwordchange.html", message=message, old=old, new=new, confirmation=confirmation, view="password_change")

        # All went well, register the new user and get his id. Doesn't store user's password in plain text
        db.execute("UPDATE users SET hash = ? WHERE id = ?", generate_password_hash(new), user_id)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("passwordchange.html", view="password_change")
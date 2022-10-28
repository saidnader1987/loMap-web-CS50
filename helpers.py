from functools import reduce
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import re

from flask import redirect, render_template, request, session
from functools import wraps

# Bank class
class Bank:
    def __init__(self, id, bank):
        self.id = id
        self.bank = bank
    
    # class method for validating a bank
    @classmethod
    def validate(cls, data, user_id, db, action):
        errors = {}
        cleaned_data = {}
        bank = data.get("bank").lower().title()
        banks = db.execute("SELECT * FROM banks WHERE user_id = ? AND bank = ?", user_id, bank)
        if action == "add":
            # Ensure bank was submitted   
            if bank:
                # bank already in database
                if len(banks) == 1: 
                    errors["bank"] = "Bank already in database"
                cleaned_data["bank"] = bank
            else: 
                errors["bank"] = "Must provide a bank"
        elif action == "edit":
            # Getting current info of the bank to edit
            user_bank_id = data.get("user_bank_id")
            bank_to_edit = db.execute("SELECT * FROM banks WHERE user_id = ? AND user_bank_id = ?", user_id, user_bank_id)[0]
            # Ensure bank was submitted
            if bank:
                # Bank already in database
                if len(banks) == 1 and bank != bank_to_edit["bank"]: 
                    errors["bank"] = "Bank already in database"
                cleaned_data["bank"] = bank
            else: 
                errors["bank"] = "Must provide a bank"
        return errors, cleaned_data


# Ammortization class
class Amortization:
    def __init__(self, id, loan_id, amort_value, amort_date):
        self.id = id
        self.loan_id = loan_id
        self.value = amort_value
        self.amort_date = datetime.strptime(amort_date, '%Y-%m-%d').date()

    # adding 2 amortizations or 1 amortization plus a float
    # self + other
    def __add__(self, other):
        try:
            other = float(other)
        except TypeError:
            return self.value + other.value
        else:
            return self.value + other

    # other + self
    def __radd__(self, other):
        try:
            other = float(other)
        except TypeError:
            return other.value + self.value
        else:
            return other + self.value

 # class method for validating an amortization
    @classmethod
    def validate(cls, data, user_id, db, action):
        errors = {}
        cleaned_data = {}
        # getting all loans of user
        loans = db.execute("SELECT * FROM loans WHERE user_id = ?", user_id)
        if action == "add":
            # loan_id
            if user_loan_id := data.get("user_loan_id"):
                try:
                    user_loan_id = int(user_loan_id)
                    if user_loan_id <= 0:
                        raise ValueError
                except ValueError:
                    errors["user_loan_id"] = "Loan id must be a positive integer"
                else:
                    # if loan_id not in loans
                    if not any(entry["user_loan_id"] == user_loan_id for entry in loans):
                        errors["user_loan_id"] =f"No loan with id: {user_loan_id} in database"
                    else:
                        cleaned_data["user_loan_id"] = user_loan_id
            else:
                errors["user_loan_id"] = "Must provide loan id"
            # amort_value
            if amort_value := data.get("amort_value"):
                try:
                    amort_value = float(amort_value)
                    if amort_value <= 0:
                        raise ValueError
                except ValueError:
                    errors["amort_value"] = "Amortization value must be a positive number"
                else:
                    loan = db.execute("SELECT * FROM loans WHERE user_id = ? AND user_loan_id = ?", user_id, user_loan_id)
                    if len(loan) != 0:
                        loan_principal = loan[0]["principal"]
                        if amort_value > loan_principal:
                            errors["amort_value"] = f"Amortization value (${amort_value:,.2f}) can not be greater than loan balance (${loan_principal:,.2f})"
                        else:
                            cleaned_data["amort_value"] = amort_value
                    else:
                        errors["amort_value"] = "Loan id must be defined in order to check if amortization value is valid"
            else: 
                errors["amort_value"] = "Must provide amortization value"
            # amort_date
            if amort_date := data.get("amort_date"):
                try:
                    amort_date = datetime.strptime(amort_date, '%Y-%m-%d').date()
                except ValueError:
                    errors["amort_date"] = "Invalid date format, should be YY-MM-DD"
                else:
                    loan = db.execute("SELECT * FROM loans WHERE user_id = ? AND user_loan_id = ?", user_id, user_loan_id)
                    if len(loan) != 0:
                        loan_issue_date = datetime.strptime(loan[0]["issue_date"], '%Y-%m-%d').date()
                        loan_maturity = datetime.strptime(loan[0]["maturity_date"], '%Y-%m-%d').date()
                        today = date.today()
                        if not amort_date <= today:
                            errors["amort_date"] = f"Amortization date ({str(amort_date)}) can not be greater than today ({str(today)})"
                        elif not loan_issue_date < amort_date <= loan_maturity:
                            errors["amort_date"] = f"Amortization date ({str(amort_date)}) can not be less than or equal to loan issue date ({str(loan_issue_date)}) and can not be greater than loan maturity date ({str(loan_maturity)})"
                        else:
                            cleaned_data["amort_date"] = amort_date
                    else:
                        errors["amort_date"] = "Loan id must be defined in order to check if amortization date is valid"
            else:
                errors["amort_date"] = "Must provide amortization date"

        elif action == "edit":
            # Getting info of the amortization to edit
            user_amortization_id = data.get("user_amortization_id")

            amortization_to_edit = db.execute("SELECT * FROM amortizations WHERE user_id = ? AND user_amortization_id = ?", user_id, user_amortization_id)[0]

            amortization_to_edit_value = amortization_to_edit["amort_value"]
            
            # Getting info of the amortization's loan
            loan_id = amortization_to_edit["loan_id"]
            loan = db.execute("SELECT * FROM loans WHERE id = ?", loan_id)[0]
            loan_principal = loan["principal"]
            loan_principal_before_amortization = loan_principal + amortization_to_edit_value
            loan_issue_date = datetime.strptime(loan["issue_date"], '%Y-%m-%d').date()
            loan_maturity = datetime.strptime(loan["maturity_date"], '%Y-%m-%d').date()
            cleaned_data["loan_id"] = loan_id
            # validate data to edit

            # amort_value
            if amort_value := data.get("amort_value"):
                try:
                    amort_value = float(amort_value)
                    if amort_value <= 0:
                        raise ValueError
                except ValueError:
                    errors["amort_value"] = "Amortization value must be a positive number"
                else:
                    if len(loan) != 0:
                        if amort_value > loan_principal_before_amortization:
                            errors["amort_value"] = f"Amortization value (${amort_value:,.2f}) can not be greater than loan balance before this amortization (${loan_principal_before_amortization:,.2f})"
                        else:
                            cleaned_data["amort_value"] = amort_value
                            cleaned_data["updated_principal"] = loan_principal_before_amortization - amort_value
                    else:
                        errors["amort_value"] = "Loan id must be defined in order to check if amortization value is valid"
            else: 
                errors["amort_value"] = "Must provide amortization value"
            # amort_date
            if amort_date := data.get("amort_date"):
                try:
                    amort_date = datetime.strptime(amort_date, '%Y-%m-%d').date()
                except ValueError:
                    errors["amort_date"] = "Invalid date format, should be YY-MM-DD"
                else:
                    if len(loan) != 0:
                        today = date.today()
                        if not amort_date <= today:
                            errors["amort_date"] = f"Amortization date ({str(amort_date)}) can not be greater than today ({str(today)})"
                        elif not loan_issue_date < amort_date <= loan_maturity:
                            errors["amort_date"] = f"Amortization date ({str(amort_date)}) can not be less than or equal to loan issue date ({str(loan_issue_date)}) and can not be greater than loan maturity date ({str(loan_maturity)})"
                        else:
                            cleaned_data["amort_date"] = amort_date
                    else:
                        errors["amort_date"] = "Loan id must be defined in order to check if amortization date is valid"
            else:
                errors["amort_date"] = "Must provide amortization date"
        return errors, cleaned_data


# Loan class
class Loan:
    def __init__(self, id, face_value, bank, issue_date, loan_term, payment_frequency, interest_rate, interest_rate_type,
    nominal_rate_compounding_period, interest_payment_frequency):
        # Loaded input or user's input
        self.id = id
        self.face_value = face_value
        self.bank = bank
        self.issue_date = datetime.strptime(issue_date, '%Y-%m-%d').date()
        self.loan_term = loan_term
        self.payment_frequency = payment_frequency
        self.interest_rate = interest_rate
        self.interest_rate_type = interest_rate_type
        self.nominal_rate_compounding_period = nominal_rate_compounding_period
        self.interest_payment_frequency = interest_payment_frequency

        # additional information
        # at moment of creation or at moment of editing loans. "Loan scheme"
        self.principal_balance = self.face_value
        self.amort_schedule = {} # Dictionary where keys are dates and values are scheduled amortizations
        self.scheduled_principals_b_amort = {}
        self.scheduled_principals_a_amort = {} # Dictionaries where keys are dates and values are principals in each period before and after amortization
        self.interest_payment_schedule = {} # Dictionary where keys are dates anda values are scheduled interest payments

        # amortizations and future cash flow based on actual amortizations
        self.actual_amortizations = [] # List containing amortization objects for this loan
        self.actual_amortizations_dict = {} # Dict containing amortizations for later reports
        self.actual_amort_schedule = self.amort_schedule # Similar to amort_schedule, but takes into account actual amortizations
        # interest
        self.actual_interest_payment_schedule = self.interest_payment_schedule # Similar to interest_payment_schedule but takes into account actual amortizations
        self.actual_principals_b_amort = self.scheduled_principals_b_amort
        self.actual_principals_a_amort = self.scheduled_principals_a_amort

    # add amortization method
    def add_amortization(self, amortization):
        # add amortization an update balance
        self.actual_amortizations.append(amortization)

    # Updating scheduled cash flow
    def update_sch(self):
        self.calculate_amort_schedule()
        self.calculate_principals()
        self.calculate_interest_payment_schedule()


    # Updating future (actual) cash flow based on actual amortizations
    def update_act(self):
        # if len(self.actual_amortizations) != 0:
        self.update_balance()
        self.actual_amort_schedule, self.actual_amortizations_dict = generate_actual_amortization_schedule(self.issue_date, self.amort_schedule, self.actual_amortizations, self.principal_balance, self.scheduled_principals_a_amort)
        self.actual_principals_b_amort, self.actual_principals_a_amort = generate_principals(self.face_value,
        self.loan_term, self.actual_amort_schedule, self.issue_date)
        self.actual_interest_payment_schedule = generate_interests(self.actual_principals_b_amort, self.interest_rate,
        self.nominal_rate_compounding_period, self.interest_payment_frequency, self.issue_date)


    def calculate_amort_schedule(self):
        self.amort_schedule = generate_amortizations(self.face_value, self.loan_term,self.issue_date, self.payment_frequency)


    def calculate_interest_payment_schedule(self):
        self.interest_payment_schedule = generate_interests(self.scheduled_principals_b_amort, self.interest_rate,
        self.nominal_rate_compounding_period, self.interest_payment_frequency, self.issue_date)


    def calculate_principals(self):
        self.scheduled_principals_b_amort, self.scheduled_principals_a_amort = generate_principals(self.face_value,
        self.loan_term, self.amort_schedule, self.issue_date)
    

    def update_balance(self):
        self.principal_balance = calculate_principal_balance(self.face_value, self.actual_amortizations)
    
    # class method for validating a loan
    @classmethod
    def validate(cls, data, user_id, db, action):
        errors = {}
        cleaned_data = {}
        bank = data.get("bank").lower().title()
        banks = db.execute("SELECT * FROM banks WHERE user_id = ? AND bank = ?", user_id, bank)
        frequencies =  db.execute("SELECT * FROM frequencies")
        compounding_periods = db.execute("SELECT * FROM frequencies WHERE frequency != 'At maturity'")
        types = db.execute("SELECT * FROM types")
        if action == "add":
            # face_value
            if face_value := data.get("face_value"):
                try:
                    face_value = float(face_value)
                    if face_value <= 0:
                        raise ValueError
                except ValueError:
                    errors["face_value"] = "Face value must be a positive number"
                else:
                    cleaned_data["face_value"] = face_value
            else: 
                errors["face_value"] = "Must provide face value"
            # bank
            if bank:
                # if bank not in banks
                if not any(entry["bank"] == bank.lower().title() for entry in banks):
                    errors["bank"] = "Bank does not exist in database"
                cleaned_data["bank"] = bank
            else: 
                errors["bank"] = "Must provide bank"
            # issue_date
            if issue_date := data.get("issue_date"):
                try:
                    issue_date = datetime.strptime(issue_date, '%Y-%m-%d').date()
                except ValueError:
                    errors["issue_date"] = "Invalid date format, should be YY-MM-DD"
                else: 
                    cleaned_data["issue_date"] = issue_date
            else:
                errors["issue_date"] = "Must provide issue date"
            # loan_term
            if loan_term := data.get("loan_term"):
                try:
                    loan_term = int(loan_term)
                    if loan_term <= 0:
                        raise ValueError
                except ValueError:
                    errors["loan_term"] = "Loan term must be a positive integer. Floating point numbers are not allowed."
                else:
                    cleaned_data["loan_term"] = loan_term
            else:
                errors["loan_term"] = "Must provide loan term"
            # payment_frequency
            if payment_frequency := data.get("payment_frequency"):
                # Make sure when you do calculations for frequencies, loan term is defined and is an int
                if loan_term := data.get("loan_term"):
                    try:
                        loan_term = int(loan_term)
                        if loan_term <= 0:
                            raise ValueError
                    except ValueError:
                        errors["payment_frequency"] = "Loan term not valid. Can not check if frequency is valid"
                    else:
                        # checking if frequency exists in database
                        if not any(entry["frequency"] == payment_frequency for entry in frequencies):
                            errors["payment_frequency"] = "Payment frequency does not exist in the database"
                        # checking if frequency match loan term
                        elif not check_frequency(loan_term, payment_frequency, frequencies):
                            months = get_dict(frequencies, payment_frequency, "frequency")["months"]
                            errors["payment_frequency"] = f"Payment frequency and loan term does not match. Loan term ({loan_term}) not divisible by months in {payment_frequency} frequency ({months})"
                        else:
                            cleaned_data["payment_frequency"] = payment_frequency
            else:
                errors["payment_frequency"] = "Must provide payment frequency"
            # interest payment_frequency
            if interest_payment_frequency := data.get("interest_payment_frequency"):
                # Make sure when you do calculations for frequencies, loan term is defined and is an int
                if loan_term := data.get("loan_term"):
                    try:
                        loan_term = int(loan_term)
                        if loan_term <= 0:
                            raise ValueError
                    except ValueError:
                        errors["interest_payment_frequency"] = "Loan term not valid. Can not check if frequency is valid"
                    else:
                        # checking if frequency exists in database
                        if not any(entry["frequency"] == interest_payment_frequency for entry in frequencies):
                            errors["interest_payment_frequency"] = "Interest payment frequency does not exist in the database"
                        # checking if frequency match loan term
                        elif not check_frequency(loan_term, interest_payment_frequency, frequencies):
                            months = get_dict(frequencies, interest_payment_frequency, "frequency")["months"]
                            errors["interest_payment_frequency"] = f"Interest payment frequency and loan term does not match. Loan term ({loan_term}) not divisible by months in {interest_payment_frequency} frequency ({months})"
                        else:
                            cleaned_data["interest_payment_frequency"] = interest_payment_frequency
            else:
                errors["interest_payment_frequency"] = "Must provide interest payment frequency"
            # interest_rate
            if interest_rate := data.get("interest_rate"):
                try:
                    interest_rate = float(interest_rate)
                    if interest_rate <= 0 or interest_rate > 100:
                        raise ValueError
                except ValueError:
                    errors["interest_rate"] = "Interest rate must be a positive number less or equal than 100"
                else:
                    cleaned_data["interest_rate"] = interest_rate
            else: 
                errors["interest_rate"] = "Must provide interest rate"
            # interest_rate_type
            if interest_rate_type := data.get("interest_rate_type").lower().title():
                # checking if rate type exists in database
                if not any(entry["type"] == interest_rate_type for entry in types):
                    errors["interest_rate_type"] = "Interest rate type does not exist in the database"
                cleaned_data["interest_rate_type"] = interest_rate_type
            else: 
                errors["interest_rate_type"] = "Must provide interest rate type"
            # nominal_rate_compounding_periods
            if nominal_rate_compounding_period := data.get("nominal_rate_compounding_period"):
                # Make sure when you do comparissons for compounding periods, rate type is defined and is valid
                if interest_rate_type := data.get("interest_rate_type").lower().title():
                    # checking if rate type exists in database
                    if not any(entry["type"] == interest_rate_type for entry in types):
                        errors["nominal_rate_compounding_period"] = "Interest rate type not valid. Can not check if nominal rate compounding period is valid"
                    else:
                        # checking if frequency exists in database
                        if not any(entry["frequency"] == nominal_rate_compounding_period for entry in compounding_periods):
                            errors["nominal_rate_compounding_period"] = "Nominal rate compounding period does not exist in the database"
                        # checking if compounding period match rate type
                        elif nominal_rate_compounding_period == "Annually" and interest_rate_type != "Effective":
                            errors["nominal_rate_compounding_period"] = "If nominal rate compounding period is set to annually, interest rate type must be set to effective" 
                            errors["interest_rate_type"] = "If nominal rate compounding period is set to annually, interest rate type must be set to effective" 
                        elif nominal_rate_compounding_period != "Annually" and interest_rate_type == "Effective":
                            errors["nominal_rate_compounding_period"] = "If nominal rate compounding period is not set to annually, interest rate type must not be set to effective" 
                            errors["interest_rate_type"] = "If nominal rate compounding period is not set to annually, interest rate type must not be set to effective" 
                        else:
                            cleaned_data["nominal_rate_compounding_period"] = nominal_rate_compounding_period
            else:
                errors["nominal_rate_compounding_period"] = "Must provide nominal rate compounding period"
        elif action == "edit":
            # getting info of the loan to edit
            user_loan_id = data.get("user_loan_id")
            loan_to_edit = db.execute("""SELECT loans.id, 
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
            # getting loan's amortizations info
            loan_id = loan_to_edit["id"]
            amortizations = db.execute("SELECT * FROM amortizations WHERE loan_id = ?", loan_id)
            if len(amortizations) != 0:
                amortized = db.execute("SELECT SUM(amort_value) AS amortized FROM amortizations WHERE loan_id = ?", loan_id)[0]["amortized"]

                min_amort_date = datetime.strptime(db.execute("SELECT MIN(amort_date) AS min_date FROM amortizations WHERE loan_id = ?", loan_id)[0]["min_date"], '%Y-%m-%d').date()

                max_amort_date = datetime.strptime(db.execute("SELECT MAX(amort_date) AS max_date FROM amortizations WHERE loan_id = ?", loan_id)[0]["max_date"],'%Y-%m-%d').date()

            # validate info

            # face_value
            if face_value := data.get("face_value"):
                try:
                    face_value = float(face_value)
                    if face_value <= 0:
                        raise ValueError
                except ValueError:
                    errors["face_value"] = "Face value must be a positive number"
                else:
                    if len(amortizations) != 0 and face_value < amortized:
                            errors["face_value"] = f"Face value (${face_value:,.2f}) can not be less than the sum of loan's amortizations (${amortized:,.2f})"
                    else:
                        cleaned_data["face_value"] = face_value
                        if len(amortizations) != 0:
                            cleaned_data["principal"] = face_value - amortized
                        else:
                            cleaned_data["principal"] = face_value

            else: 
                errors["face_value"] = "Must provide face value"
            # bank
            if bank:
                # if bank not in banks
                if not any(entry["bank"] == bank.lower().title() for entry in banks):
                    errors["bank"] = "Bank does not exist in database"
                cleaned_data["bank"] = bank
            else: 
                errors["bank"] = "Must provide bank"
            # issue_date
            if issue_date := data.get("issue_date"):
                # Make sure when you do calculations for issue_date, loan term is defined and is an int
                if loan_term := data.get("loan_term"):
                    try:
                        loan_term = int(loan_term)
                        if loan_term <= 0:
                            raise ValueError
                    except ValueError:
                        errors["issue_date"] = "Loan term not valid. Can not check if issue date is valid"
                    else:
                        try:
                            issue_date = datetime.strptime(issue_date, '%Y-%m-%d').date()
                            maturity_date = issue_date + relativedelta(months = loan_term)
                        except ValueError:
                            errors["issue_date"] = "Invalid date format, should be YY-MM-DD"
                        else: 
                            if len(amortizations) != 0 and (issue_date >= min_amort_date or maturity_date < max_amort_date):
                                errors["issue_date"] = f"Issue date ({str(issue_date)}) can not be greater than or equal to min amortization date ({str(min_amort_date)}) and loan maturity ({str(maturity_date)}) can not be less than max amortization date ({str(max_amort_date)})"
                            # elif len(amortizations) != 0 and maturity_date < max_amort_date:
                            #     errors["issue_date"] = f"Loan maturity ({str(maturity_date)}) can not be less than max amortization date ({str(max_amort_date)})"
                            else:
                                cleaned_data["issue_date"] = issue_date
            else:
                errors["issue_date"] = "Must provide issue date"
            # loan_term
            if loan_term := data.get("loan_term"):
                # Make sure when you do calculations for maturity_date, issue date is defined and valid
                if issue_date := data.get("issue_date"):
                    try:
                        issue_date = datetime.strptime(issue_date, '%Y-%m-%d').date()
                    except ValueError:
                        errors["loan_term"] = "Issue date not valid. Can not check if loan term is valid"
                    else:
                        try:
                            loan_term = int(loan_term)
                            if loan_term <= 0:
                                raise ValueError
                            maturity_date = issue_date + relativedelta(months = loan_term)
                        except ValueError:
                            errors["loan_term"] = "Loan term must be a positive integer. Floating point numbers are not allowed."
                        else:
                            if len(amortizations) != 0 and (issue_date >= min_amort_date or maturity_date < max_amort_date):
                                errors["loan_term"] = f"Issue date ({str(issue_date)}) can not be greater than or equal to min amortization date ({str(min_amort_date)}) and loan maturity ({str(maturity_date)}) can not be less than max amortization date ({str(max_amort_date)})"
                            else:
                                cleaned_data["loan_term"] = loan_term
            else:
                errors["loan_term"] = "Must provide loan term"
            # payment_frequency
            if payment_frequency := data.get("payment_frequency"):
                # Make sure when you do calculations for frequencies, loan term is defined and is an int
                if loan_term := data.get("loan_term"):
                    try:
                        loan_term = int(loan_term)
                        if loan_term <= 0:
                            raise ValueError
                    except ValueError:
                        errors["payment_frequency"] = "Loan term not valid. Can not check if frequency is valid"
                    else:
                        # checking if frequency exists in database
                        if not any(entry["frequency"] == payment_frequency for entry in frequencies):
                            errors["payment_frequency"] = "Payment frequency does not exist in the database"
                        # checking if frequency match loan term
                        elif not check_frequency(loan_term, payment_frequency, frequencies):
                            months = get_dict(frequencies, payment_frequency, "frequency")["months"]
                            errors["payment_frequency"] = f"Payment frequency and loan term does not match. Loan term ({loan_term}) not divisible by months in {payment_frequency} frequency ({months})"
                        else:
                            cleaned_data["payment_frequency"] = payment_frequency
            else:
                errors["payment_frequency"] = "Must provide payment frequency"
            # interest payment_frequency
            if interest_payment_frequency := data.get("interest_payment_frequency"):
                # Make sure when you do calculations for frequencies, loan term is defined and is an int
                if loan_term := data.get("loan_term"):
                    try:
                        loan_term = int(loan_term)
                        if loan_term <= 0:
                            raise ValueError
                    except ValueError:
                        errors["interest_payment_frequency"] = "Loan term not valid. Can not check if frequency is valid"
                    else:
                        # checking if frequency exists in database
                        if not any(entry["frequency"] == interest_payment_frequency for entry in frequencies):
                            errors["interest_payment_frequency"] = "Interest payment frequency does not exist in the database"
                        # checking if frequency match loan term
                        elif not check_frequency(loan_term, interest_payment_frequency, frequencies):
                            months = get_dict(frequencies, interest_payment_frequency, "frequency")["months"]
                            errors["interest_payment_frequency"] = f"Interest payment frequency and loan term does not match. Loan term ({loan_term}) not divisible by months in {interest_payment_frequency} frequency ({months})"
                        else:
                            cleaned_data["interest_payment_frequency"] = interest_payment_frequency
            else:
                errors["interest_payment_frequency"] = "Must provide interest payment frequency"
            # interest_rate
            if interest_rate := data.get("interest_rate"):
                try:
                    interest_rate = float(interest_rate)
                    if interest_rate <= 0 or interest_rate > 100:
                        raise ValueError
                except ValueError:
                    errors["interest_rate"] = "Interest rate must be a positive number less or equal than 100"
                else:
                    cleaned_data["interest_rate"] = interest_rate
            else: 
                errors["interest_rate"] = "Must provide interest rate"
            # interest_rate_type
            if interest_rate_type := data.get("interest_rate_type").lower().title():
                # checking if rate type exists in database
                if not any(entry["type"] == interest_rate_type for entry in types):
                    errors["interest_rate_type"] = "Interest rate type does not exist in the database"
                cleaned_data["interest_rate_type"] = interest_rate_type
            else: 
                errors["interest_rate_type"] = "Must provide interest rate type"
            # nominal_rate_compounding_periods
            if nominal_rate_compounding_period := data.get("nominal_rate_compounding_period"):
                # Make sure when you do comparissons for compounding periods, rate type is defined and is valid
                if interest_rate_type := data.get("interest_rate_type").lower().title():
                    # checking if rate type exists in database
                    if not any(entry["type"] == interest_rate_type for entry in types):
                        errors["nominal_rate_compounding_period"] = "Interest rate type not valid. Can not check if nominal rate compounding period is valid"
                    else:
                        # checking if frequency exists in database
                        if not any(entry["frequency"] == nominal_rate_compounding_period for entry in compounding_periods):
                            errors["nominal_rate_compounding_period"] = "Nominal rate compounding period does not exist in the database"
                        # checking if compounding period match rate type
                        elif nominal_rate_compounding_period == "Annually" and interest_rate_type != "Effective":
                            errors["nominal_rate_compounding_period"] = "If nominal rate compounding period is set to annually, interest rate type must be set to effective" 
                            errors["interest_rate_type"] = "If nominal rate compounding period is set to annually, interest rate type must be set to effective" 
                        elif nominal_rate_compounding_period != "Annually" and interest_rate_type == "Effective":
                            errors["nominal_rate_compounding_period"] = "If nominal rate compounding period is not set to annually, interest rate type must not be set to effective" 
                            errors["interest_rate_type"] = "If nominal rate compounding period is not set to annually, interest rate type must not be set to effective" 
                        else:
                            cleaned_data["nominal_rate_compounding_period"] = nominal_rate_compounding_period
            else:
                errors["nominal_rate_compounding_period"] = "Must provide nominal rate compounding period"
        return errors, cleaned_data


# Helpers for flask

def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def is_strong(p):
    """
    Return True if p is at least eight characters long, contains upper and lower and has at least one digit
    Return False otherwise 
    """
    password_regex = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9]).{8,}$")

    if password_regex.search(p):
        return True
    else:
        return False


def get_next_id(table, user_id, db):
    records = db.execute(f"SELECT * FROM {table}s WHERE user_id = ?", user_id)
    max_record = db.execute(f"SELECT MAX(user_{table}_id) AS max FROM {table}s WHERE user_id = ?", user_id)[0]
    next_id = max_record.get("max", 0) + 1 if max_record.get("max", 0) else 1
    return next_id

def usd(value):
    """Format value as USD."""
    return f"${value:,.2f}"


def percentage(value):
    """Format value as %."""
    return f"{value:,.2f}%"


def calculate_future_date(dt, plus):
    return dt + relativedelta(months=plus)


# Constants
MONTHS = {
    "Monthly": 1,
    "Bi-monthly": 2,
    "Quarterly": 3,
    "Semi-annually": 6,
    "Annually": 12
}

PERIODS = {
    "Monthly": 12,
    "Bi-monthly": 6,
    "Quarterly": 4,
    "Semi-annually": 2,
    "Annually": 1
}

TYPES = ["Effective", "Nominal"]


# Functions
def check_frequency(term, frequency, frequencies):
    """
    Input: term, an int specifying the number of months of one loan
    Input: frequency, a string specifying the payment frequency
    Returns True if the frequency exists in the PERIODS dict and match the term, otherwise False
    """
    if frequency == "At maturity":
        return True
    elif any(entry["frequency"] == frequency for entry in frequencies):
        # months in frequency period
        months = get_dict(frequencies, frequency, "frequency")["months"]
        # term is divisible by months
        if term % months == 0:
            return True
        else:
            return False
    else:
        return False


# def get_obj(l, v, lookup_att):
#     """
#     Input: l, a list of objects
#     Input: v, the value of an attribute of the object
#     Input: lookup_att, the name of the attribute of the object
#     Returns obj if the object is found, otherwise None
#     """
#     for obj in l:
#         if getattr(obj, lookup_att) == v:
#             return obj
#     return None


def get_dict(l, v, lookup_key):
    """
    Input: l, a list of dictionaries
    Input: v, the value of the key of the dictionary to look up
    Input: lookup_key, the name of the key of the dictionary to look up
    Returns dictionary if the dictionary is found, otherwise None
    """
    for entry in l:
        if entry.get(lookup_key) == v:
            return entry
    return None


def generate_amortizations(face, term, issue, frequency):
    amortizations = {}
    # calculate amortization periods
    # if frequency != "at maturity":
    #     n = term / MONTHS[frequency]
    # else:
    #     n = 1
    n = term / MONTHS[frequency] if frequency != "At maturity" else 1
    # calculate scheduled amortizations
    sch_amort = round(face / n, 2)
    for i in range(term):
        # generate monthly periods
        date_i = issue + relativedelta(months=i + 1)
        # checking if period divided by MONTHS has a remainder
        if frequency != "At maturity" and (i + 1) % MONTHS[frequency] == 0:
            amortizations[date_i] = sch_amort
        elif frequency == "At maturity" and i + 1 == term:
            amortizations[date_i] = sch_amort
        else:
            amortizations[date_i] = 0
    return amortizations


def generate_actual_amortization_schedule(issue, sch_amortizations, actual_amortizations, principal, sch_principals_a_amort):
    # getting loan term
    term = len(sch_amortizations)
    # getting loan issue_date
    # issue = min(sch_amortizations) + relativedelta(months=- 1)
    # Creating the dict that will be returned
    actual_amortization_schedule = {}
    actual_amortizations_dict = {}
    # getting remaining periods, number of amortizations and future amortization value
    # max_amort_date = max(actual_amortizations, key = lambda x : x.amort_date).amort_date
    # generating all periods
    check = False
    today = date.today()
    last_date = max(sch_amortizations)

    if today < last_date:
        for i in range(term):
            date_i = issue + relativedelta(months=i + 1)
            date_i_minus_1 = issue + relativedelta(months = i)
            # date_i_minus_1 = date_i + relativedelta(months= - 1)
            actual_amort_in_period = sum(amort.value for amort in actual_amortizations if amort.amort_date > date_i_minus_1
            and amort.amort_date <= date_i)
            # Period less than today
            if date_i_minus_1 < today and date_i < today:
                actual_amortization_schedule[date_i] = actual_amort_in_period
                actual_amortizations_dict[date_i] = actual_amort_in_period
            # Period == today
            elif date_i_minus_1 < today <= date_i:
                # actual_amort_in_period = sum(amort.value for amort in actual_amortizations if amort.amort_date > date_i_minus_1
                # and amort.amort_date <= date_i)
                # Checking to see if there's a scheduled amortization in period
                # Period is not an amortization payment month
                if round(sch_amortizations[date_i],0) == 0:
                    actual_amortization_schedule[date_i] = actual_amort_in_period
                    actual_amortizations_dict[date_i] = actual_amort_in_period
                # Amortization payment month
                else:
                    # Must meet condition that actual principal == scheduled principal
                    due = round(principal - sch_principals_a_amort[date_i], 1)
                    if due > 0 and check == False:
                        actual_amortization_schedule[date_i] = actual_amort_in_period + due
                        actual_amortizations_dict[date_i] = actual_amort_in_period
                        check = True
                    else:
                        actual_amortization_schedule[date_i] = actual_amort_in_period
                        actual_amortizations_dict[date_i] = actual_amort_in_period
            # Period is greater than today
            elif today <= date_i_minus_1:
                if not check:
                    due = round(principal - sch_principals_a_amort[date_i], 1)
                     # Checking to see if there's a scheduled amortization in period
                    # Period is not an amortization payment month
                    if round(sch_amortizations[date_i],0) == 0:
                        actual_amortization_schedule[date_i] = actual_amort_in_period
                    else:
                        if due > 0:
                            actual_amortization_schedule[date_i] = due
                            check = True
                        elif due <= 0:
                            actual_amortization_schedule[date_i] = 0
                else:
                    actual_amortization_schedule[date_i] = sch_amortizations[date_i]
                actual_amortizations_dict[date_i] = 0
    else:
        for i in range(term):
            date_i = issue + relativedelta(months=i + 1)
            date_i_minus_1 = issue + relativedelta(months = i)
            actual_amort_in_period = sum(amort.value for amort in actual_amortizations if amort.amort_date > date_i_minus_1
            and amort.amort_date <= date_i)
            # Period differente than last period
            if i != term - 1:
                actual_amortization_schedule[date_i] = actual_amort_in_period
                actual_amortizations_dict[date_i] = actual_amort_in_period
            else:
                # due = round(principal - sch_principals_a_amort[date_i], 1)
                actual_amortization_schedule[date_i] = principal
                actual_amortizations_dict[date_i] = actual_amort_in_period
    return actual_amortization_schedule, actual_amortizations_dict


def generate_principals(face, term, cash_flow, issue):
    principals_a = {}
    principals_b = {}
    principal = face
    for i in range(term):
        date_i = issue + relativedelta(months=i + 1)
        sch_amort = cash_flow[date_i]
        principal -= sch_amort
        principals_a[date_i] = round(principal, 2)
        principals_b[date_i] = round(principal + sch_amort, 2)
    return principals_b , principals_a


def generate_interests(cash_flow, rate, comp_period, frequency, issue):
# def generate_interests(rate, period):
    interests = {}
    # calculate monthly rate
    i_m = convert_nominal_to_monthly_effective(rate, comp_period)
    acc_interest = 0
    # calculate months until interest payment
    n = MONTHS[frequency] if (frequency != "At maturity") else len(cash_flow)
    for i in range(len(cash_flow)):
        # generate monthly periods
        date_i = issue + relativedelta(months=i + 1)
        # calculate monthly interest
        interest_m = calculate_interest(i_m, cash_flow[date_i])
        # future value of monthly interest at payment date
        comp_periods_i = (n - (i + 1) % n) if (i + 1) % n != 0 else 0
        fv_interest_m = interest_m * (1 + i_m / 100) ** comp_periods_i
        # accrued interest
        acc_interest += fv_interest_m
        if frequency != "At maturity" and (i + 1) % MONTHS[frequency] == 0:
            interests[date_i] = round(acc_interest, 2)
            acc_interest = 0
        elif frequency == "At maturity" and i + 1 == len(cash_flow):
            interests[date_i] = round(acc_interest, 2)
        else:
            interests[date_i] = 0
    return interests


def convert_nominal_to_monthly_effective(rate, comp_period):
    nominal_comp_periods = PERIODS[comp_period]
    # calculate the effective rate according to the compounding periods of nominal rate
    effective_rate = (rate / nominal_comp_periods)
    # calculate effective monthly rate
    effective_monthly_rate = ((1 + effective_rate / 100) ** (1/MONTHS[comp_period]) - 1)
    return round(effective_monthly_rate * 100, 4)


def calculate_interest(rate:float, value:float) -> float:
    return round(rate * value / 100, 2)


def calculate_principal_balance(face:float, am_list:list)->float:
    if len(am_list) > 1:
        am = reduce(lambda a, b: a + b, am_list)
        return face - am
    elif len(am_list) == 1:
        return face - am_list[0].value
    else:
        return face


def cash_flow_report(loan):
    report = []
    # wrapper = textwrap.TextWrapper(width=50)
    for period in loan.amort_schedule:
        cash_flow_info = {
            "date": period,
            "scheduled_principals_b_amort": f"${loan.scheduled_principals_b_amort[period]:,.2f}",
            "amort_schedule": f"${loan.amort_schedule[period]:,.2f}",
            "interest_payment_schedule": f"${loan.interest_payment_schedule[period]:,.2f}",
            "actual_principals_b_amort": f"${loan.actual_principals_b_amort[period]:,.2f}", #if len(loan.actual_amortizations) != 0 else
            #f"${loan.scheduled_principals_b_amort[period]:,.1f}",
            "actual_amortizations": f"${loan.actual_amortizations_dict[period]:,.2f}", #if len(loan.actual_amortizations) != 0 else
            #f"${0:,.1f}",
            "actual_amort_schedule": f"${loan.actual_amort_schedule[period]:,.2f}", #if len(loan.actual_amortizations) != 0 else
            #f"${loan.amort_schedule[period]:,.1f}",
            "actual_interest_payment_schedule": f"${loan.actual_interest_payment_schedule[period]:,.2f}", #if len(loan.actual_amortizations) != 0 else
            #f"${loan.interest_payment_schedule[period]:,.1f}"
        }
        report.append(cash_flow_info)
    return report



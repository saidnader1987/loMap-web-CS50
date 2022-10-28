# loMap
#### Video Demo:  <https://www.youtube.com/watch?v=YvOX_I7KYKE>
#### Description: Loan management web application

## Concept
_loMap_ is a management web application for your loans. Its backend is written in Python using Flask and its frontend uses raw CSS instead of a library like Bootstrap. It uses several standard libraries and packages.

With this program you can manage a database for your loans and the amortizations you pay for those loans, and ultimately it can show you valuable reports of your data such as cash flows.

## How it works
The first step is to register. You need to provide a unique username that it is not being used by someone else, an a password which must be at least eight characters long, contains upper and lower letters and has at least one digit. Then you can log in to start using the application. 

Then next step is to add banks to the database, then you add loans and finally you add amortizations for those loans. You can also edit and delete data provided no rule is violated. All your data is stored in different tables inside a SQLite database.

The data you input when you create, edit or delete data is constrained by basic rules as I will later explain. You can interact with the application via 5 basic options: loans, amortizations, banks, change password and log out.

## Loans
In this option you can view all the basic info of your loans. You can filter the info so you see only the loans you want to see. You can also add, edit, amortize and delete loans. On each loan there is an option to see its cash flow (more on that later).

## Amortizations
In this option you can view all the basic info of your amortizations. You can filter the info so you see only the amortizations you want to see. You can also add and edit amortizations.

## Banks
In this option you can view all the basic info of your banks. You can filter the info so you see only the banks you want to see. You can also add and edit banks.

### Data
All of your data is stored in a SQLite file called loMap.db which contains several tables to keep track of the state of the application.

## Change password
In this option you can change your password as it name implies

## Log out
With this option you log out of the application

### Rules
Its worth noting that all validations are performed in the backend and not just in the frontend.

1. Banks
  - Id is set automatically and can not be modified
  - The same bank can not be added to the database twice
  - You can not delete a bank that is being used by a loan

2. Loans
  - Id is set automatically and can not be modified
  - One bank in database is the minimum requirement for adding loans
  - Loan face value must be a positive integer or float
  - Loan bank must be in bank database
  - Loan issue date must be a valid date in YYYY-MM-DD format
  - Loan term must be a positive integer in months. Floats are not allowed
  - Loan payment frequency and interest paymente frequency can be set to monthly, bi-monthly, quarterly, semi-annually, annually and at maturity and must match loan term. Namely, you can not have a bi-monthly payment frequency if your term is 3 months, because otherwise you will be missing 1 month. Don't worry about the math, the program will do it for you and explain when something is awry
  - Loan interest rate must be a positive integer or float between 0 and 100 percent
  - Loan interest rate type can be set to effective or to nominal. If it's set to effective the nominal rate compounding period must be set to annually
  - Conversely, if loan ineterst rate type is set to nominal, the nominal rate compounding period can be set to monthly, bi-monthly, quarterly, semi-annually and annually
  - You can not delete a loan that has amortizations associated with it

  3. Amortizations
   - Id is set automatically and can not be modified
   - You can only add amortizations to previously created loans. One loan in database is the minimum requirement for adding amortizations
   - Amortization value can not be greater than loan principal (the ammount of money you owe for a loan at any particular time)
   - Amortization date can not be greater than current date and must be in loan's range. That is, amortization date must be greater than loan issue date and lesser than or equal to loan maturity date (issue date + term)

You can freely edit and delete any entry in loans, amortizations and banks database as long as the change you made does not violate any rule. For instance, if you have already an amortization for a loan on a specific date, when you try to edit that loan issue date, you must take into account the date of that amortization. Conversely, if the loan does not have amortizations yet, you can freely edit its issue date.

### Cash flow
This is where all the magic happens, where all of the financial math is applied. You must choose a loan and then the program will show you a report containing the following information:
- A row for each month of your loan from issue date to maturity date
- A column for the scheduled principal (money you owe each period for a particular loan) according to the amortization payment schedule
- Two columns for the scheduled amortization and interest payments according to the basic data of your loan (i.e. interest rate, payment frequencies, rate type, etc.). These columns **do not take into account the amortizations already made**
- A column for your actual amortizations (not to be confused with the scheduled amortizations). The amortization is placed on the period it took place; for instance if the issue date of the loan is the first of January 2022, and the first amortization was on January 23rd, the amortization will be shown on the first of February 2022 (the period it took place) for simplicity.
- Two columns for the actual scheduled amortization and actual scheduled interest payments **taking into account the amortizations already made**
- A column for the actual scheduled principal **taking into account the amortizations already made**

And that's it, that's loMap. it's very intuitive and it will provide you explanations for each step and each rule you violate. I hope you have fun with it.

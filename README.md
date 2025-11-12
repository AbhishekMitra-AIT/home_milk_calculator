# home_milk_calculator
Daily Milk Delivery Management System - Developed a web-based solution to digitize and automate household milk delivery tracking, eliminating manual record-keeping errors.

Key Features:

    CRUD operations for daily milk quantity entries with date management
    Automated cost calculations (₹50/liter) and monthly aggregations
    Chronological data organization with month-wise breakdowns
    Responsive UI with edit/delete functionality.

Technical Implementation:

    Backend: Flask framework with SQLAlchemy ORM
    Database: SQLite (local) / PostgreSQL (production)
    Deployment: Railway platform with Gunicorn WSGI server
    Database migration scripts for schema updates


Ref using python anywhere - https://www.youtube.com/watch?v=Bx_jHawKn5A

website - [https://abhishekmitra.pythonanywhere.com/ -> currently debugging, having bugs..](https://web-production-01a84.up.railway.app/)

steps for running app in local server
1. create a virtual environment (python -m venv venv)
2. activate the virtual environment for windows (venv\Scripts\activate)
3. install the dependencies from reuirements.txt (pip install -r requirements.txt)
4. run the app (python app.py)


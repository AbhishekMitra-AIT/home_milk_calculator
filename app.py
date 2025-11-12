from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float
import datetime as dt, os, secrets
from collections import defaultdict

# how initialise the db object, define your model, 
# and create the table. 
class Base(DeclarativeBase):
  pass

db = SQLAlchemy(model_class=Base)

# create the app
app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# configure the SQLite database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///milk-calculation.db"

# initialize the app with the extension
db.init_app(app)

class Milk(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(250), nullable=True)
    milk_qty: Mapped[float] = mapped_column(Float, nullable=True)
    cost: Mapped[float] = mapped_column(Float, nullable=True)
    month_year: Mapped[str] = mapped_column(String(50), nullable=True)  # Store "MM-YYYY"

# Create table schema in the database. Requires application context.
with app.app_context():
    db.create_all()

# helper to extract month-year from date string
def get_month_year(date_str):
    """Extract MM-YYYY from DD-MM-YYYY date string"""
    if date_str:
        parts = date_str.split('-')
        if len(parts) == 3:
            return f"{parts[1]}-{parts[2]}"  # MM-YYYY
    return None

# helper to recalculate monthly totals
def recalc_monthly_totals():
    with app.app_context():
        result = db.session.execute(db.select(Milk).order_by(Milk.date, Milk.id))
        records = list(result.scalars())
        
        # Group by month_year and calculate totals per month
        monthly_groups = defaultdict(list)
        for r in records:
            if r.month_year:
                monthly_groups[r.month_year].append(r)
        
        db.session.commit()

# Read All Records
with app.app_context():
    result = db.session.execute(db.select(Milk).order_by(Milk.date, Milk.id))
    milk_data = list(result.scalars())  # Convert to list while session is open
if milk_data==[]:
    print("No milk data found in the database.")
else:
  for milk in milk_data: 
    print("Milk Data:")
    print(f"{milk.id} - {milk.date} - {milk.milk_qty} - {milk.cost} - {milk.month_year}")


@app.route('/')
def home():
    with app.app_context():
        result = db.session.execute(db.select(Milk).order_by(Milk.date.desc(), Milk.id.desc()))
        milk_data = list(result.scalars())
        
        # Group records by month-year
        monthly_data = defaultdict(list)
        for record in milk_data:
            if record.month_year:
                monthly_data[record.month_year].append(record)
        
        # Calculate monthly totals
        monthly_totals = {}
        for month, records in monthly_data.items():
            monthly_totals[month] = sum((r.cost or 0.0) for r in records)
        
        # Sort months in descending order (most recent first)
        sorted_months = sorted(monthly_data.keys(), key=lambda x: dt.datetime.strptime(x, "%m-%Y"), reverse=True)
        
        # Compute overall total
        total_cost_all = sum((m.cost or 0.0) for m in milk_data)
    
    return render_template("index.html", 
                         monthly_data=monthly_data, 
                         sorted_months=sorted_months,
                         monthly_totals=monthly_totals,
                         total=total_cost_all)

@app.route("/edit", methods=["GET", "POST"])
def edit():
    if request.method == "POST":
        # Update record
        milk_id = int(request.form.get("id"))
        milk_record = db.get_or_404(Milk, milk_id)
        
        # Handle new date (HTML date input returns YYYY-MM-DD)
        new_date_raw = request.form.get("date")
        if new_date_raw:
            try:
                parsed = dt.datetime.strptime(new_date_raw, "%Y-%m-%d")
                milk_record.date = parsed.strftime("%d-%m-%Y")
                milk_record.month_year = parsed.strftime("%m-%Y")
            except (ValueError, TypeError):
                # keep existing date on parse error
                pass

        try:
            new_qty = float(request.form.get("number", 0))
        except (ValueError, TypeError):
            return redirect(url_for("home"))

        new_cost = new_qty * 50.0

        milk_record.milk_qty = new_qty
        milk_record.cost = new_cost
        db.session.commit()

        # Recalculate monthly totals
        recalc_monthly_totals()

        return redirect(url_for("home"))
    else:
        # Show edit form
        milk_id = request.args.get("id")
        milk_record = db.get_or_404(Milk, int(milk_id))
        return render_template("edit.html", milk=milk_record)

@app.route('/delete')
def delete_data():
    # DELETE RECORD
    milk_id = request.args.get('id')
    milk_to_delete = db.get_or_404(Milk, int(milk_id))
    db.session.delete(milk_to_delete)
    db.session.commit()

    # Recalculate totals after deletion
    recalc_monthly_totals()
    return redirect(url_for('home'))

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        # get and validate quantity
        milk_qty_raw = request.form.get("number", "0")
        try:
            milk_qty = float(milk_qty_raw)
        except (ValueError, TypeError):
            return redirect(url_for('add'))

        cost = milk_qty * 50.0
        
        # handle optional date input (HTML date returns YYYY-MM-DD)
        date_raw = request.form.get("date")
        if date_raw:
            try:
                parsed = dt.datetime.strptime(date_raw, "%Y-%m-%d")
                date_str = parsed.strftime("%d-%m-%Y")
                month_year_str = parsed.strftime("%m-%Y")
            except (ValueError, TypeError):
                now = dt.datetime.now()
                date_str = now.strftime("%d-%m-%Y")
                month_year_str = now.strftime("%m-%Y")
        else:
            now = dt.datetime.now()
            date_str = now.strftime("%d-%m-%Y")
            month_year_str = now.strftime("%m-%Y")

        with app.app_context():
            existing_entry = db.session.execute(
                db.select(Milk).filter_by(date=date_str)
            ).scalar_one_or_none()
            
            if existing_entry:
                flash(f'An entry for {date_str} already exists!', 'error')
                return redirect(url_for('add'))

            new_record = Milk(
                milk_qty=milk_qty,
                date=date_str,
                cost=cost,
                month_year=month_year_str
            )
            db.session.add(new_record)
            db.session.commit()

            # Recalculate monthly totals
            recalc_monthly_totals()
        return redirect(url_for('home'))
    else:
        return render_template("add.html")


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
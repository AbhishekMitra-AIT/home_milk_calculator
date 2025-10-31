from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Float
import datetime as dt

# how initialise the db object, define your model, 
# and create the table. 
class Base(DeclarativeBase):
  pass

db = SQLAlchemy(model_class=Base)

# create the app
app = Flask(__name__)

# configure the SQLite database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///milk-calculation.db"

# initialize the app with the extension
db.init_app(app)

class Milk(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(250), nullable=True)
    milk_qty: Mapped[float] = mapped_column(Float, nullable=True)
    cost: Mapped[float] = mapped_column(Float, nullable=True)
    total_cost: Mapped[float] = mapped_column(Float, nullable=True)

# Create table schema in the database. Requires application context.
with app.app_context():
    db.create_all()

# helper to recalculate running totals ordering by date
def recalc_totals():
    with app.app_context():
        result = db.session.execute(db.select(Milk).order_by(Milk.date, Milk.id))
        records = list(result.scalars())
        running_total = 0.0
        for r in records:
            running_total += (r.cost or 0.0)
            r.total_cost = running_total
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
    # milk.cost += milk.total_cost
    print(f"{milk.id} - {milk.date} - {milk.milk_qty} - {milk.cost} - {milk.total_cost}")
      

'''
Red underlines? Install the required packages first: 
Open the Terminal in PyCharm (bottom left). 

On Windows type:
python -m pip install -r requirements.txt

On MacOS type:
pip3 install -r requirements.txt

This will install the packages from requirements.txt for this project.
'''


@app.route('/')
def home():
    with app.app_context():
        result = db.session.execute(db.select(Milk).order_by(Milk.date, Milk.id))
        milk_data = list(result.scalars())  # Convert to list while session is open
        # compute total cost (sum of cost fields) to show beside "Add New Record"
        total_cost_all = sum((m.cost or 0.0) for m in milk_data)
    return render_template("index.html", milk=milk_data, total=total_cost_all)

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

        # Recalculate running total_cost for all records ordered by date
        recalc_totals()

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
    recalc_totals()
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
            except (ValueError, TypeError):
                date_str = dt.datetime.now().strftime("%d-%m-%Y")
        else:
            date_str = dt.datetime.now().strftime("%d-%m-%Y")

        with app.app_context():
            prev_total = db.session.query(db.func.sum(Milk.cost)).scalar() or 0.0
            total_cost = prev_total + cost

            new_record = Milk(
                milk_qty=milk_qty,
                date=date_str,
                cost=cost,
                total_cost=total_cost
            )
            db.session.add(new_record)
            db.session.commit()

        # Recalculate running totals ordered by date (so inserting past date is handled)
            recalc_totals()
        return redirect(url_for('home'))
    else:
        return render_template("add.html")


if __name__ == "__main__":
    # app.run(debug=True)
    app.run(host='0.0.0.0', port=5000)


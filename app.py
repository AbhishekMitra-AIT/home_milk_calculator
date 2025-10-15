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

# Read All Records
with app.app_context():
    result = db.session.execute(db.select(Milk).order_by(Milk.id))
    milk_data = list(result.scalars())  # Convert to list while session is open
if milk_data==[]:
    print("No milk data found in the database.")
else:
  for milk in milk_data: 
    print("Milk Data:")
    milk.cost += milk.total_cost
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
        result = db.session.execute(db.select(Milk).order_by(Milk.id))
        milk_data = list(result.scalars())  # Convert to list while session is open
    return render_template("index.html", milk=milk_data)

@app.route("/edit", methods=["GET", "POST"])
def edit():
    pass

@app.route('/delete')
def delete_data():
    # DELETE RECORD
    milk_id = request.args.get('id')
    milk_to_delete = db.get_or_404(Milk, int(milk_id))
    db.session.delete(milk_to_delete)
    db.session.commit()
    return redirect(url_for('home'))

@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        milk_qty = request.form["number"]
        cost = float(milk_qty)*50.0
        
        # CREATE new RECORD
        '''
        When creating new records, the primary key fields is optional. you can also write:
        new_book = Book(title="Harry Potter", author="J. K. Rowling", rating=9.3)
        the id field will be auto-generated. 
        '''
        with app.app_context():
            
            prev_total = db.session.query(db.func.sum(Milk.cost)).scalar() or 0.0
            total_cost = prev_total + cost

            new_record = Milk(
                milk_qty=milk_qty,
                date=dt.datetime.now().strftime("%d-%m-%Y"),
                cost=cost,
                total_cost=total_cost
            )
            db.session.add(new_record)
            db.session.commit()

        # return render_template("add.html", message="Book added successfully!")
        return redirect(url_for('home'))  # Redirect to home page after adding record
    else:
        return render_template("add.html")


if __name__ == "__main__":
    # app.run(debug=True)
    app.run(host='0.0.0.0', port=5000)


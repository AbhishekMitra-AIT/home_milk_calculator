# File: app_refactored.py
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from sqlalchemy import text, inspect
import datetime as dt
from collections import defaultdict

# Import from our new modules
from utils.config import Config
from models.models import db, User, Milk
from views.helpers import (
    login_required, get_month_year, recalc_monthly_totals,
    generate_verification_token, verify_token, send_verification_email
)

# Create app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
oauth = OAuth(app)

# Register OAuth
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

github = oauth.register(
    name='github',
    client_id=app.config['GHCLIENT_ID'],
    client_secret=app.config['GHCLIENT_SECRET'],
    access_token_url='https://github.com/login/oauth/access_token',
    access_token_params=None,
    authorize_url='https://github.com/login/oauth/authorize',
    authorize_params=None,
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'},
)

# Create tables
with app.app_context():
    try:
        db.create_all()
        print("✓ Database tables created/verified successfully")
        
        # Auto-migrate
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'user' in tables:
            columns = [col['name'] for col in inspector.get_columns('user')]
            
            if 'milk_price_per_litre' not in columns:
                db.session.execute(text('ALTER TABLE "user" ADD COLUMN milk_price_per_litre FLOAT DEFAULT 50.0'))
                print("✓ Added milk_price_per_litre column")
            if 'currency' not in columns:
                db.session.execute(text("ALTER TABLE \"user\" ADD COLUMN currency VARCHAR(10) DEFAULT 'INR'"))
                print("✓ Added currency column")
            if 'currency_symbol' not in columns:
                db.session.execute(text("ALTER TABLE \"user\" ADD COLUMN currency_symbol VARCHAR(5) DEFAULT '₹'"))
                print("✓ Added currency_symbol column")
            db.session.commit()
        
    except Exception as e:
        print(f"✗ Database initialization error: {e}")


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = db.session.query(User).filter_by(email=email).first()
        
        if user and user.password_hash and check_password_hash(user.password_hash, password):
            if not user.email_verified:
                flash('Please verify your email before logging in', 'error')
                return redirect(url_for('login'))
            session['user_id'] = user.id
            session['username'] = user.username or user.email
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
        
        existing_user = db.session.query(User).filter_by(email=email).first()
        if existing_user:
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        
        new_user = User(
            email=email,
            username=username,
            password_hash=generate_password_hash(password),
            email_verified=True  # Set to True for easy testing
        )
        db.session.add(new_user)
        db.session.commit()
        
        # Send verification email
        token = generate_verification_token(email, app.config['SECRET_KEY'])
        email_config = {
            'EMAIL_ADDRESS': app.config['EMAIL_ADDRESS'],
            'EMAIL_PASSWORD': app.config['EMAIL_PASSWORD'],
            'SMTP_SERVER': app.config['SMTP_SERVER'],
            'SMTP_PORT': app.config['SMTP_PORT']
        }
        
        if send_verification_email(email, token, email_config):
            flash('Registration successful! Please check your email to verify your account.', 'success')
        else:
            flash('Registration successful! You can now login.', 'success')
        
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/verify-email/<token>')
def verify_email(token):
    email = verify_token(token, app.config['SECRET_KEY'])
    if not email:
        flash('Invalid or expired verification link', 'error')
        return redirect(url_for('login'))
    
    user = db.session.query(User).filter_by(email=email).first()
    if user:
        user.email_verified = True
        db.session.commit()
        flash('Email verified successfully! You can now login.', 'success')
    else:
        flash('User not found', 'error')
    
    return redirect(url_for('login'))


@app.route('/login/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True).replace("http://", "https://")
    return google.authorize_redirect(redirect_uri)


@app.route('/callback/google')
def google_callback():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    
    email = user_info.get('email')
    name = user_info.get('name')
    oauth_id = user_info.get('sub')
    
    user = db.session.query(User).filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            username=name,
            oauth_provider='google',
            oauth_id=oauth_id,
            email_verified=True
        )
        db.session.add(user)
        db.session.commit()
    
    session['user_id'] = user.id
    session['username'] = user.username or user.email
    flash('Login successful!', 'success')
    return redirect(url_for('home'))


@app.route('/login/github')
def github_login():
    redirect_uri = url_for('github_callback', _external=True).replace("http://", "https://")
    return github.authorize_redirect(redirect_uri)


@app.route('/callback/github')
def github_callback():
    token = github.authorize_access_token()
    resp = github.get('user', token=token)
    user_info = resp.json()
    
    email = user_info.get('email')
    if not email:
        emails_resp = github.get('user/emails', token=token)
        emails = emails_resp.json()
        for email_obj in emails:
            if email_obj.get('primary'):
                email = email_obj.get('email')
                break
    
    name = user_info.get('name') or user_info.get('login')
    oauth_id = str(user_info.get('id'))
    
    user = db.session.query(User).filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            username=name,
            oauth_provider='github',
            oauth_id=oauth_id,
            email_verified=True
        )
        db.session.add(user)
        db.session.commit()
    
    session['user_id'] = user.id
    session['username'] = user.username or user.email
    flash('Login successful!', 'success')
    return redirect(url_for('home'))


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))


# ============================================================================
# MILK CRUD ROUTES
# ============================================================================

@app.route('/')
@login_required
def home():
    user_id = session.get('user_id')
    user = db.session.get(User, user_id)
    
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('logout'))
    
    result = db.session.execute(
        db.select(Milk)
        .filter_by(user_id=user_id)
        .order_by(Milk.date.desc(), Milk.id.desc())
    )
    milk_data = list(result.scalars())
    
    monthly_data = defaultdict(list)
    for record in milk_data:
        if record.month_year:
            monthly_data[record.month_year].append(record)
    
    monthly_totals = {}
    for month, records in monthly_data.items():
        monthly_totals[month] = sum((r.cost or 0.0) for r in records)
    
    sorted_months = sorted(monthly_data.keys(), key=lambda x: dt.datetime.strptime(x, "%m-%Y"), reverse=True)
    total_cost_all = sum((m.cost or 0.0) for m in milk_data)

    return render_template("index.html", 
                         monthly_data=monthly_data, 
                         sorted_months=sorted_months,
                         monthly_totals=monthly_totals,
                         total=total_cost_all,
                         username=session.get('username'),
                         currency_symbol=user.currency_symbol)


@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    user_id = session.get('user_id')
    
    if request.method == "POST":
        user = db.session.get(User, user_id)
        milk_price = user.milk_price_per_litre if user else 50.0
        
        milk_qty_raw = request.form.get("number", "0")
        try:
            milk_qty = float(milk_qty_raw)
        except (ValueError, TypeError):
            flash('Invalid milk quantity', 'error')
            return redirect(url_for('add'))

        cost = milk_qty * milk_price
        
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

        existing_entry = db.session.execute(
            db.select(Milk).filter_by(date=date_str, user_id=user_id)
        ).scalar_one_or_none()
        
        if existing_entry:
            flash(f'An entry for {date_str} already exists!', 'error')
            return redirect(url_for('add'))

        new_record = Milk(
            milk_qty=milk_qty,
            date=date_str,
            cost=cost,
            month_year=month_year_str,
            user_id=user_id
        )
        db.session.add(new_record)
        db.session.commit()
        recalc_monthly_totals(user_id)
        
        flash('Record added successfully!', 'success')
        return redirect(url_for('home'))
    
    return render_template("add.html")


@app.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    user_id = session.get('user_id')
    
    if request.method == "POST":
        milk_id = int(request.form.get("id"))
        milk_record = db.session.execute(
            db.select(Milk).filter_by(id=milk_id, user_id=user_id)
        ).scalar_one_or_none()
        
        if not milk_record:
            flash('Record not found or access denied', 'error')
            return redirect(url_for("home"))
        
        new_date_raw = request.form.get("date")
        if new_date_raw:
            try:
                parsed = dt.datetime.strptime(new_date_raw, "%Y-%m-%d")
                milk_record.date = parsed.strftime("%d-%m-%Y")
                milk_record.month_year = parsed.strftime("%m-%Y")
            except (ValueError, TypeError):
                pass

        try:
            new_qty = float(request.form.get("number", 0))
        except (ValueError, TypeError):
            return redirect(url_for("home"))

        user = db.session.get(User, user_id)
        milk_price = user.milk_price_per_litre if user else 50.0
        new_cost = new_qty * milk_price

        milk_record.milk_qty = new_qty
        milk_record.cost = new_cost
        db.session.commit()
        recalc_monthly_totals(user_id)

        flash('Record updated successfully!', 'success')
        return redirect(url_for("home"))
    else:
        milk_id = request.args.get("id")
        milk_record = db.session.execute(
            db.select(Milk).filter_by(id=int(milk_id), user_id=user_id)
        ).scalar_one_or_none()
        
        if not milk_record:
            flash('Record not found or access denied', 'error')
            return redirect(url_for("home"))
            
        return render_template("edit.html", milk=milk_record)


@app.route('/delete')
@login_required
def delete_data():
    user_id = session.get('user_id')
    
    milk_id = request.args.get('id')
    milk_to_delete = db.session.execute(
        db.select(Milk).filter_by(id=int(milk_id), user_id=user_id)
    ).scalar_one_or_none()
    
    if not milk_to_delete:
        flash('Record not found or access denied', 'error')
        return redirect(url_for('home'))
    
    db.session.delete(milk_to_delete)
    db.session.commit()
    recalc_monthly_totals(user_id)
    
    flash('Record deleted successfully!', 'success')
    return redirect(url_for('home'))


# ============================================================================
# SETTINGS ROUTE
# ============================================================================

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user_id = session.get('user_id')
    user = db.session.get(User, user_id)
    
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        milk_price = request.form.get('milk_price')
        currency = request.form.get('currency', 'INR')
        currency_symbol = request.form.get('currency_symbol', '₹')
        recalculate = request.form.get('recalculate') == 'yes'
        
        try:
            new_price = float(milk_price)
            if new_price <= 0:
                flash('Milk price must be greater than 0', 'error')
                return redirect(url_for('settings'))
            
            old_price = user.milk_price_per_litre
            
            user.milk_price_per_litre = new_price
            user.currency = currency
            user.currency_symbol = currency_symbol
            db.session.commit()
            
            if recalculate and old_price != new_price:
                milk_records = db.session.execute(
                    db.select(Milk).filter_by(user_id=user_id)
                ).scalars().all()
                
                for record in milk_records:
                    record.cost = record.milk_qty * new_price
                
                db.session.commit()
                flash(f'Settings updated! Recalculated {len(milk_records)} records with new price.', 'success')
            else:
                flash('Settings updated successfully!', 'success')
            
            return redirect(url_for('home'))
            
        except (ValueError, TypeError):
            flash('Invalid milk price', 'error')
            return redirect(url_for('settings'))
    
    currencies = [
        {'code': 'INR', 'symbol': '₹', 'name': 'Indian Rupee'},
        {'code': 'USD', 'symbol': '$', 'name': 'US Dollar'},
        {'code': 'EUR', 'symbol': '€', 'name': 'Euro'},
        {'code': 'GBP', 'symbol': '£', 'name': 'British Pound'},
        {'code': 'JPY', 'symbol': '¥', 'name': 'Japanese Yen'},
        {'code': 'AUD', 'symbol': 'A$', 'name': 'Australian Dollar'},
        {'code': 'CAD', 'symbol': 'C$', 'name': 'Canadian Dollar'},
        {'code': 'CHF', 'symbol': 'Fr', 'name': 'Swiss Franc'},
        {'code': 'CNY', 'symbol': '¥', 'name': 'Chinese Yuan'},
        {'code': 'AED', 'symbol': 'د.إ', 'name': 'UAE Dirham'},
    ]
    
    return render_template('settings.html', user=user, currencies=currencies)


if __name__ == "__main__":
    print("✓ Using refactored MVT architecture")
    print("✓ Visit: http://localhost:5000/login\n")
    app.run(host='0.0.0.0', port=5000, debug=True)
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Float, Boolean, DateTime, ForeignKey
import datetime as dt, os, secrets
from collections import defaultdict
import smtplib
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from functools import wraps
from itsdangerous import URLSafeTimedSerializer
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_cors import CORS
from utils.jwt_auth import (
    generate_access_token,
    generate_refresh_token,
    decode_token,
    token_required,
    get_current_user
)

# Load environment variables
load_dotenv()

# Database setup
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)

# Enable CORS for API endpoints
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Secret Key for sessions and tokens
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# Database Configuration - PostgreSQL for production, SQLite for local
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    # Railway/Production: Use PostgreSQL
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
    print("✓ Using PostgreSQL database (Production)")
else:
    # Local Development: Use SQLite
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///milk-calculation.db"
    print("✓ Using SQLite database (Development)")

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

# Email Configuration
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

# OAuth Configuration
oauth = OAuth(app)

# Google OAuth
google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# GitHub OAuth
github = oauth.register(
    name='github',
    client_id=os.environ.get("GHCLIENT_ID"),
    client_secret=os.environ.get("GHCLIENT_SECRET"),
    access_token_url='https://github.com/login/oauth/access_token',
    access_token_params=None,
    authorize_url='https://github.com/login/oauth/authorize',
    authorize_params=None,
    api_base_url='https://api.github.com/',
    client_kwargs={'scope': 'user:email'},
)

# Initialize the app with the extension
db.init_app(app)

# Models
class User(db.Model):
    __tablename__ = 'user'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(80), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=True)
    oauth_provider: Mapped[str] = mapped_column(String(20), nullable=True)
    oauth_id: Mapped[str] = mapped_column(String(200), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    
    # User settings
    milk_price_per_litre: Mapped[float] = mapped_column(Float, default=50.0)
    currency: Mapped[str] = mapped_column(String(10), default='INR')
    currency_symbol: Mapped[str] = mapped_column(String(5), default='₹')
    
    # Relationship to Milk records
    milk_records = relationship('Milk', back_populates='user', cascade='all, delete-orphan')


class Milk(db.Model):
    __tablename__ = 'milk'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(250), nullable=True, index=True)
    milk_qty: Mapped[float] = mapped_column(Float, nullable=True)
    cost: Mapped[float] = mapped_column(Float, nullable=True)
    month_year: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    
    # Foreign key to link to User
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('user.id'), nullable=False, index=True)
    
    # Relationship back to User
    user = relationship('User', back_populates='milk_records')


# Create table schema in the database
with app.app_context():
    try:
        db.create_all()
        print("✓ Database tables created/verified successfully")
        
        # Auto-migrate: Add settings columns if they don't exist
        from sqlalchemy import text, inspect
        inspector = inspect(db.engine)
        
        # Only for PostgreSQL (check if user table exists)
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


# Email verification token generator
def generate_verification_token(email):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='email-verification')


def verify_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='email-verification', max_age=expiration)
        return email
    except:
        return None


def send_verification_email(email, token):
    """Send verification email to user"""
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        print("⚠️ Email credentials not configured. Verification email not sent.")
        return False
    
    verification_url = url_for('verify_email', token=token, _external=True)
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Verify Your Email - Milk Calculator'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = email
    
    html = f"""
    <html>
      <body>
        <h2>Welcome to Milk Calculator Dashboard!</h2>
        <p>Please click the link below to verify your email address:</p>
        <p><a href="{verification_url}">Verify Email</a></p>
        <p>Or copy and paste this URL into your browser:</p>
        <p>{verification_url}</p>
        <p>This link will expire in 1 hour.</p>
        <br>
        <p>If you didn't create an account, please ignore this email.</p>
      </body>
    </html>
    """
    
    part = MIMEText(html, 'html')
    msg.attach(part)
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# Helper to extract month-year from date string
def get_month_year(date_str):
    """Extract MM-YYYY from DD-MM-YYYY date string"""
    if date_str:
        parts = date_str.split('-')
        if len(parts) == 3:
            return f"{parts[1]}-{parts[2]}"
    return None


# Helper to recalculate monthly totals (user-specific)
def recalc_monthly_totals(user_id):
    with app.app_context():
        result = db.session.execute(
            db.select(Milk)
            .filter_by(user_id=user_id)
            .order_by(Milk.date, Milk.id)
        )
        records = list(result.scalars())
        
        monthly_groups = defaultdict(list)
        for r in records:
            if r.month_year:
                monthly_groups[r.month_year].append(r)
        
        db.session.commit()


# Authentication Routes
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
            email_verified=False
        )
        db.session.add(new_user)
        db.session.commit()
        
        # Send verification email
        token = generate_verification_token(email)
        if send_verification_email(email, token):
            flash('Registration successful! Please check your email to verify your account.', 'success')
        else:
            flash('Registration successful! However, verification email could not be sent.', 'warning')
        
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/verify-email/<token>')
def verify_email(token):
    email = verify_token(token)
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


# Protected Routes - User-specific
@app.route('/')
@login_required
def home():
    user_id = session.get('user_id')
    
    with app.app_context():
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

        with app.app_context():
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
    else:
        return render_template("add.html")


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


# ============================================================================
# JWT API AUTHENTICATION ROUTES (Add to app.py)
# ============================================================================

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """JWT-based registration"""
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Email and password required'}), 400
    
    email = data.get('email')
    username = data.get('username', email.split('@')[0])
    password = data.get('password')
    
    # Check if user exists
    existing_user = db.session.query(User).filter_by(email=email).first()
    if existing_user:
        return jsonify({'message': 'Email already registered'}), 409
    
    # Create new user
    new_user = User(
        email=email,
        username=username,
        password_hash=generate_password_hash(password),
        email_verified=True
    )
    db.session.add(new_user)
    db.session.commit()
    
    # Generate tokens
    access_token = generate_access_token(new_user.id, new_user.email)
    refresh_token = generate_refresh_token(new_user.id, new_user.email)
    
    # Store refresh token
    new_user.refresh_token = refresh_token
    db.session.commit()
    
    return jsonify({
        'message': 'Registration successful',
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': new_user.id,
            'email': new_user.email,
            'username': new_user.username
        }
    }), 201


@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """JWT-based login"""
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Email and password required'}), 400
    
    email = data.get('email')
    password = data.get('password')
    
    # Find user
    user = db.session.query(User).filter_by(email=email).first()
    
    if not user or not user.password_hash:
        return jsonify({'message': 'Invalid credentials'}), 401
    
    # Verify password
    if not check_password_hash(user.password_hash, password):
        return jsonify({'message': 'Invalid credentials'}), 401
    
    if not user.email_verified:
        return jsonify({'message': 'Please verify your email'}), 403
    
    # Generate tokens
    access_token = generate_access_token(user.id, user.email)
    refresh_token = generate_refresh_token(user.id, user.email)
    
    # Store refresh token
    user.refresh_token = refresh_token
    db.session.commit()
    
    return jsonify({
        'message': 'Login successful',
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'currency_symbol': user.currency_symbol
        }
    }), 200


@app.route('/api/auth/refresh', methods=['POST'])
def api_refresh_token():
    """Refresh access token"""
    data = request.get_json()
    
    if not data or not data.get('refresh_token'):
        return jsonify({'message': 'Refresh token required'}), 400
    
    refresh_token = data.get('refresh_token')
    
    # Decode refresh token
    payload = decode_token(refresh_token)
    
    if not payload or payload.get('type') != 'refresh':
        return jsonify({'message': 'Invalid refresh token'}), 401
    
    # Get user
    user = db.session.get(User, payload['user_id'])
    
    if not user or user.refresh_token != refresh_token:
        return jsonify({'message': 'Invalid refresh token'}), 401
    
    # Generate new access token
    new_access_token = generate_access_token(user.id, user.email)
    
    return jsonify({
        'access_token': new_access_token
    }), 200


@app.route('/api/auth/logout', methods=['POST'])
@token_required
def api_logout():
    """Logout - invalidate refresh token"""
    user = get_current_user()
    
    # Clear refresh token
    user.refresh_token = None
    db.session.commit()
    
    return jsonify({'message': 'Logout successful'}), 200


@app.route('/api/auth/me', methods=['GET'])
@token_required
def api_get_current_user():
    """Get current user info"""
    user = get_current_user()
    
    return jsonify({
        'user': {
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'currency': user.currency,
            'currency_symbol': user.currency_symbol,
            'milk_price_per_litre': user.milk_price_per_litre
        }
    }), 200


# ============================================================================
# JWT-PROTECTED MILK CRUD API ROUTES (Add to app.py)
# ============================================================================

@app.route('/api/milk/records', methods=['GET'])
@token_required
def api_get_milk_records():
    """Get all milk records"""
    user = get_current_user()
    
    result = db.session.execute(
        db.select(Milk)
        .filter_by(user_id=user.id)
        .order_by(Milk.date.desc())
    )
    milk_data = list(result.scalars())
    
    # Group by month
    monthly_data = defaultdict(list)
    for record in milk_data:
        if record.month_year:
            monthly_data[record.month_year].append({
                'id': record.id,
                'date': record.date,
                'milk_qty': record.milk_qty,
                'cost': record.cost
            })
    
    # Calculate monthly totals
    monthly_totals = {}
    for month, records in monthly_data.items():
        monthly_totals[month] = sum(r['cost'] for r in records)
    
    return jsonify({
        'monthly_data': dict(monthly_data),
        'monthly_totals': monthly_totals,
        'total_records': len(milk_data)
    }), 200


@app.route('/api/milk/records', methods=['POST'])
@token_required
def api_add_milk_record():
    """Add new milk record"""
    user = get_current_user()
    data = request.get_json()
    
    if not data or not data.get('milk_qty'):
        return jsonify({'message': 'Milk quantity required'}), 400
    
    try:
        milk_qty = float(data.get('milk_qty'))
    except (ValueError, TypeError):
        return jsonify({'message': 'Invalid milk quantity'}), 400
    
    cost = milk_qty * user.milk_price_per_litre
    
    # Handle date
    date_raw = data.get('date')
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
    
    # Check for duplicate
    existing_entry = db.session.execute(
        db.select(Milk).filter_by(date=date_str, user_id=user.id)
    ).scalar_one_or_none()
    
    if existing_entry:
        return jsonify({'message': f'Entry for {date_str} already exists'}), 409
    
    # Create record
    new_record = Milk(
        milk_qty=milk_qty,
        date=date_str,
        cost=cost,
        month_year=month_year_str,
        user_id=user.id
    )
    db.session.add(new_record)
    db.session.commit()
    
    return jsonify({
        'message': 'Record added successfully',
        'record': {
            'id': new_record.id,
            'date': new_record.date,
            'milk_qty': new_record.milk_qty,
            'cost': new_record.cost
        }
    }), 201


@app.route('/api/milk/records/<int:record_id>', methods=['PUT'])
@token_required
def api_update_milk_record(record_id):
    """Update milk record"""
    user = get_current_user()
    
    milk_record = db.session.execute(
        db.select(Milk).filter_by(id=record_id, user_id=user.id)
    ).scalar_one_or_none()
    
    if not milk_record:
        return jsonify({'message': 'Record not found'}), 404
    
    data = request.get_json()
    
    # Update quantity
    if 'milk_qty' in data:
        try:
            new_qty = float(data['milk_qty'])
            milk_record.milk_qty = new_qty
            milk_record.cost = new_qty * user.milk_price_per_litre
        except (ValueError, TypeError):
            return jsonify({'message': 'Invalid milk quantity'}), 400
    
    # Update date
    if 'date' in data:
        try:
            parsed = dt.datetime.strptime(data['date'], "%Y-%m-%d")
            milk_record.date = parsed.strftime("%d-%m-%Y")
            milk_record.month_year = parsed.strftime("%m-%Y")
        except (ValueError, TypeError):
            pass
    
    db.session.commit()
    
    return jsonify({
        'message': 'Record updated successfully',
        'record': {
            'id': milk_record.id,
            'date': milk_record.date,
            'milk_qty': milk_record.milk_qty,
            'cost': milk_record.cost
        }
    }), 200


@app.route('/api/milk/records/<int:record_id>', methods=['DELETE'])
@token_required
def api_delete_milk_record(record_id):
    """Delete milk record"""
    user = get_current_user()
    
    milk_to_delete = db.session.execute(
        db.select(Milk).filter_by(id=record_id, user_id=user.id)
    ).scalar_one_or_none()
    
    if not milk_to_delete:
        return jsonify({'message': 'Record not found'}), 404
    
    db.session.delete(milk_to_delete)
    db.session.commit()
    
    return jsonify({'message': 'Record deleted successfully'}), 200


@app.route('/api/settings', methods=['GET', 'PUT'])
@token_required
def api_user_settings():
    """Get or update user settings"""
    user = get_current_user()
    
    if request.method == 'GET':
        return jsonify({
            'settings': {
                'milk_price_per_litre': user.milk_price_per_litre,
                'currency': user.currency,
                'currency_symbol': user.currency_symbol
            }
        }), 200
    
    # PUT - Update settings
    data = request.get_json()
    
    if 'milk_price_per_litre' in data:
        try:
            new_price = float(data['milk_price_per_litre'])
            if new_price <= 0:
                return jsonify({'message': 'Price must be greater than 0'}), 400
            user.milk_price_per_litre = new_price
        except (ValueError, TypeError):
            return jsonify({'message': 'Invalid price'}), 400
    
    if 'currency' in data:
        user.currency = data['currency']
    
    if 'currency_symbol' in data:
        user.currency_symbol = data['currency_symbol']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Settings updated successfully',
        'settings': {
            'milk_price_per_litre': user.milk_price_per_litre,
            'currency': user.currency,
            'currency_symbol': user.currency_symbol
        }
    }), 200


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
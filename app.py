from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Float, Boolean, DateTime, ForeignKey
import datetime as dt, os, secrets
from collections import defaultdict
import requests, os, secrets, smtplib
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from authlib.integrations.flask_client import OAuth
from functools import wraps
from itsdangerous import URLSafeTimedSerializer
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


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


# initialize the app with the extension
db.init_app(app)

# Models
class User(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(80), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=True)
    oauth_provider: Mapped[str] = mapped_column(String(20), nullable=True)  # 'google', 'github', or None
    oauth_id: Mapped[str] = mapped_column(String(200), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    
    # Relationship to Milk records
    milk_records = relationship('Milk', back_populates='user', cascade='all, delete-orphan')
 

class Milk(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(250), nullable=True)
    milk_qty: Mapped[float] = mapped_column(Float, nullable=True)
    cost: Mapped[float] = mapped_column(Float, nullable=True)
    month_year: Mapped[str] = mapped_column(String(50), nullable=True)  # Store "MM-YYYY"
    
    # Foreign key to link to User
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('user.id'), nullable=False)
    
    # Relationship back to User
    user = relationship('User', back_populates='milk_records')

# Create table schema in the database. Requires application context.
with app.app_context():
    db.create_all()

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


# helper to extract month-year from date string
def get_month_year(date_str):
    """Extract MM-YYYY from DD-MM-YYYY date string"""
    if date_str:
        parts = date_str.split('-')
        if len(parts) == 3:
            return f"{parts[1]}-{parts[2]}"  # MM-YYYY
    return None

# helper to recalculate monthly totals (now user-specific)
def recalc_monthly_totals(user_id):
    with app.app_context():
        result = db.session.execute(
            db.select(Milk)
            .filter_by(user_id=user_id)
            .order_by(Milk.date, Milk.id)
        )
        records = list(result.scalars())
        
        # Group by month_year and calculate totals per month
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
            flash('Registration successful! However, verification email could not be sent. Please contact support.', 'warning')
        
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
            email_verified=True  # OAuth emails are pre-verified
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
        # GitHub might not return email, fetch from emails endpoint
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


# Protected Routes - Now user-specific
@app.route('/')
@login_required
def home():
    user_id = session.get('user_id')
    
    with app.app_context():
        # Filter milk data by current user
        result = db.session.execute(
            db.select(Milk)
            .filter_by(user_id=user_id)
            .order_by(Milk.date.desc(), Milk.id.desc())
        )
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
                         total=total_cost_all,
                         username=session.get('username'))

@app.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    user_id = session.get('user_id')
    
    if request.method == "POST":
        # Update record
        milk_id = int(request.form.get("id"))
        milk_record = db.session.execute(
            db.select(Milk).filter_by(id=milk_id, user_id=user_id)
        ).scalar_one_or_none()
        
        if not milk_record:
            flash('Record not found or access denied', 'error')
            return redirect(url_for("home"))
        
        # Handle new date (HTML date input returns YYYY-MM-DD)
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

        new_cost = new_qty * 50.0

        milk_record.milk_qty = new_qty
        milk_record.cost = new_cost
        db.session.commit()

        # Recalculate monthly totals
        recalc_monthly_totals(user_id)

        flash('Record updated successfully!', 'success')
        return redirect(url_for("home"))
    else:
        # Show edit form
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
    
    # DELETE RECORD - only if it belongs to current user
    milk_id = request.args.get('id')
    milk_to_delete = db.session.execute(
        db.select(Milk).filter_by(id=int(milk_id), user_id=user_id)
    ).scalar_one_or_none()
    
    if not milk_to_delete:
        flash('Record not found or access denied', 'error')
        return redirect(url_for('home'))
    
    db.session.delete(milk_to_delete)
    db.session.commit()

    # Recalculate totals after deletion
    recalc_monthly_totals(user_id)
    
    flash('Record deleted successfully!', 'success')
    return redirect(url_for('home'))

@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    user_id = session.get('user_id')
    
    if request.method == "POST":
        # get and validate quantity
        milk_qty_raw = request.form.get("number", "0")
        try:
            milk_qty = float(milk_qty_raw)
        except (ValueError, TypeError):
            flash('Invalid milk quantity', 'error')
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
            # Check if entry exists for this user and date
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
                user_id=user_id  # Link to current user
            )
            db.session.add(new_record)
            db.session.commit()

            # Recalculate monthly totals
            recalc_monthly_totals(user_id)
        
        flash('Record added successfully!', 'success')
        return redirect(url_for('home'))
    else:
        return render_template("add.html")


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
# File: helpers.py
from functools import wraps
from flask import session, redirect, url_for, flash
from collections import defaultdict
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from itsdangerous import URLSafeTimedSerializer
from models.models import db, Milk


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def get_month_year(date_str):
    """Extract MM-YYYY from DD-MM-YYYY"""
    if date_str:
        parts = date_str.split('-')
        if len(parts) == 3:
            return f"{parts[1]}-{parts[2]}"
    return None


def recalc_monthly_totals(user_id):
    """Recalculate monthly totals"""
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


def generate_verification_token(email, secret_key):
    """Generate email verification token"""
    serializer = URLSafeTimedSerializer(secret_key)
    return serializer.dumps(email, salt='email-verification')


def verify_token(token, secret_key, expiration=3600):
    """Verify email verification token"""
    serializer = URLSafeTimedSerializer(secret_key)
    try:
        email = serializer.loads(token, salt='email-verification', max_age=expiration)
        return email
    except:
        return None


def send_verification_email(email, token, config):
    """Send verification email"""
    if not config['EMAIL_ADDRESS'] or not config['EMAIL_PASSWORD']:
        print("⚠️ Email credentials not configured")
        return False
    
    from flask import url_for
    verification_url = url_for('verify_email', token=token, _external=True)
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Verify Your Email - Milk Calculator'
    msg['From'] = config['EMAIL_ADDRESS']
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
        with smtplib.SMTP(config['SMTP_SERVER'], config['SMTP_PORT']) as server:
            server.starttls()
            server.login(config['EMAIL_ADDRESS'], config['EMAIL_PASSWORD'])
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
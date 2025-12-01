import jwt
import datetime as dt
from functools import wraps
from flask import request, jsonify, current_app


def generate_access_token(user_id, email):
    """Generate JWT access token (24 hours)"""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': dt.datetime.now() + dt.timedelta(hours=24),
        'iat': dt.datetime.now(),
        'type': 'access'
    }
    
    token = jwt.encode(
        payload,
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )
    
    return token


def generate_refresh_token(user_id, email):
    """Generate JWT refresh token (30 days)"""
    payload = {
        'user_id': user_id,
        'email': email,
        'exp': dt.datetime.utcnow() + dt.timedelta(days=30),
        'iat': dt.datetime.utcnow(),
        'type': 'refresh'
    }
    
    token = jwt.encode(
        payload,
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )
    
    return token


def decode_token(token):
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(
            token,
            current_app.config['SECRET_KEY'],
            algorithms=['HS256']
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None  # Token expired
    except jwt.InvalidTokenError:
        return None  # Invalid token


def token_required(f):
    """Decorator to protect routes with JWT"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check for token in Authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]  # Bearer <token>
            except IndexError:
                return jsonify({'message': 'Token format invalid. Use: Bearer <token>'}), 401
        
        # Check for token in cookies (for browser-based apps)
        if not token and 'access_token' in request.cookies:
            token = request.cookies.get('access_token')
        
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        # Decode token
        payload = decode_token(token)
        
        if not payload:
            return jsonify({'message': 'Token is invalid or expired'}), 401
        
        # Verify token type
        if payload.get('type') != 'access':
            return jsonify({'message': 'Invalid token type'}), 401
        
        # Import User model here to avoid circular imports
        from models.models import User, db
        
        # Get user from database
        user = db.session.get(User, payload['user_id'])
        
        if not user:
            return jsonify({'message': 'User not found'}), 401
        
        # Add user to request context
        request.current_user = user
        
        return f(*args, **kwargs)
    
    return decorated


def get_current_user():
    """Get current authenticated user from request"""
    return getattr(request, 'current_user', None)
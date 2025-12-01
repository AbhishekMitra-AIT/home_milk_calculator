# JWT Implementation Checklist - Your Project Structure

## File Structure After Implementation

```
home_milk_calculator/
├── app.py                        # ✏️ MODIFY: Add API routes
├── add_refresh_token_column.py   # ➕ NEW: Migration script
├── models/
│   ├── __init__.py
│   └── models.py                 # ✏️ MODIFY: Add refresh_token column
├── utils/
│   ├── __init__.py
│   ├── config.py
│   └── jwt_auth.py               # ➕ NEW: JWT utilities
├── templates/                     # ✅ NO CHANGES
├── requirements.txt              # ✏️ MODIFY: Add JWT dependencies
└── ...
```

## Step-by-Step Implementation

### Step 1: Install Dependencies

```bash
pip install PyJWT==2.8.0 flask-cors==4.0.0
```

Add to `requirements.txt`:
```txt
PyJWT==2.8.0
flask-cors==4.0.0
```

### Step 2: Create `utils/jwt_auth.py`

```bash
# Create the file
touch utils/jwt_auth.py
```

Copy the entire `utils/jwt_auth.py` content from the artifact above.

**Key points:**
- ✅ Imports from `models.models` (not just `models`)
- ✅ Uses `current_app.config['SECRET_KEY']`
- ✅ Includes `@token_required` decorator
- ✅ Includes `get_current_user()` helper

### Step 3: Update `models/models.py`

Add this column to your `User` class:

```python
# In models/models.py, add to User class:

class User(db.Model):
    # ... existing columns ...
    
    # ADD THIS LINE:
    refresh_token: Mapped[str] = mapped_column(String(500), nullable=True)
```

**Location:** After `currency_symbol` column, before `milk_records` relationship.

### Step 4: Create Migration Script

Create `add_refresh_token_column.py` in **root directory**:

```python
from app import app, db
from sqlalchemy import text, inspect

def add_refresh_token_column():
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('user')]
            
            if 'refresh_token' not in columns:
                print("Adding refresh_token column...")
                db.session.execute(text('ALTER TABLE "user" ADD COLUMN refresh_token VARCHAR(500)'))
                db.session.commit()
                print("✓ refresh_token column added")
            else:
                print("✓ refresh_token column already exists")
        except Exception as e:
            print(f"✗ Error: {e}")
            db.session.rollback()

if __name__ == "__main__":
    add_refresh_token_column()
```

Run it:
```bash
python add_refresh_token_column.py
```

### Step 5: Update `app.py`

#### A. Add imports (at the top, after existing imports):

```python
from flask_cors import CORS
from utils.jwt_auth import (
    generate_access_token,
    generate_refresh_token,
    decode_token,
    token_required,
    get_current_user
)
```

#### B. Enable CORS (after `app = Flask(__name__)`):

```python
# After: app = Flask(__name__)
# Add:
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
```

#### C. Add API routes (before `if __name__ == "__main__":`):

Copy all the API routes from the artifact:
- `/api/auth/register`
- `/api/auth/login`
- `/api/auth/refresh`
- `/api/auth/logout`
- `/api/auth/me`
- `/api/milk/records` (GET, POST)
- `/api/milk/records/<id>` (PUT, DELETE)
- `/api/settings` (GET, PUT)

### Step 6: Test the Implementation

#### Test 1: Server Starts

```bash
python app.py
```

You should see:
```
✓ Using SQLite database (Development)
✓ Database tables created/verified successfully
 * Running on http://127.0.0.1:5000
```

#### Test 2: Register User

```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "password123"
  }'
```

Expected response:
```json
{
  "message": "Registration successful",
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": {
    "id": 1,
    "email": "test@example.com",
    "username": "testuser"
  }
}
```

#### Test 3: Login

```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'
```

#### Test 4: Protected Route (Get User Info)

```bash
# Save token from previous response
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

curl -X GET http://localhost:5000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

#### Test 5: Add Milk Record

```bash
curl -X POST http://localhost:5000/api/milk/records \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "milk_qty": 2.5,
    "date": "2025-01-15"
  }'
```

### Step 7: Verify Database Changes

```bash
# Check if refresh_token column exists
python -c "from app import app, db; from sqlalchemy import inspect; app.app_context().push(); inspector = inspect(db.engine); print([col['name'] for col in inspector.get_columns('user')])"
```

Should show: `['id', 'email', 'username', 'password_hash', ..., 'refresh_token']`

## Troubleshooting

### Issue 1: ImportError: cannot import name 'generate_access_token'

**Cause:** `utils/jwt_auth.py` not created or in wrong location

**Fix:**
```bash
# Verify file exists
ls -la utils/jwt_auth.py

# If missing, create it
touch utils/jwt_auth.py
# Then copy content from artifact
```

### Issue 2: circular import error

**Cause:** Importing models at module level in `jwt_auth.py`

**Fix:** Models are imported inside the `@token_required` decorator function (already done in the code)

### Issue 3: Column refresh_token doesn't exist

**Cause:** Migration not run

**Fix:**
```bash
python add_refresh_token_column.py
```

### Issue 4: CORS error in browser

**Cause:** CORS not enabled

**Fix:** Add this after `app = Flask(__name__)`:
```python
from flask_cors import CORS
CORS(app, resources={r"/api/*": {"origins": "*"}})
```

### Issue 5: 401 Unauthorized even with valid token

**Cause:** User model not found or token expired

**Fix:**
- Check token expiry (24 hours for access token)
- Use refresh token to get new access token
- Verify user exists in database

## Testing Checklist

- [x] Server starts without errors
- [x] Can register new user via API
- [x] Can login via API
- [x] Receive access_token and refresh_token
- [ ] Can access protected route with token
- [ ] Can add milk record via API
- [ ] Can get all records via API
- [ ] Can update record via API
- [ ] Can delete record via API
- [ ] Can update settings via API
- [ ] Can refresh access token
- [ ] Can logout via API
- [x] Old web interface still works (`/login`, `/register`, etc.)

## API Endpoints Summary

### Public Endpoints (No Auth Required)
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get tokens
- `POST /api/auth/refresh` - Refresh access token

### Protected Endpoints (Auth Required)
- `POST /api/auth/logout` - Logout
- `GET /api/auth/me` - Get current user
- `GET /api/milk/records` - Get all milk records
- `POST /api/milk/records` - Add milk record
- `PUT /api/milk/records/<id>` - Update record
- `DELETE /api/milk/records/<id>` - Delete record
- `GET /api/settings` - Get user settings
- `PUT /api/settings` - Update settings

## Deployment to Railway

Your existing deployment process doesn't change:

```bash
git add .
git commit -m "Add JWT authentication API"
git push origin main
```

Railway will automatically:
1. Install new dependencies (PyJWT, flask-cors)
2. Run migration on first startup (via auto-migrate code)
3. Deploy API endpoints alongside web interface

## Both Systems Work Together

- **Web Interface:** `/login`, `/register`, `/home` - Uses sessions
- **API:** `/api/*` - Uses JWT tokens

They're **completely independent** and can coexist! 🎉

## Next Steps

After successful implementation:

1. **Test API with Postman** - Import collection from testing guide
2. **Build frontend** - React/Vue/Angular consuming API
3. **Create mobile app** - Flutter/React Native using API
4. **Add API documentation** - Swagger/OpenAPI
5. **Add rate limiting** - flask-limiter for API security

Your Flask app now has **modern REST API** capabilities! 🚀
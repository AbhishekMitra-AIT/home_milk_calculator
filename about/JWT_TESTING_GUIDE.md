# JWT Authentication Testing Guide

## Installation

```bash
pip install PyJWT==2.8.0 flask-cors==4.0.0
```

## API Endpoints

### Authentication Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/auth/register` | Register new user | No |
| POST | `/api/auth/login` | Login and get tokens | No |
| POST | `/api/auth/refresh` | Refresh access token | No |
| POST | `/api/auth/logout` | Logout (invalidate refresh token) | Yes |
| GET | `/api/auth/me` | Get current user info | Yes |

### Milk Records Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/milk/records` | Get all records | Yes |
| POST | `/api/milk/records` | Add new record | Yes |
| PUT | `/api/milk/records/<id>` | Update record | Yes |
| DELETE | `/api/milk/records/<id>` | Delete record | Yes |

### Settings Endpoint

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/settings` | Get user settings | Yes |
| PUT | `/api/settings` | Update settings | Yes |

## Testing with cURL

### 1. Register New User

```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "password123"
  }'
```

**Response:**
```json
{
  "message": "Registration successful",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "email": "test@example.com",
    "username": "testuser"
  }
}
```

### 2. Login

```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'
```

**Response:**
```json
{
  "message": "Login successful",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "email": "test@example.com",
    "username": "testuser",
    "currency_symbol": "₹"
  }
}
```

### 3. Get Current User (Protected Route)

```bash
# Save token from login response
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

curl -X GET http://localhost:5000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "user": {
    "id": 1,
    "email": "test@example.com",
    "username": "testuser",
    "currency": "INR",
    "currency_symbol": "₹",
    "milk_price_per_litre": 50.0
  }
}
```

### 4. Add Milk Record

```bash
curl -X POST http://localhost:5000/api/milk/records \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "milk_qty": 2.5,
    "date": "2025-01-15"
  }'
```

**Response:**
```json
{
  "message": "Record added successfully",
  "record": {
    "id": 1,
    "date": "15-01-2025",
    "milk_qty": 2.5,
    "cost": 125.0
  }
}
```

### 5. Get All Records

```bash
curl -X GET http://localhost:5000/api/milk/records \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "monthly_data": {
    "01-2025": [
      {
        "id": 1,
        "date": "15-01-2025",
        "milk_qty": 2.5,
        "cost": 125.0
      }
    ]
  },
  "monthly_totals": {
    "01-2025": 125.0
  },
  "total_records": 1
}
```

### 6. Update Record

```bash
curl -X PUT http://localhost:5000/api/milk/records/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "milk_qty": 3.0
  }'
```

### 7. Delete Record

```bash
curl -X DELETE http://localhost:5000/api/milk/records/1 \
  -H "Authorization: Bearer $TOKEN"
```

### 8. Update Settings

```bash
curl -X PUT http://localhost:5000/api/settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "milk_price_per_litre": 60.0,
    "currency": "USD",
    "currency_symbol": "$"
  }'
```

### 9. Refresh Access Token

```bash
REFRESH_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

curl -X POST http://localhost:5000/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "'$REFRESH_TOKEN'"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### 10. Logout

```bash
curl -X POST http://localhost:5000/api/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

## Testing with Python

```python
import requests
import json

BASE_URL = "http://localhost:5000/api"

# 1. Register
response = requests.post(f"{BASE_URL}/auth/register", json={
    "email": "test@example.com",
    "username": "testuser",
    "password": "password123"
})
print("Register:", response.json())

# 2. Login
response = requests.post(f"{BASE_URL}/auth/login", json={
    "email": "test@example.com",
    "password": "password123"
})
data = response.json()
access_token = data['access_token']
refresh_token = data['refresh_token']
print("Login:", data)

# 3. Get current user
headers = {"Authorization": f"Bearer {access_token}"}
response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
print("Current User:", response.json())

# 4. Add milk record
response = requests.post(
    f"{BASE_URL}/milk/records",
    headers=headers,
    json={
        "milk_qty": 2.5,
        "date": "2025-01-15"
    }
)
print("Add Record:", response.json())

# 5. Get all records
response = requests.get(f"{BASE_URL}/milk/records", headers=headers)
print("All Records:", response.json())

# 6. Update settings
response = requests.put(
    f"{BASE_URL}/settings",
    headers=headers,
    json={
        "milk_price_per_litre": 60.0,
        "currency": "USD",
        "currency_symbol": "$"
    }
)
print("Update Settings:", response.json())

# 7. Refresh token
response = requests.post(f"{BASE_URL}/auth/refresh", json={
    "refresh_token": refresh_token
})
new_access_token = response.json()['access_token']
print("New Access Token:", new_access_token)

# 8. Logout
headers = {"Authorization": f"Bearer {access_token}"}
response = requests.post(f"{BASE_URL}/auth/logout", headers=headers)
print("Logout:", response.json())
```

## Testing with Postman

### Setup

1. Create new Collection: "Milk Calculator API"
2. Add Environment with variables:
   - `base_url`: `http://localhost:5000/api`
   - `access_token`: (will be set automatically)
   - `refresh_token`: (will be set automatically)

### Collection Setup

#### Register Request
- **Method:** POST
- **URL:** `{{base_url}}/auth/register`
- **Body (JSON):**
```json
{
  "email": "test@example.com",
  "username": "testuser",
  "password": "password123"
}
```
- **Tests (Script):**
```javascript
pm.test("Registration successful", function() {
    pm.response.to.have.status(201);
    var jsonData = pm.response.json();
    pm.environment.set("access_token", jsonData.access_token);
    pm.environment.set("refresh_token", jsonData.refresh_token);
});
```

#### Login Request
- **Method:** POST
- **URL:** `{{base_url}}/auth/login`
- **Body (JSON):**
```json
{
  "email": "test@example.com",
  "password": "password123"
}
```
- **Tests (Script):**
```javascript
pm.test("Login successful", function() {
    pm.response.to.have.status(200);
    var jsonData = pm.response.json();
    pm.environment.set("access_token", jsonData.access_token);
    pm.environment.set("refresh_token", jsonData.refresh_token);
});
```

#### Protected Requests
For all protected endpoints, add to **Headers:**
- **Key:** `Authorization`
- **Value:** `Bearer {{access_token}}`

## Testing with JavaScript (Frontend)

```javascript
// API Client Class
class MilkCalculatorAPI {
    constructor(baseURL = 'http://localhost:5000/api') {
        this.baseURL = baseURL;
        this.accessToken = null;
        this.refreshToken = null;
    }

    async register(email, username, password) {
        const response = await fetch(`${this.baseURL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, username, password })
        });
        const data = await response.json();
        
        if (response.ok) {
            this.accessToken = data.access_token;
            this.refreshToken = data.refresh_token;
            localStorage.setItem('access_token', this.accessToken);
            localStorage.setItem('refresh_token', this.refreshToken);
        }
        
        return data;
    }

    async login(email, password) {
        const response = await fetch(`${this.baseURL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const data = await response.json();
        
        if (response.ok) {
            this.accessToken = data.access_token;
            this.refreshToken = data.refresh_token;
            localStorage.setItem('access_token', this.accessToken);
            localStorage.setItem('refresh_token', this.refreshToken);
        }
        
        return data;
    }

    async refreshAccessToken() {
        const response = await fetch(`${this.baseURL}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: this.refreshToken })
        });
        const data = await response.json();
        
        if (response.ok) {
            this.accessToken = data.access_token;
            localStorage.setItem('access_token', this.accessToken);
        }
        
        return data;
    }

    async getMilkRecords() {
        const response = await fetch(`${this.baseURL}/milk/records`, {
            headers: {
                'Authorization': `Bearer ${this.accessToken}`
            }
        });
        
        if (response.status === 401) {
            await this.refreshAccessToken();
            return this.getMilkRecords(); // Retry
        }
        
        return await response.json();
    }

    async addMilkRecord(milkQty, date) {
        const response = await fetch(`${this.baseURL}/milk/records`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.accessToken}`
            },
            body: JSON.stringify({ milk_qty: milkQty, date })
        });
        
        if (response.status === 401) {
            await this.refreshAccessToken();
            return this.addMilkRecord(milkQty, date); // Retry
        }
        
        return await response.json();
    }

    async logout() {
        await fetch(`${this.baseURL}/auth/logout`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.accessToken}`
            }
        });
        
        this.accessToken = null;
        this.refreshToken = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
    }
}

// Usage Example
const api = new MilkCalculatorAPI();

// Register
await api.register('test@example.com', 'testuser', 'password123');

// Login
await api.login('test@example.com', 'password123');

// Get records
const records = await api.getMilkRecords();
console.log(records);

// Add record
await api.addMilkRecord(2.5, '2025-01-15');

// Logout
await api.logout();
```

## Error Responses

### 400 Bad Request
```json
{
  "message": "Email and password required"
}
```

### 401 Unauthorized
```json
{
  "message": "Token is invalid or expired"
}
```

### 403 Forbidden
```json
{
  "message": "Please verify your email"
}
```

### 404 Not Found
```json
{
  "message": "Record not found"
}
```

### 409 Conflict
```json
{
  "message": "Email already registered"
}
```

## Token Expiry

- **Access Token:** 24 hours
- **Refresh Token:** 30 days

When access token expires, use the refresh endpoint to get a new one.

## Security Notes

1. **HTTPS Only in Production:** Always use HTTPS in production
2. **Store Tokens Securely:** 
   - Don't store in localStorage for sensitive apps
   - Use httpOnly cookies for web apps
3. **Token Rotation:** Refresh tokens are single-use
4. **Logout:** Always invalidate refresh token on logout

## Deployment on Railway

Your existing app works with both:
- **Web Interface:** Session-based (your existing routes)
- **API:** JWT-based (`/api/*` endpoints)

Both can coexist! No changes needed to your existing web interface.
# Authentication System - NeuroFeed

## Overview

The NeuroFeed authentication system provides secure user registration and login with JWT-based token authentication. Users can create accounts, log in, or continue as guests.

---

## Features

✅ **User Registration** - Sign up with email and password
✅ **Secure Login** - Email/password authentication with hashed passwords
✅ **Token-Based Auth** - JWT tokens for API requests
✅ **Guest Mode** - Continue as guest without account
✅ **User Profile** - Display and manage user account
✅ **Automatic Onboarding** - New users auto-onboarded to recommendation system

---

## Project Structure

### Frontend

```
frontend/
├── login.html           # Login page
├── signup.html          # Registration page
├── auth.css             # Shared authentication styles
├── auth.js              # Shared authentication utilities
├── index.html           # Updated with user menu
├── app.js               # Updated with auth checks
└── styles.css           # Updated with user menu styles
```

### Backend

```
backend/
├── main.py              # Updated with auth endpoints
auth.py                  # Authentication module
```

### Database

```
auth.sqlite              # User authentication database (auto-created)
```

---

## Database Schema

### `auth_users` Table

```sql
CREATE TABLE auth_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    user_id TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);

CREATE INDEX idx_email ON auth_users(email);
CREATE INDEX idx_user_id ON auth_users(user_id);
```

### `auth_tokens` Table

```sql
CREATE TABLE auth_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_valid BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES auth_users(user_id)
);
```

---

## API Endpoints

### Sign Up

**POST** `/auth/signup`

Request:
```json
{
    "email": "user@example.com",
    "password": "SecurePass123"
}
```

Response (201):
```json
{
    "user_id": "U1a2b3c4d5e6f7890",
    "email": "user@example.com",
    "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

Errors:
- 400: Invalid email format
- 400: Password too short (< 8 characters)
- 400: Email already registered

---

### Login

**POST** `/auth/login`

Request:
```json
{
    "email": "user@example.com",
    "password": "SecurePass123"
}
```

Response (200):
```json
{
    "user_id": "U1a2b3c4d5e6f7890",
    "email": "user@example.com",
    "token": "eyJhbGciOiJIUzI1NiIs..."
}
```

Errors:
- 401: Invalid email or password
- 400: Missing credentials

---

### Verify Token

**POST** `/auth/verify`

Query Parameters:
- `token`: Authentication token

Response (200):
```json
{
    "valid": true,
    "user_id": "U1a2b3c4d5e6f7890"
}
```

Errors:
- 401: Invalid or expired token

---

### Get User Info

**GET** `/auth/user/{user_id}`

Response (200):
```json
{
    "id": 1,
    "email": "user@example.com",
    "user_id": "U1a2b3c4d5e6f7890",
    "created_at": "2026-04-19T12:00:00"
}
```

---

## Frontend Pages

### Login Page (`login.html`)

- Email input with validation
- Password input
- "Sign In" button with loading state
- "Continue as Guest" option
- Link to signup page
- Modern, responsive design
- Error message display
- Gradient background with animations

**URL**: `http://localhost:8000/app/login.html`

---

### Signup Page (`signup.html`)

- Email input with format validation
- Password input with strength requirements
  - Minimum 8 characters
  - Must contain letters and numbers
- Confirm password with matching validation
- "Create Account" button with loading state
- "Continue as Guest" option
- Link to login page
- Same design as login page
- Real-time validation feedback

**URL**: `http://localhost:8000/app/signup.html`

---

## Authentication Flow

### New User Registration

```
1. User visits signup.html
2. Enters email and password
3. Frontend validates:
   - Email format
   - Password requirements
   - Password confirmation match
4. POST to /auth/signup
5. Backend:
   - Checks for duplicate email
   - Hashes password with salt
   - Creates user record
   - Generates user_id
   - Auto-onboards user
   - Returns token
6. Frontend:
   - Stores user_id in localStorage
   - Stores token in localStorage
   - Redirects to index.html
```

### Returning User Login

```
1. User visits login.html
2. Enters email and password
3. Frontend validates credentials format
4. POST to /auth/login
5. Backend:
   - Looks up user by email
   - Verifies password hash
   - Generates new token
   - Returns token
6. Frontend:
   - Stores user_id in localStorage
   - Stores token in localStorage
   - Redirects to index.html
```

### Authenticated API Requests

```
1. Frontend includes token in Authorization header:
   Authorization: Bearer <token>
2. Backend validates token on protected routes
3. If invalid/expired:
   - Return 401 Unauthorized
   - Frontend redirects to login
```

### Guest Mode

```
1. User clicks "Continue as Guest"
2. Frontend generates guest_id: guest_<random>
3. Stores in localStorage:
   - userId: guest_<random>
   - isGuest: true
4. No token needed for guest requests
5. Guest can browse but limited features
```

---

## Password Security

### Password Hashing

- Uses PBKDF2-HMAC-SHA256
- Salt: 16 bytes random hex
- Iterations: 100,000
- Format: `salt$hash`

### Example Flow

```python
password = "MyPassword123"
salt = secrets.token_hex(16)  # e.g., "a1b2c3d4e5f6..."
hash = pbkdf2_hmac('sha256', password, salt, 100000)
stored = f"{salt}${hash.hex()}"  # e.g., "a1b2c3d4e5f6...5d8e9f0g1..."
```

---

## Local Storage Keys

| Key | Purpose | Format |
|-----|---------|--------|
| `userId` | Current user ID | `U<hex>` or `guest_<random>` |
| `userEmail` | User email | `user@example.com` |
| `token` | Auth token | JWT token |
| `isGuest` | Guest mode flag | `"true"` or not set |

---

## Running the System

### 1. Start Backend

```powershell
cd D:\final\final
.\venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Access Application

**App Home**: `http://localhost:8000/app`
**Login**: `http://localhost:8000/app/login.html`
**Signup**: `http://localhost:8000/app/signup.html`

### 3. User Flow

1. First time → `signup.html` to create account
2. Returning → `login.html` to log in
3. Either → Click "Continue as Guest" for anonymous access
4. After auth → Redirected to `index.html` (main news feed)

---

## Error Handling

### Frontend Validation

- Email format
- Password length (≥ 8 chars)
- Password complexity (letters + numbers)
- Password matching
- Empty field checks

### Backend Validation

- Duplicate email check
- Password strength verification
- SQL injection prevention (parameterized queries)
- Invalid email format
- User account status

### Error Messages

User-friendly messages displayed:
- "Email already registered"
- "Invalid email format"
- "Password must be at least 8 characters"
- "Passwords do not match"
- "Connection error. Please try again."

---

## Testing

### Test Signup

```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass123"}'
```

### Test Login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass123"}'
```

### Test Protected Endpoint

```bash
curl http://localhost:8000/auth/user/U<user_id> \
  -H "Authorization: Bearer <token>"
```

---

## Future Enhancements

- [ ] Email verification
- [ ] Password reset via email
- [ ] OAuth integration (Google, GitHub)
- [ ] Two-factor authentication
- [ ] User profile editing
- [ ] Account deletion
- [ ] Session management
- [ ] Rate limiting on auth endpoints
- [ ] Audit logging

---

## Security Best Practices

✅ Passwords hashed with salt and 100k iterations
✅ Token-based stateless authentication
✅ HTTPS recommended for production
✅ CORS enabled for localhost (configure for production)
✅ Parameterized SQL queries
✅ Email uniqueness enforced
✅ Token expiration (30 days)
✅ Secure random token generation

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'auth'"

Make sure you're running from the correct directory:
```powershell
cd D:\final\final
```

### "Email already registered"

Use a different email or reset the `auth.sqlite` database:
```powershell
rm auth.sqlite  # Delete old database
# Backend will auto-create new one on startup
```

### "Invalid email or password"

- Check email is correct
- Password is case-sensitive
- Ensure account was created

### Token expiration

- Log out and log in again
- Token validity is 30 days

---

## Support

For issues or questions:
1. Check terminal logs for backend errors
2. Check browser console for frontend errors
3. Verify database file exists: `auth.sqlite`
4. Ensure backend is running on port 8000

---

Created: 2026-04-19
Last Updated: 2026-04-19
Version: 1.0.0

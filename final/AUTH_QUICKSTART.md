# Authentication System - Quick Start Guide

## ⚡ 5-Minute Setup

### 1. Start Backend

```powershell
cd D:\final\final
.\venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

✅ Wait for: `Application startup complete.`

---

### 2. Open Frontend

Visit in browser:
```
http://localhost:8000/app
```

---

## 🔐 Using Authentication

### New User? Sign Up

1. Go to: `http://localhost:8000/app/signup.html`
2. Enter:
   - Email: `you@example.com`
   - Password: `MyPassword123` (8+ chars, letters + numbers)
   - Confirm password
3. Click **Create Account**
4. ✅ Auto-redirected to news feed

### Existing User? Log In

1. Go to: `http://localhost:8000/app/login.html`
2. Enter email and password
3. Click **Sign In**
4. ✅ Redirected to news feed

### No Account? Use Guest Mode

1. On login or signup page
2. Click **Continue as Guest**
3. ✅ Access app without account
4. Limited features available

---

## 👤 User Menu

In the top-right of the news feed:

```
your_email ▼  [Click to expand]
  → Logout
```

Click **Logout** to return to login page.

---

## 📝 Database

Authentication database is **auto-created** on first run:

```
d:\final\final\auth.sqlite
```

Files created:
- `auth_users` table - stores email, password hash, user_id
- `auth_tokens` table - manages authentication tokens

---

## 🛠️ Testing

### Test Signup via curl

```bash
curl -X POST http://localhost:8000/auth/signup ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"test@example.com\",\"password\":\"TestPass123\"}"
```

### Test Login via curl

```bash
curl -X POST http://localhost:8000/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"test@example.com\",\"password\":\"TestPass123\"}"
```

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Secure Signup** | Email + password with validation |
| **Secure Login** | Email/password with hashed verification |
| **Auto Onboard** | New users auto-added to recommendation system |
| **Guest Mode** | Anonymous access without account |
| **Token Auth** | JWT-based authentication |
| **User Menu** | Profile and logout from app |
| **Responsive** | Works on mobile and desktop |

---

## 📚 Pages

| URL | Purpose |
|-----|---------|
| `http://localhost:8000/app/login.html` | User login |
| `http://localhost:8000/app/signup.html` | New user registration |
| `http://localhost:8000/app/index.html` | Main news feed (requires auth) |
| `http://localhost:8000/app` | App home (redirects based on auth) |

---

## 🚨 Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'auth'"

**Solution**: Check working directory
```powershell
cd D:\final\final  # Must be in project root
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Problem: "Email already registered"

**Solution**: Use different email or delete database
```powershell
rm auth.sqlite  # Creates new database on next startup
```

### Problem: Page redirects to login

**Solution**: Database might not be initialized
1. Check backend console for errors
2. Stop backend (Ctrl+C)
3. Delete `auth.sqlite`
4. Restart backend

### Problem: Can't reach http://localhost:8000

**Solution**: Backend might not be running
1. Check terminal for "Application startup complete"
2. Ensure port 8000 is free
3. Restart backend

---

## 📋 Password Requirements

- **Length**: Minimum 8 characters
- **Characters**: Mix of letters and numbers
- **Case**: Case-sensitive
- **Special chars**: Not required but allowed

Examples:
- ✅ `MyPassword123`
- ✅ `Secure@Pass99`
- ❌ `password` (too short)
- ❌ `12345678` (no letters)
- ❌ `abcdefgh` (no numbers)

---

## 🔒 Security

All passwords are:
- Hashed with PBKDF2-HMAC-SHA256
- Salted with 16 bytes random data
- Iterated 100,000 times
- Never stored in plain text

Tokens:
- Valid for 30 days
- Unique per login
- Invalidated on logout

---

## 📞 Need Help?

See full documentation in [AUTHENTICATION.md](AUTHENTICATION.md)

Features include:
- API endpoint reference
- Database schema details
- Authentication flow diagrams
- Testing procedures
- Production deployment guide

---

Ready? Start with **Sign Up** or **Log In**! 🚀

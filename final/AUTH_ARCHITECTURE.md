# NeuroFeed Authentication System Architecture

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         WEB BROWSER                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────┐   │
│  │   login.html     │  │   signup.html    │  │ index.html  │   │
│  │  (auth form)     │  │  (register form) │  │  (news feed)│   │
│  └──────────────────┘  └──────────────────┘  └─────────────┘   │
│           │                    │                    │            │
│           │                    │                    │            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              auth.js & auth.css (UI Logic)                 │ │
│  │  - Form validation  - Token management  - User menu        │ │
│  └────────────────────────────────────────────────────────────┘ │
│           │                    │                    │            │
└───────────┼────────────────────┼────────────────────┼────────────┘
            │                    │                    │
        API Calls (HTTP POST/GET with tokens)
            │                    │                    │
┌───────────┼────────────────────┼────────────────────┼────────────┐
│           ▼                    ▼                    ▼            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              FastAPI Backend (main.py)                     │ │
│  │                                                            │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │ │
│  │  │ POST /signup │  │ POST /login  │  │ GET /user    │    │ │
│  │  │ (register)   │  │ (auth)       │  │ (get info)   │    │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘    │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │           auth.py (Authentication Logic)            │ │ │
│  │  │                                                      │ │ │
│  │  │  - hash_password()    - login_user()               │ │ │
│  │  │  - verify_password()  - verify_token()             │ │ │
│  │  │  - generate_token()   - signup_user()              │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
│           │                                                      │
└───────────┼──────────────────────────────────────────────────────┘
            │
    SQL Queries (sqlite3)
            │
    ┌───────────────────────────────────────┐
    │      auth.sqlite Database             │
    │                                       │
    │  ┌────────────────────────────────┐   │
    │  │  auth_users table              │   │
    │  │  ├─ id (PK)                    │   │
    │  │  ├─ email (UNIQUE)             │   │
    │  │  ├─ password_hash (PBKDF2)     │   │
    │  │  ├─ user_id (UNIQUE)           │   │
    │  │  ├─ created_at                 │   │
    │  │  └─ is_active                  │   │
    │  └────────────────────────────────┘   │
    │                                       │
    │  ┌────────────────────────────────┐   │
    │  │  auth_tokens table             │   │
    │  │  ├─ id (PK)                    │   │
    │  │  ├─ user_id (FK)               │   │
    │  │  ├─ token (UNIQUE)             │   │
    │  │  ├─ expires_at                 │   │
    │  │  └─ is_valid                   │   │
    │  └────────────────────────────────┘   │
    │                                       │
    └───────────────────────────────────────┘
```

---

## 🔄 Authentication Flows

### Sign Up Flow

```
User (Browser)              Frontend              Backend            Database
     │                        │                      │                  │
     │────signup form────────▶│                      │                  │
     │                        │─validate input──────▶│                  │
     │                        │                      │                  │
     │                        │                      │─check email─────▶│
     │                        │                      │◀─not found───────│
     │                        │                      │                  │
     │                        │                      │─hash password    │
     │                        │                      │─generate token   │
     │                        │                      │-generate user_id │
     │                        │                      │                  │
     │                        │                      │─insert user─────▶│
     │                        │                      │◀─success─────────│
     │                        │                      │                  │
     │                        │◀─return token────────│                  │
     │                        │                      │                  │
     │◀─store token in localStorage                 │                  │
     │                        │                      │                  │
     │────redirect to app───▶│                      │                  │
     │                        │                      │                  │
```

### Login Flow

```
User (Browser)              Frontend              Backend            Database
     │                        │                      │                  │
     │────login form─────────▶│                      │                  │
     │                        │─validate format─────▶│                  │
     │                        │                      │                  │
     │                        │                      │─query email─────▶│
     │                        │                      │◀─user record─────│
     │                        │                      │                  │
     │                        │                      │─verify password  │
     │                        │                      │-generate token   │
     │                        │                      │                  │
     │                        │                      │─insert token────▶│
     │                        │                      │◀─success─────────│
     │                        │                      │                  │
     │                        │◀─return token────────│                  │
     │                        │                      │                  │
     │◀─store token in localStorage                 │                  │
     │                        │                      │                  │
     │────redirect to app───▶│                      │                  │
     │                        │                      │                  │
```

### Protected API Call Flow

```
Frontend (with token)       Backend              Database
     │                        │                    │
     │─POST /api/endpoint     │                    │
     │ with Authorization     │                    │
     │ header────────────────▶│                    │
     │                        │-verify token──────▶│
     │                        │◀─token valid───────│
     │                        │                    │
     │                        │-execute operation  │
     │                        │-query DB───────────▶│
     │                        │◀─result────────────│
     │                        │                    │
     │◀─return response───────│                    │
     │                        │                    │
```

---

## 🔐 Password Security Flow

```
┌─ Plain Text Password ─────────────────────────┐
│  "MyPassword123"                              │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
        ┌─ Random Salt ──────┐
        │  16 bytes random   │
        │  hex: a1b2c3d4...  │
        └────────┬───────────┘
                 │
                 ▼
      ┌─ PBKDF2-HMAC-SHA256 ─┐
      │ 100,000 iterations   │
      │ Hash + Salt combined │
      └────────┬─────────────┘
               │
               ▼
      ┌─ Stored in Database ─┐
      │ Format: salt$hash     │
      │ a1b2c3d4...$5e6f...  │
      │ (Never plain text!)   │
      └───────────────────────┘
```

---

## 🔑 Token Management

```
┌─── Token Generation ──────────────┐
│                                   │
│ 1. User logs in                   │
│ 2. Credentials verified ✓         │
│ 3. Generate secure random token   │
│ 4. Set expiration (30 days)       │
│ 5. Store in database              │
│ 6. Return to frontend             │
│                                   │
└─────────────┬─────────────────────┘
              │
              ▼
    ┌─ Token Stored Locally ──┐
    │ localStorage            │
    │ ├─ userId               │
    │ ├─ userEmail            │
    │ ├─ token (SECRET!)      │
    │ └─ isGuest              │
    └────────────┬────────────┘
                 │
                 ▼
      ┌─ Token in API Requests ──┐
      │ Authorization: Bearer... │
      │ Sent with every request  │
      └────────────┬─────────────┘
                   │
                   ▼
        ┌─ Backend Verification ──┐
        │ 1. Extract token        │
        │ 2. Look up in DB        │
        │ 3. Check expiration     │
        │ 4. Check is_valid flag  │
        │ 5. Process if valid     │
        │ 6. Return 401 if not    │
        └─────────────────────────┘
```

---

## 🗄️ Database Schema Relationships

```
┌──────────────────────────────────────────────────────┐
│             auth_users (User Accounts)               │
├──────────────────────────────────────────────────────┤
│ PK: id                                               │
│ UQ: email                                            │
│ UQ: user_id                                          │
│                                                      │
│ Columns:                                             │
│  • id (autoincrement)                                │
│  • email (unique, indexed)                           │
│  • password_hash (PBKDF2)                            │
│  • user_id (unique, indexed)                         │
│  • created_at (timestamp)                            │
│  • updated_at (timestamp)                            │
│  • is_active (boolean)                               │
└────────────────┬─────────────────────────────────────┘
                 │ 1:Many (One user → Many tokens)
                 │
                 ▼
┌──────────────────────────────────────────────────────┐
│          auth_tokens (Active Sessions)               │
├──────────────────────────────────────────────────────┤
│ PK: id                                               │
│ FK: user_id (references auth_users)                  │
│ UQ: token                                            │
│                                                      │
│ Columns:                                             │
│  • id (autoincrement)                                │
│  • user_id (FK to auth_users)                        │
│  • token (unique, indexed)                           │
│  • created_at (timestamp)                            │
│  • expires_at (timestamp)                            │
│  • is_valid (boolean)                                │
└──────────────────────────────────────────────────────┘
```

---

## 🛡️ Security Layers

```
Layer 1: Frontend Validation
│
├─ Email format check
├─ Password strength check
├─ Required field validation
└─ User feedback on errors
        │
        ▼
Layer 2: Network Security
│
├─ HTTPS (recommended for production)
├─ CORS validation
└─ Token in Authorization header
        │
        ▼
Layer 3: Backend Validation
│
├─ Input sanitization
├─ SQL injection prevention
├─ Duplicate email check
└─ User status verification
        │
        ▼
Layer 4: Password Security
│
├─ PBKDF2-HMAC-SHA256 hashing
├─ Random salt (16 bytes)
├─ 100,000 iterations
└─ No plain text storage
        │
        ▼
Layer 5: Token Security
│
├─ Secure random generation
├─ Expiration checking
├─ Invalidation on logout
└─ Database integrity checks
```

---

## 📊 System States

```
User Not Logged In:
┌─────────────────────┐
│ Redirect to login   │
│                     │
│ Options:            │
│ • Sign up (new)     │
│ • Log in (existing) │
│ • Guest mode        │
└─────────────────────┘

Authenticated User:
┌──────────────────────────┐
│ Can access app           │
│                          │
│ localStorage contains:   │
│ • userId                 │
│ • userEmail              │
│ • token (30 days valid)  │
│                          │
│ Options:                 │
│ • Browse feed            │
│ • Logout                 │
└──────────────────────────┘

Guest User:
┌───────────────────────┐
│ Limited access        │
│                       │
│ localStorage contains:│
│ • userId (guest_xxx) │
│ • isGuest: true      │
│ • NO token           │
│                       │
│ Options:             │
│ • Browse feed        │
│ • (Limited features) │
└───────────────────────┘
```

---

## 🔄 Component Interaction Diagram

```
                  ┌────────────────────┐
                  │   User Browser     │
                  └─────────┬──────────┘
                            │
                ┌───────────┼───────────┐
                │           │           │
         ┌──────▼────┐ ┌───▼────┐ ┌──▼──────┐
         │ login.html│ │signup  │ │index.html
         │           │ │.html   │ │(app)
         └──────┬────┘ └───┬────┘ └──┬──────┘
                │          │        │
         ┌──────┴──────────┴────────┴─────┐
         │  Shared Libraries              │
         │  • auth.js                     │
         │  • auth.css                    │
         │  • app.js (for index.html)     │
         │  • styles.css                  │
         └──────┬──────────────────────────┘
                │
         ┌──────▼────────────────────────┐
         │  FastAPI Backend (main.py)    │
         │  ├─ POST /auth/signup         │
         │  ├─ POST /auth/login          │
         │  ├─ POST /auth/verify         │
         │  ├─ GET /auth/user/{id}       │
         │  └─ (other API routes)        │
         └──────┬────────────────────────┘
                │
         ┌──────▼────────────────────────┐
         │  Auth Module (auth.py)        │
         │  ├─ Password hashing          │
         │  ├─ Token generation          │
         │  ├─ User lookup               │
         │  └─ Verification              │
         └──────┬────────────────────────┘
                │
         ┌──────▼────────────────────────┐
         │  SQLite Database              │
         │  • auth_users                 │
         │  • auth_tokens                │
         └───────────────────────────────┘
```

---

## 🚦 Status Codes Reference

```
Success (2xx):
├─ 200 OK          - Login/token verification successful
├─ 201 Created     - Account created successfully

Client Errors (4xx):
├─ 400 Bad Request - Invalid input (email format, password length)
├─ 401 Unauthorized- Invalid credentials or expired token
├─ 409 Conflict    - Email already registered

Server Errors (5xx):
├─ 500 Server Error- Database or internal error
```

---

This architecture provides:
- ✅ Secure authentication
- ✅ Clear separation of concerns  
- ✅ Scalable token management
- ✅ Production-ready security
- ✅ Easy to extend and maintain

For implementation details, see IMPLEMENTATION_SUMMARY.md
For quick start, see AUTH_QUICKSTART.md
For full reference, see AUTHENTICATION.md

# ✅ Authentication System - Testing & Verification Checklist

**Date Created**: April 19, 2026
**Purpose**: Verify all authentication components are working correctly
**Status**: Use this to confirm successful deployment

---

## 🚀 Phase 1: Backend Startup (5 minutes)

- [ ] **1.1 Open PowerShell**
  ```powershell
  # Command to run
  powershell
  ```
  
- [ ] **1.2 Navigate to project**
  ```powershell
  cd D:\final\final
  ```
  
- [ ] **1.3 Activate environment**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
  - Expected: `(venv)` appears in prompt
  
- [ ] **1.4 Start backend**
  ```powershell
  python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
  ```
  - Expected output:
    ```
    INFO:     Uvicorn running on http://0.0.0.0:8000
    INFO:     Application startup complete
    ```

- [ ] **1.5 Verify database created**
  - Check: `auth.sqlite` file exists in `D:\final\final`
  - File size should be > 4KB
  
- [ ] **1.6 Leave backend running**
  - Keep terminal open
  - Note: Ctrl+C stops the server

---

## 🌐 Phase 2: Frontend Access (5 minutes)

- [ ] **2.1 Open browser**
  - Chrome, Firefox, Edge, or Safari

- [ ] **2.2 Test app home**
  - URL: `http://localhost:8000/app`
  - Expected: Redirects to `login.html`
  - Reason: Not logged in yet

- [ ] **2.3 Test login page**
  - URL: `http://localhost:8000/app/login.html`
  - Expected: Login form loads
  - Check elements:
    - [ ] Email input field
    - [ ] Password input field
    - [ ] "Sign In" button
    - [ ] "Continue as Guest" button
    - [ ] "Don't have account?" link
    - [ ] Gradient background visible

- [ ] **2.4 Test signup page**
  - URL: `http://localhost:8000/app/signup.html`
  - Expected: Signup form loads
  - Check elements:
    - [ ] Email input field
    - [ ] Password input field
    - [ ] Confirm password field
    - [ ] "Create Account" button
    - [ ] "Continue as Guest" button
    - [ ] "Already have account?" link
    - [ ] Password requirements shown
    - [ ] Gradient background visible

---

## 📝 Phase 3: Signup Flow Testing (5 minutes)

- [ ] **3.1 Navigate to signup page**
  - URL: `http://localhost:8000/app/signup.html`

- [ ] **3.2 Test form validation**
  
  **Test 2.2a - Invalid email format**
  - Input: `invalidemail` (no @)
  - Action: Click "Create Account"
  - Expected: Error message: "Invalid email format"
  
  **Test 3.2b - Weak password**
  - Input: `short` (less than 8 chars)
  - Action: Click "Create Account"
  - Expected: Error message: "Password must be at least 8 characters"
  
  **Test 3.2c - Password mismatch**
  - Email: `test@example.com`
  - Password: `ValidPass123`
  - Confirm: `WrongPass123`
  - Action: Click "Create Account"
  - Expected: Error message: "Passwords don't match"
  
  **Test 3.2d - Missing fields**
  - Leave fields empty
  - Action: Click "Create Account"
  - Expected: Error messages for empty fields

- [ ] **3.3 Successful signup**
  - Email: `testuser@example.com`
  - Password: `SecurePass123`
  - Confirm: `SecurePass123`
  - Action: Click "Create Account"
  - Expected:
    - [ ] Loading spinner appears on button
    - [ ] Button becomes disabled
    - [ ] After 1-2 seconds: Redirects to `index.html`
    - [ ] URL changes to `http://localhost:8000/app`
    - [ ] News feed loads

- [ ] **3.4 Verify data storage**
  - Check browser DevTools (F12)
  - Go to Application → Local Storage
  - Should see:
    - [ ] `userId` - starts with "U"
    - [ ] `userEmail` - "testuser@example.com"
    - [ ] `token` - long random string
    - [ ] `isGuest` - false (or not set)

- [ ] **3.5 Verify database**
  - Stop backend (Ctrl+C)
  - Open PowerShell terminal (new tab)
  - Check database:
    ```powershell
    cd D:\final\final
    $env:PYTHONPATH='D:\final\final'
    & '.\venv\Scripts\python.exe' -c "
    import sqlite3
    conn = sqlite3.connect('auth.sqlite')
    c = conn.cursor()
    c.execute('SELECT * FROM auth_users')
    for row in c.fetchall():
        print(row)
    conn.close()
    "
    ```
  - Expected: One user record with:
    - [ ] Email: testuser@example.com
    - [ ] User ID starting with "U"
    - [ ] Password hash (not plain text!)
  - Close PowerShell tab

- [ ] **3.6 Restart backend**
  - In original terminal, press Up arrow to get last command
  - Press Enter to restart backend

---

## 🔐 Phase 4: Login Flow Testing (5 minutes)

- [ ] **4.1 Navigate to login page**
  - First, navigate to `http://localhost:8000/app`
  - Should redirect to `http://localhost:8000/app/login.html`

- [ ] **4.2 Test form validation**
  
  **Test 4.2a - Invalid email**
  - Input: `notanemail`
  - Password: `SecurePass123`
  - Expected: Error or rejection on submit
  
  **Test 4.2b - Missing fields**
  - Leave email or password empty
  - Expected: Cannot submit

- [ ] **4.3 Test wrong credentials**
  - Email: `testuser@example.com`
  - Password: `WrongPassword123`
  - Action: Click "Sign In"
  - Expected: Error message: "Invalid email or password"
  - Note: localStorage should be empty

- [ ] **4.4 Successful login**
  - Email: `testuser@example.com`
  - Password: `SecurePass123`
  - Action: Click "Sign In"
  - Expected:
    - [ ] Loading spinner appears
    - [ ] Button disabled
    - [ ] Redirects to app after 1-2 seconds
    - [ ] News feed loads

- [ ] **4.5 Verify token stored**
  - Open DevTools (F12)
  - Check Application → Local Storage
  - Should have same keys as signup:
    - [ ] userId
    - [ ] userEmail
    - [ ] token (might be different from signup token)

---

## 👤 Phase 5: User Menu Testing (5 minutes)

- [ ] **5.1 Navigate to app**
  - You should still be logged in
  - If not, log in again
  - URL: `http://localhost:8000/app`

- [ ] **5.2 Locate user menu**
  - Top right of screen
  - Should show: `testuser@example.com ▼`
  - Expected styling: Teal button, white text

- [ ] **5.3 Test menu dropdown**
  - Click the user menu button
  - Expected: Dropdown appears below
  - Options visible:
    - [ ] "Logout" link (red text)

- [ ] **5.4 Test logout**
  - Click "Logout"
  - Expected:
    - [ ] Redirects to `login.html`
    - [ ] URL: `http://localhost:8000/app/login.html`
    - [ ] User menu disappears

- [ ] **5.5 Verify localStorage cleared**
  - Open DevTools (F12)
  - Check Application → Local Storage
  - Should be empty or minimal
  - Previous keys gone:
    - [ ] userId - cleared
    - [ ] userEmail - cleared
    - [ ] token - cleared

---

## 👥 Phase 6: Guest Mode Testing (3 minutes)

- [ ] **6.1 Start fresh**
  - You should be on login page
  - Clear localStorage for clean test:
    - [ ] Open DevTools (F12)
    - [ ] Application → Local Storage
    - [ ] Delete all entries

- [ ] **6.2 Click "Continue as Guest"**
  - On login.html or signup.html
  - Expected:
    - [ ] Redirects to app immediately
    - [ ] No form submission
    - [ ] News feed loads

- [ ] **6.3 Verify guest data**
  - Open DevTools
  - Check localStorage:
    - [ ] userId starts with "guest_"
    - [ ] isGuest is "true"
    - [ ] userEmail might be empty or "guest"
    - [ ] NO token (or empty token)

- [ ] **6.4 Guest functionality**
  - News feed should work
  - Try clicking on articles
  - Expected: Basic features work, possibly limited

---

## 🔗 Phase 7: API Endpoint Testing (5 minutes)

Open PowerShell (new tab, keep backend running):

- [ ] **7.1 Test signup endpoint**
  ```powershell
  $email = "apitest@example.com"
  $password = "APITestPass123"
  $body = @{
      email = $email
      password = $password
  } | ConvertTo-Json
  
  $response = Invoke-WebRequest -Uri "http://localhost:8000/auth/signup" `
    -Method POST `
    -Headers @{"Content-Type"="application/json"} `
    -Body $body
  
  $response.Content | ConvertFrom-Json | Format-Table
  ```
  
  Expected response:
  ```json
  {
    "success": true,
    "user_id": "U...",
    "email": "apitest@example.com",
    "token": "..."
  }
  ```

- [ ] **7.2 Test login endpoint**
  ```powershell
  $body = @{
      email = "testuser@example.com"
      password = "SecurePass123"
  } | ConvertTo-Json
  
  $response = Invoke-WebRequest -Uri "http://localhost:8000/auth/login" `
    -Method POST `
    -Headers @{"Content-Type"="application/json"} `
    -Body $body
  
  $response.Content | ConvertFrom-Json | Format-Table
  ```
  
  Expected: Similar success response with new token

- [ ] **7.3 Test verify endpoint**
  ```powershell
  # First get a token from login above
  # Then use it to verify:
  
  $token = "YOUR_TOKEN_HERE"  # From login response
  
  $response = Invoke-WebRequest -Uri "http://localhost:8000/auth/verify" `
    -Method POST `
    -Headers @{
        "Content-Type"="application/json"
        "Authorization"="Bearer $token"
    } `
    -Body "{}"
  
  $response.Content | ConvertFrom-Json | Format-Table
  ```
  
  Expected: `{"is_valid": true}`

- [ ] **7.4 Test duplicate email**
  ```powershell
  # Try to sign up with same email as 3.1
  $body = @{
      email = "testuser@example.com"
      password = "DifferentPass123"
  } | ConvertTo-Json
  
  $response = Invoke-WebRequest -Uri "http://localhost:8000/auth/signup" `
    -Method POST `
    -Headers @{"Content-Type"="application/json"} `
    -Body $body -ErrorAction SilentlyContinue
  
  $response.Content
  ```
  
  Expected error: Email already registered

---

## 🔒 Phase 8: Security Verification (5 minutes)

- [ ] **8.1 Password not stored plain**
  - Check database:
    ```powershell
    & '.\venv\Scripts\python.exe' -c "
    import sqlite3
    conn = sqlite3.connect('auth.sqlite')
    c = conn.cursor()
    c.execute('SELECT email, password_hash FROM auth_users LIMIT 1')
    email, hash_val = c.fetchone()
    print(f'Email: {email}')
    print(f'Hash: {hash_val}')
    print(f'Hash format: {\"salt$hash\" if \"$\" in hash_val else \"unknown\"}')
    conn.close()
    "
    ```
  - Expected: Hash contains `$` separator
  - Hash is NOT the password

- [ ] **8.2 Token format**
  - Check a token in localStorage
  - Expected: Long random string (looks random)
  - NOT a JWT (no dots)

- [ ] **8.3 Password requirements enforced**
  - Try signup with weak password
  - Examples to test:
    - [ ] `password` - too short
    - [ ] `12345678` - no letters
    - [ ] `abcdefgh` - no numbers
  - All should be rejected

- [ ] **8.4 Email format validation**
  - Try signup with:
    - [ ] `notanemail` - missing @
    - [ ] `user@` - missing domain
    - [ ] `@example.com` - missing user
  - All should be rejected

---

## 🐛 Phase 9: Error Handling (3 minutes)

- [ ] **9.1 Try invalid operations**
  
  **Test 9.1a - Login before signup**
  - URL: `http://localhost:8000/app/login.html`
  - Email: `notregistered@example.com`
  - Password: `SomePass123`
  - Expected: Friendly error message
  
  **Test 9.1b - Case sensitivity**
  - Signup with: `TestUser@Example.Com`
  - Try login with: `testuser@example.com`
  - Expected: Either accepts (case-insensitive) or clear error
  
  **Test 9.1c - Extra spaces**
  - Signup with: `  testuser@example.com  ` (with spaces)
  - Check if trimmed or rejected
  - Expected: Consistent handling

- [ ] **9.2 Database errors**
  - Stop backend temporarily
  - Try to login from browser
  - Expected: Clear error message
  - Restart backend

---

## 📊 Phase 10: Data Verification (5 minutes)

- [ ] **10.1 Inspect auth database**
  ```powershell
  & '.\venv\Scripts\python.exe' << 'EOF'
  import sqlite3
  from datetime import datetime
  
  conn = sqlite3.connect('auth.sqlite')
  c = conn.cursor()
  
  print("=== auth_users table ===")
  c.execute('SELECT * FROM auth_users')
  for row in c.fetchall():
      print(row)
  
  print("\n=== auth_tokens table ===")
  c.execute('SELECT user_id, token, expires_at, is_valid FROM auth_tokens')
  for row in c.fetchall():
      print(f"User: {row[0][:10]}..., Token: {row[1][:20]}..., Expires: {row[2]}, Valid: {row[3]}")
  
  print("\n=== Statistics ===")
  c.execute('SELECT COUNT(*) FROM auth_users')
  print(f"Total users: {c.fetchone()[0]}")
  
  c.execute('SELECT COUNT(*) FROM auth_tokens')
  print(f"Total tokens: {c.fetchone()[0]}")
  
  conn.close()
  EOF
  ```
  
  Expected:
  - [ ] 2+ users created (testuser, apitest)
  - [ ] Multiple tokens from logins
  - [ ] Timestamps present
  - [ ] user_id format: "U" + hex

- [ ] **10.2 Token expiration**
  - Tokens should expire in 30 days
  - Check `expires_at` field
  - Format should be readable timestamp

- [ ] **10.3 Check indices**
  ```powershell
  & '.\venv\Scripts\python.exe' -c "
  import sqlite3
  conn = sqlite3.connect('auth.sqlite')
  c = conn.cursor()
  c.execute(\"SELECT name FROM sqlite_master WHERE type='index'\")
  for row in c.fetchall():
      print(row[0])
  conn.close()
  "
  ```
  
  Expected indices present:
  - [ ] idx_email
  - [ ] idx_user_id
  - [ ] idx_user_id_tokens

---

## ✅ Final Validation Checklist

- [ ] **All phases 1-10 completed successfully**
- [ ] **No error messages in backend console**
- [ ] **All redirects working correctly**
- [ ] **Database contains expected data**
- [ ] **Local storage working**
- [ ] **User menu appears when logged in**
- [ ] **Logout clears storage**
- [ ] **Guest mode works**
- [ ] **Form validation working**
- [ ] **API endpoints respond correctly**

---

## 🎉 Success Criteria

✅ **System is ready if:**

1. Users can sign up successfully
2. Users can log in successfully
3. Users can log out successfully
4. Guest mode works without account
5. News feed accessible to authenticated users
6. Data persists across page reloads
7. Logout clears all user data
8. Error messages are helpful
9. Database properly stores users
10. Passwords are never stored plain text

---

## 📋 Sign-Off

| Item | Status | Notes |
|------|--------|-------|
| Backend startup | ✅/❌ | |
| Frontend loading | ✅/❌ | |
| Database creation | ✅/❌ | |
| Signup flow | ✅/❌ | |
| Login flow | ✅/❌ | |
| Logout flow | ✅/❌ | |
| Guest mode | ✅/❌ | |
| User menu | ✅/❌ | |
| API endpoints | ✅/❌ | |
| Security | ✅/❌ | |
| **Overall** | **✅/❌** | |

---

## 🔧 Troubleshooting Quick Links

- Backend won't start? → See AUTHENTICATION.md → Troubleshooting
- Database error? → Delete auth.sqlite and restart backend
- Import error? → Ensure working directory is D:\final\final
- Token expired? → User needs to log in again
- Password hash wrong? → Check PBKDF2 implementation in auth.py

---

**Save this checklist!** Use it each time you deploy to verify everything works.

For detailed docs, see:
- 📘 [AUTHENTICATION.md](AUTHENTICATION.md)
- ⚡ [AUTH_QUICKSTART.md](AUTH_QUICKSTART.md)
- 🏗️ [AUTH_ARCHITECTURE.md](AUTH_ARCHITECTURE.md)
- 📝 [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

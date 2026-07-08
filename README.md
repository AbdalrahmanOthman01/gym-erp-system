# Sport Time Gym — Management ERP Control Center

A high-performance, secure, and real-time desktop-integrated Gym Management ERP System. Built as a FastAPI monolithic application with a native desktop wrapper, designed for front-desk front-line operations, client management, point-of-sale checkout, and multi-tier role permissions.

---

## 🚀 Key Features

### 1. 👥 Multi-Role Authorization & Scope Controls
- 👑 **Super Admin**: Complete master override access. Handles settings, staff management, inventory templates, price adjustments, logs, and global financial audits.
- 💰 **Accountant / Branch Representative (BR)**: Restricts data fetching to gender-scoped scopes (Male accountants manage Male members, Female accountants manage Female members). Handles check-ins, renewals, payments, and QR stickers printing. Redirection guards block settings or configurations.

### 2. 🧾 Membership & Subscription Tiers
- Support for **Session-based**, **Time-based** (e.g. 30 days, 90 days), and **Unlimited** packages.
- Integrated package state controls (**Active**, **Expired**, **Frozen**, **Blocked**).
- Automated unfreezing on scanner check-in with recalculation of freeze offset extensions.

### 3. 📷 Webcam QR Check-in System
- No proprietary scanner hardware needed—uses HTML5-QR webcam, laptop, or mobile camera streams.
- Scans user UUID-based QR stickers (zero personal PII exposed inside QR string).
- Multi-scan avoidance protection, expired check-in rejections, and direct accountant notification for immediate renewal.

### 4. 💰 Point of Sale (POS) Cashier & Payments
- Register manual plan deposits, installments, and outstanding balances.
- Merchandise checkout terminal with stock counts, cost margins, sale prices, and low-stock warning telemetry.
- General gym expense outflow logger.

### 5. 📊 Live Telemetry & Revenue Range Auditing
- Real-time websocket notifications (`NEW_PAYMENT`, `CHECK_IN` activity feeds).
- Dynamic Chart.js visualizations (peak entry hours, visit frequency, plan splits).
- **Date Range Revenue & Profit History**: Search custom date ranges to audit daily subscriptions, POS sales, outflows, and net profit.
- **Daily Archive Search**: Double-click any day to list subscribed members and logged expenses side-by-side.

### 6. 🔒 Device Security Middleware
- Binds application startup to a Windows hardware license fingerprint using the cryptographic registry `MachineGuid` registry key. 
- Prevents unauthorized copies from executing on frontend devices without Admin approval.

---

## 🛠️ Technology Stack

- **Backend Framework**: FastAPI (Uvicorn HTTP ASGI server)
- **Database Engine**: SQLite with async SQLAlchemy + `aiosqlite` drivers
- **Frontend Frame**: HTML5 / TailwindCSS / Alpine.js (Lightweight interactive state)
- **Visuals**: FontAwesome Icons, Google Fonts (Outfit & Inter), Chart.js
- **Desktop Wrapper**: PyWebView (Native chromeless Win32 window wrap)
- **Compilation Tool**: PyInstaller

---

## 📦 Installation & Setup

### 1. Initialize Virtual Environment
```powershell
python -m venv venv
venv\Scripts\activate
```

### 2. Install Package Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Environment Configurations
Configure variables inside a `.env` file in the root directory:
```env
PROJECT_NAME="Sport Time Gym ERP"
VERSION="1.0"
SECRET_KEY="your-hexadecimal-secret-key"
ACCESS_TOKEN_EXPIRE_MINUTES=480
DATABASE_URL="sqlite+aiosqlite:///./gym_erp_db.db"
```

### 4. Seed Mock Historical Data
Generates rich, 6-month historical logs, telemetry, accounts, inventory, and transactions:
```powershell
venv\Scripts\python seed_db.py
```

---

## ⚡ Running the Application

### Option A: Standard Web App Mode
Runs Uvicorn web server exposed on port 8000. Access via browser at `http://127.0.0.1:8000`:
```powershell
venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

### Option B: Native Desktop App Mode
Launches the FastAPI server in a background thread and boots up the native control window:
```powershell
venv\Scripts\python gui.py
```

---

## 🔨 Building Standalone Executable (No Python Required)

To bundle the entire monolithic codebase (including python runtime, assets, templates, and libraries) into a single standalone `.exe` for front-desk deployment:

```powershell
venv\Scripts\python -m PyInstaller gui.spec --clean --noconfirm
```
The output executable will be compiled inside the `dist/` directory:
- **Location**: `dist/SportTimeGym.exe`

---

## 🔑 Default Login Credentials (Demo)

| Role | Username (Phone) | Password | Scope Details |
| :--- | :--- | :--- | :--- |
| **Super Admin** | `0000` | `password123` | Global HQ administration, full reports and settings |
| **Male Accountant** | `1111` | `password123` | Limited to Male member lists and actions |
| **Female Accountant** | `2222` | `password123` | Limited to Female member lists and actions |

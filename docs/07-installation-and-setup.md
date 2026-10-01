# 07 — Installation and Setup Guide (Windows 11)

This guide walks a student or developer through setting up and running NetworkAI on a fresh Windows 11 workstation.

---

## 1. Prerequisites

Ensure the following tools are installed on your Windows machine:
1. **Python 3.10, 3.11, or 3.12:**
   * Download from [python.org](https://www.python.org/downloads/).
   * *Critical:* Check the box **"Add Python to PATH"** during installation.
2. **Node.js (LTS version 18, 20, or 22):**
   * Download from [nodejs.org](https://nodejs.org/).
   * Includes `npm` package manager.
3. **PowerShell or Windows Terminal:** Default terminal in Windows 11.

Verify installations in PowerShell:
```powershell
python --version
# Expected: Python 3.10.x - 3.12.x

node --version
# Expected: v18.x.x - v22.x.x

npm --version
# Expected: 9.x.x or 10.x.x
```

---

## 2. Workspace Directory Structure

Navigate to your workspace root (e.g., `C:\Users\<username>\Desktop\CN PROJECT`):
```text
CN PROJECT/
├── backend/                  # FastAPI Application
│   ├── app/                  # Application code (models, services, schemas)
│   ├── tests/                # Automated pytest suite (145 tests)
│   ├── requirements.txt      # Python dependencies
│   └── seed_demo_scenario.py # Deterministic college demo seeder
├── frontend/                 # React 19 + Vite Application
│   ├── src/                  # Components, hooks, types, services
│   ├── package.json          # Node dependencies
│   └── vite.config.ts        # Vite build configuration
├── docs/                     # Documentation suite
└── network_monitoring.db     # SQLite persistence database (created on launch)
```

---

## 3. Backend Setup

Open a PowerShell terminal and navigate to the project directory:

```powershell
cd "C:\Users\darsh\OneDrive\Desktop\CN PROJECT"
```

### 3.1 Create and Activate Virtual Environment
```powershell
# Create virtual environment named .venv
python -m venv .venv

# Activate virtual environment
.\.venv\Scripts\Activate.ps1
```

*(If PowerShell displays an `ExecutionPolicy` error, run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` and try again).*

### 3.2 Install Python Dependencies
```powershell
pip install --upgrade pip
pip install -r backend/requirements.txt
```

Core dependencies installed:
* `fastapi`, `uvicorn`: Asynchronous web server
* `psutil`: Operating system hardware & network interface sampling
* `scikit-learn`, `numpy`: Isolation Forest and vector mathematics
* `sqlalchemy`: SQL Object-Relational Mapping
* `pytest`, `httpx`: Automated testing framework

---

## 4. Frontend Setup

Open a second PowerShell terminal:

```powershell
cd "C:\Users\darsh\OneDrive\Desktop\CN PROJECT\frontend"

# Install Node modules
npm install
```

---

## 5. Seed Demonstration Data (Optional but Recommended)

To populate the database with the pre-configured College Campus demonstration scenario (4 mock devices, topology links, and sample alerts):

```powershell
# Inside backend/ directory with .venv active:
cd "C:\Users\darsh\OneDrive\Desktop\CN PROJECT\backend"
python seed_demo_scenario.py
```

Output:
```text
[*] Initializing Database for Phase 7 Demo Scenario...
[*] Purging previous demo records (scoped strictly to demo-* identifiers)...
[*] Registering 4 Mock Devices...
[*] Generating Topology Links for demo-core-01...
[*] Discovery executed: 3 neighbors (2 resolved)
[*] Creating Demo Alert Lifecycle History...
[SUCCESS] Demo scenario seeded successfully!
          Demo Devices: 4 | Open Alerts: 2 | Acknowledged: 1 | Resolved: 1
```

---

## 6. Running the Application

### 6.1 Terminal 1: Start Backend API
```powershell
cd "C:\Users\darsh\OneDrive\Desktop\CN PROJECT\backend"
..\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
* Backend URL: `http://127.0.0.1:8000`
* Interactive API Documentation (Swagger): `http://127.0.0.1:8000/docs`

### 6.2 Terminal 2: Start Frontend Development Server
```powershell
cd "C:\Users\darsh\OneDrive\Desktop\CN PROJECT\frontend"
npm run dev
```
* Frontend Dashboard URL: `http://localhost:5173`

Open your web browser and navigate to **`http://localhost:5173`**.

---

## 7. How to Stop Services

To shut down NetworkAI safely:
1. In the backend terminal, press `Ctrl + C`. Uvicorn will trigger the graceful shutdown lifespan handler, stopping polling loops and closing database sessions.
2. In the frontend terminal, press `Ctrl + C` and type `Y` to terminate the Vite development server.
3. Deactivate the virtual environment: `deactivate`.

---

## 8. Common Troubleshooting Scenarios

### Error: Port 8000 Is Already in Use
* **Cause:** A previous instance of Uvicorn or another service is still running in the background.
* **Fix (PowerShell):**
  ```powershell
  Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force
  ```

### Error: Port 5173 Is in Use
* **Cause:** Vite will automatically offer to run on port 5174. If you prefer port 5173, kill the existing Node process:
  ```powershell
  Get-Process node | Stop-Process -Force
  ```

### Error: SQLite Database Locked (`OperationalError: database is locked`)
* **Cause:** Concurrent writers or an unclosed database browser application (like DB Browser for SQLite).
* **Fix:** Close external database inspection tools. NetworkAI's WAL mode handles concurrent application reads/writes automatically.

### Error: `psutil.AccessDenied`
* **Cause:** Certain corporate antivirus configurations restrict reading specific virtual network adapters.
* **Fix:** In the NetworkAI dashboard, switch the active monitoring interface from the header dropdown to standard `Wi-Fi` or `Ethernet`.

---

## 9. Verification & Automated Test Run

To verify that your installation is 100% sound:

```powershell
cd "C:\Users\darsh\OneDrive\Desktop\CN PROJECT\backend"
..\.venv\Scripts\Activate.ps1
pytest -q
```
**Expected Result:** `145 passed, 1 warning` in ~25 seconds.

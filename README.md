# 1. make project folder (if needed) & init git
mkdir odoo-hackathon-2025
cd odoo-hackathon-2025
git init

# 2. create README.md with the template (or open an editor and paste)
cat > README.md <<'EOF'
# [PROJECT_NAME] — Odoo x Amalthea IITGN Hackathon 2025

**TL;DR:** One-line pitch that judges will remember.

## Problem
A one-paragraph problem statement (what hurts today).

## Our solution
Short explanation of the product and the user impact.

## Tech stack
- Backend: FastAPI / Flask / Django (choose one)
- Frontend: React / Vue
- DB: SQLite (local) → Postgres (if time)
- Realtime: WebSockets / SSE / PubSub
- Offline: localStorage / IndexedDB + sync queue

## How to run (dev)
Prereqs: Python 3.10, Node.js, npm
1. Backend:
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn main:app --reload

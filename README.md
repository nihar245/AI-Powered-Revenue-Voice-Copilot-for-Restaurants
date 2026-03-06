# AI-Powered Revenue & Voice Copilot for Restaurants

AI-powered revenue intelligence engine and voice ordering copilot for restaurants, built on the PetPooja POS ecosystem.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Browser  (React + Vite)   localhost:5173               │
│  frontend/Frontend_mined/                               │
└─────────────────┬───────────────────────────────────────┘
                  │  HTTP  /api/*
┌─────────────────▼───────────────────────────────────────┐
│  Node.js / Express API     localhost:3000               │
│  backend/src/app.js                                     │
│  • Revenue Intelligence routes  (/api/revenue/*)        │
│  • Voice Copilot routes         (/api/voice/*)          │
│  • Menu / Orders / KOT / Auth   (/api/*)                │
└──────────┬──────────────────────────────────────────────┘
           │  HTTP  /test/*  (multipart audio)
┌──────────▼──────────────────────────────────────────────┐
│  Python FastAPI — Gemini Live Voice Service  :8002      │
│  ai_service_gemini/                                     │
│  • POST /test/voice-chat  — audio → cart + TTS          │
│  • POST /test/add-item    — upsell chip quick-add       │
│  • POST /test/confirm-order — write KOT to DB           │
│  • GET  /test/session/:id — session state               │
└──────────────────────┬──────────────────────────────────┘
                       │  asyncpg
┌──────────────────────▼──────────────────────────────────┐
│  PostgreSQL  cafe_odoo   localhost:5432                 │
│  18 tables: orders, menu_items, kot, customers, …       │
└─────────────────────────────────────────────────────────┘
```

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Node.js | ≥ 18 | [nodejs.org](https://nodejs.org) |
| Python | 3.10 – 3.12 | Conda or venv |
| PostgreSQL | 14 + | Installed locally |
| pgAdmin 4 | any | GUI for PostgreSQL |
| Git | any | |

---

## 1. PostgreSQL & pgAdmin Setup

### 1a. Create the database

Open **pgAdmin 4** → right-click **Databases** → **Create** → **Database**:

- **Database name:** `cafe_odoo`
- **Owner:** `postgres`
- Click **Save**

Or run in the pgAdmin **Query Tool** / psql:

```sql
CREATE DATABASE cafe_odoo OWNER postgres;
```

### 1b. Load the schema

In pgAdmin, open the Query Tool against `cafe_odoo` and run the contents of [schema.sql](schema.sql):

```
File → Open → schema.sql → Execute (F5)
```

### 1c. Seed static data

Run [final_static_seed.sql](final_static_seed.sql) in the same Query Tool:

```
File → Open → final_static_seed.sql → Execute (F5)
```

### 1d. Generate synthetic transactional data (optional but recommended)

```bash
cd "d:\projects\AI-Powered-Revenue-Voice-Copilot-for-Restaurants"
python "generate_data_final (1).py"
```

This inserts ~270,000 rows (orders, customers, KOTs, payments, feedback, inventory).

> **Note:** The script auto-reads DB credentials from environment variables or defaults to `postgres/password` on `localhost:5432/cafe_odoo`. Edit the top of the script if your credentials differ.

---

## 2. Python AI Service (ai_service_gemini — port 8002)

### 2a. Create and activate a conda environment

```bash
conda create -n ai_service python=3.11 -y
conda activate ai_service
```

### 2b. Install dependencies

```bash
cd "d:\projects\AI-Powered-Revenue-Voice-Copilot-for-Restaurants\ai_service_gemini"
pip install -r requirements.txt
```

### 2c. Configure environment variables

Edit `ai_service_gemini/.env` — it should already contain your Gemini API key. Confirm the DB URL matches your PostgreSQL setup:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/cafe_odoo
GEMINI_API_KEY=your_key_here
GEMINI_TEXT_MODEL=gemini-2.0-flash
GEMINI_AUDIO_MODEL=gemini-2.5-flash-native-audio-latest
```

### 2d. Start the service

```bash
cd "d:\projects\AI-Powered-Revenue-Voice-Copilot-for-Restaurants\ai_service_gemini"
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

Verify at: http://localhost:8002/docs

Expected startup output:
```
[startup] Cached 30 menu items, 10 tables from DB.
[startup] ai_service_gemini ready
```

---

## 3. Node.js Backend (port 3000)

### 3a. Install dependencies

```bash
cd "d:\projects\AI-Powered-Revenue-Voice-Copilot-for-Restaurants\backend"
npm install
```

### 3b. Configure environment variables

`backend/.env` is already created. Edit it with your actual PostgreSQL password and a strong JWT secret:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cafe_odoo
DB_USER=postgres
DB_PASSWORD=your_password

NODE_PORT=3000

JWT_SECRET=change_this_to_a_long_random_secret_at_least_32_chars

AI_SERVICE_URL=http://localhost:8002
```

### 3c. Start the server

**Development (auto-reload on file change):**
```bash
cd "d:\projects\AI-Powered-Revenue-Voice-Copilot-for-Restaurants\backend"
npm run dev
```

**Production:**
```bash
npm start
```

Expected output:
```
Migration check complete
PetPooja backend running on http://localhost:3000
```

Verify at: http://localhost:3000/api/health → `{"status":"ok"}`

---

## 4. React Frontend (port 5173)

### 4a. Install dependencies

```bash
cd "d:\projects\AI-Powered-Revenue-Voice-Copilot-for-Restaurants\frontend\Frontend_mined"
npm install
```

### 4b. Configure environment variables

`frontend/Frontend_mined/.env` is already created:

```env
VITE_API_URL=http://localhost:3000/api
VITE_DATA_DATE=
```

### 4c. Start the dev server

```bash
npm run dev
```

Open http://localhost:5173 in your browser.

---

## 5. Start Order (All Services Together)

Open **4 terminals** and run one command in each:

| Terminal | Command | URL |
|----------|---------|-----|
| 1 — AI Service | `cd ai_service_gemini && uvicorn main:app --port 8002 --reload` | :8002/docs |
| 2 — Backend | `cd backend && npm run dev` | :3000/api/health |
| 3 — Frontend | `cd frontend/Frontend_mined && npm run dev` | :5173 |
| 4 — pgAdmin | (open pgAdmin GUI separately) | localhost:pgAdmin port |

> **Important order:** Start the AI service first (it connects to DB on startup), then the backend, then the frontend.

---

## 6. pgAdmin Connection Settings

When connecting pgAdmin to the `cafe_odoo` database:

| Field | Value |
|-------|-------|
| Host | `localhost` |
| Port | `5432` |
| Maintenance DB | `cafe_odoo` |
| Username | `postgres` |
| Password | *(your PostgreSQL password)* |
| SSL mode | `Prefer` |

---

## 7. API Reference

### Revenue Intelligence (`/api/revenue/*`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/revenue/contribution-margin` | Item-level margin analysis |
| GET | `/api/revenue/menu-engineering` | Stars / Puzzles / Plowhorses / Dogs matrix |
| GET | `/api/revenue/top-combos` | Association-rule based combo suggestions |
| GET | `/api/revenue/aov` | Average order value by channel / time |
| GET | `/api/revenue/anomalies` | Daily revenue anomaly flags |
| GET | `/api/revenue/demand-forecast` | Next 7-day item demand forecast |
| GET | `/api/revenue/price-recommendations` | Suggested price changes |

### Voice Copilot (`/api/voice/*`)

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| POST | `/api/voice/process-turn` | multipart: `audio` (file), `session_id`, `language?`, `table_id?` | Full voice turn → transcript + cart + TTS audio |
| POST | `/api/voice/add-item` | JSON: `session_id`, `product_id`, `item_name`, `quantity?` | Add item via upsell chip |
| POST | `/api/voice/confirm-order` | JSON: `session_id` | Confirm order → write to DB + KOT |
| GET | `/api/voice/session/:session_id` | — | Current session state |

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/menu/items` | All menu items with variants |
| GET | `/api/orders/today` | Today's orders summary |
| GET | `/api/kot/pending` | Pending KOTs for kitchen display |
| GET | `/api/inventory/alerts` | Low-stock warnings |
| GET | `/api/customers/churn-risk` | High churn-risk customers |
| POST | `/api/auth/login` | Login → JWT token |
| POST | `/api/auth/register` | Register a new user |

---

## 8. Voice Ordering Flow

```
Customer speaks into browser mic
       ↓
VoiceOrder.jsx   — MediaRecorder captures WebM/Opus
       ↓
POST /api/voice/process-turn  (multipart audio)
       ↓
Node.js backend  — forwards to ai_service_gemini
       ↓
POST :8002/test/voice-chat
       ↓
Gemini Live API  — STT + NLU + TTS in one session
       ↓
Response: { transcript, intent, cart, audio_base64, upsell_chips, … }
       ↓
Frontend plays audio, updates cart UI, shows upsell chips
       ↓
Confirm button → POST /api/voice/confirm-order
       ↓
ai_service writes orders + order_items + KOT to PostgreSQL
```

---

## 9. Environment Files Summary

| File | Purpose |
|------|---------|
| `backend/.env` | DB credentials, JWT secret, NODE_PORT, AI_SERVICE_URL |
| `frontend/Frontend_mined/.env` | VITE_API_URL pointing to backend |
| `ai_service_gemini/.env` | DATABASE_URL, GEMINI_API_KEY, model names |

---

## 10. Troubleshooting

| Problem | Fix |
|---------|-----|
| `ECONNREFUSED :5432` | PostgreSQL service is not running. Start it via Services or `pg_ctl start` |
| `relation "menu_items" does not exist` | Run `schema.sql` then `final_static_seed.sql` in pgAdmin |
| `ECONNREFUSED :8002` | AI service not started. Run `uvicorn main:app --port 8002` in `ai_service_gemini/` |
| `JWT secret missing` | Set `JWT_SECRET` in `backend/.env` |
| Microphone permission denied | Browser must be served over HTTPS or `localhost` for mic access |
| `GEMINI_API_KEY` empty | Add your key to `ai_service_gemini/.env` |
| Frontend shows stale data | Verify `VITE_API_URL` in `frontend/Frontend_mined/.env` points to `:3000` |
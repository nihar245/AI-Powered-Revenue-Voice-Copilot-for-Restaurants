# 🍽️ AI-Powered Revenue & Voice Copilot for Restaurants

> An intelligent restaurant management platform combining AI-driven revenue optimization with multilingual voice ordering capabilities

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.2-61DAFB?style=flat&logo=react)](https://reactjs.org/)
[![Node.js](https://img.shields.io/badge/Node.js-Express-339933?style=flat&logo=node.js)](https://nodejs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=flat&logo=postgresql)](https://www.postgresql.org/)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Database Schema](#-database-schema)
- [Installation](#-installation)
- [Running the Application](#-running-the-application)
- [API Documentation](#-api-documentation)
- [AI/ML Models](#-aiml-models)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Overview

**PetPooja AI Copilot** is a comprehensive restaurant management solution that leverages artificial intelligence to optimize revenue and streamline operations. Built for the modern restaurant ecosystem, it provides two powerful modules:

### **Module 1: Revenue Intelligence Engine 📊**
Analyzes POS data in real-time to deliver actionable insights on:
- Menu optimization and pricing strategies
- Demand forecasting and inventory management
- Customer churn prediction and segmentation
- Contribution margin analysis
- Anomaly detection in sales patterns

### **Module 2: AI Voice Ordering Copilot 🎤**
A multilingual voice assistant that:
- Accepts voice orders from customers (Hindi + English)
- Understands natural language intent
- Handles menu item mapping and customizations
- Suggests intelligent upsells
- Generates structured Kitchen Order Tickets (KOT)

---

## ✨ Key Features

### Revenue Intelligence
- **Contribution Margin Analysis**: Real-time profitability tracking per menu item
- **Menu Engineering**: BCG matrix classification (Stars, Puzzles, Plowhorses, Dogs)
- **Smart Combo Recommendations**: Association rule mining for meal bundles
- **Demand Forecasting**: 7-day ahead prediction using LightGBM
- **Price Optimization**: Data-driven pricing suggestions based on demand elasticity
- **Anomaly Detection**: Isolation Forest for detecting unusual sales patterns
- **Customer Churn Prediction**: XGBoost-based early warning system
- **Inventory Alerts**: Low stock warnings with performance signals
- **AOV Intelligence**: Average Order Value analysis by channel, time, and payment method

### Voice Ordering
- **Speech-to-Text**: OpenAI Whisper for accurate multilingual transcription
- **Intent Classification**: DistilBERT-based NLU for understanding customer intent
- **Semantic Menu Matching**: Sentence Transformers + FAISS for fuzzy item matching
- **Dialogue Management**: Context-aware conversation flow
- **Text-to-Speech**: gTTS for natural voice responses
- **Order Validation**: Real-time menu availability and price calculation
- **KOT Generation**: Automatic kitchen order creation with priority handling
- **Multi-variant Support**: Handles Half/Full portions, addons, and customizations

### Additional Features
- **Real-time Dashboard**: KPIs, revenue trends, and top-selling items
- **Kitchen Display System**: Live KOT tracking with status updates
- **Order Management**: Multi-channel order handling (Dine-in, Takeaway, Zomato, Swiggy)
- **Customer Segmentation**: VIP, Regular, Occasional, Lost, New
- **Inventory Management**: Ingredient tracking with recipe BOM
- **Reports & Analytics**: Comprehensive business intelligence reports

---

## 🏗️ Architecture

```
┌─────────────────┐         ┌─────────────────┐         ┌──────────────────┐
│                 │         │                 │         │                  │
│  React Frontend │◄────────┤  Node.js/Express│◄────────┤   PostgreSQL     │
│  (Port 5173)    │         │   Backend       │         │   Database       │
│                 │         │  (Port 3000)    │         │  (Port 5432)     │
└─────────────────┘         └────────┬────────┘         └──────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    │                                  │
            ┌───────▼────────┐              ┌─────────▼─────────┐
            │  ML Service    │              │  AI Voice Service │
            │  (FastAPI)     │              │  (FastAPI)        │
            │  Port 8000     │              │  Port 8001        │
            │                │              │                   │
            │ • Demand       │              │ • Whisper STT     │
            │ • Churn        │              │ • Intent NLU      │
            │ • Anomaly      │              │ • LLM (Qwen)      │
            │ • Menu Opt     │              │ • gTTS/Piper TTS  │
            └────────────────┘              └───────────────────┘
```

---

## 🛠️ Tech Stack

### Frontend
- **Framework**: React 18.2 with Vite 5
- **Styling**: Tailwind CSS 3.4
- **UI Components**: Lucide React icons
- **Charts**: Recharts 2.12
- **Routing**: React Router DOM 6.22

### Backend
- **Runtime**: Node.js (Express 4.21)
- **Database Client**: node-postgres (pg)
- **Authentication**: JWT + bcryptjs
- **Security**: Helmet, CORS, Rate Limiting
- **File Upload**: Multer
- **HTTP Client**: Axios

### ML Service
- **Framework**: FastAPI 0.100+ with Uvicorn
- **ML Libraries**: 
  - scikit-learn (Isolation Forest)
  - LightGBM (Demand Forecasting)
  - XGBoost (Churn Prediction)
  - mlxtend (Association Rules)
- **Database**: SQLAlchemy + psycopg2

### AI Voice Service
- **Framework**: FastAPI 0.115+ with Uvicorn
- **STT**: faster-whisper 1.1 (OpenAI Whisper optimized)
- **NLU**: sentence-transformers 3.3 (Embeddings + FAISS)
- **LLM**: Ollama (Qwen/Phi4-mini via llama-cpp)
- **TTS**: gTTS 2.5 + Piper (optional)
- **Language**: Python 3.10+
- **ML Framework**: PyTorch 2.5 (CPU-only)

### Database
- **RDBMS**: PostgreSQL 16
- **Tables**: 18 tables (normalized schema)
- **Indexes**: 13 performance indexes

---

## 📁 Project Structure

```
AI-Powered-Revenue-Voice-Copilot-for-Restaurants/
│
├── backend/                          # Node.js Express API (Port 3000)
│   ├── src/
│   │   ├── app.js                    # Main Express app
│   │   ├── config/
│   │   │   └── db.js                 # PostgreSQL connection pool
│   │   ├── controllers/              # Business logic
│   │   │   ├── authController.js
│   │   │   ├── dashboardController.js
│   │   │   ├── revenueController.js
│   │   │   ├── analyticsController.js
│   │   │   ├── voiceController.js
│   │   │   ├── orderController.js
│   │   │   ├── kotController.js
│   │   │   ├── customerController.js
│   │   │   ├── inventoryController.js
│   │   │   └── productsController.js
│   │   ├── routes/                   # API routes
│   │   ├── services/
│   │   │   └── mlService.js          # ML service client
│   │   └── middleware/
│   │       └── auth.js               # JWT authentication
│   ├── migrations/                   # SQL migrations
│   └── package.json
│
├── frontend/Frontend_mined/          # React App (Port 5173)
│   ├── src/
│   │   ├── App.jsx                   # Main router
│   │   ├── config.js                 # API client
│   │   ├── components/
│   │   │   ├── AppLayout.jsx
│   │   │   └── Navbar.jsx
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Orders.jsx
│   │   │   ├── VoiceOrder.jsx
│   │   │   ├── Revenue.jsx
│   │   │   ├── Analytics.jsx
│   │   │   ├── Inventory.jsx
│   │   │   ├── Customers.jsx
│   │   │   ├── KitchenDisplay.jsx
│   │   │   └── Products.jsx
│   │   └── context/
│   │       └── POSContext.jsx
│   ├── tests/                        # Playwright tests
│   └── package.json
│
├── ml_service/                       # Python ML Service (Port 8000)
│   ├── main.py                       # FastAPI app
│   ├── train.py                      # Model training
│   ├── models/                       # Trained models (.pkl)
│   └── requirements.txt
│
├── ai_service/                       # AI Voice Service (Port 8001)
│   ├── main.py                       # FastAPI app
│   ├── config.py
│   ├── routers/
│   │   ├── voice.py
│   │   ├── health.py
│   │   └── test_pipeline.py
│   ├── services/
│   │   ├── stt/                      # Speech-to-text
│   │   ├── nlu/                      # Intent detection
│   │   ├── llm/                      # LLM integration
│   │   ├── tts/                      # Text-to-speech
│   │   ├── dialogue/
│   │   ├── menu/
│   │   └── database/
│   ├── models/
│   │   └── schemas.py
│   ├── static/
│   │   └── voicelab.html
│   └── requirements.txt
│
├── ai_service_cloud/                 # Cloud API variant
├── ai_service_gemini/                # Gemini Live API variant
│
├── models/                           # Jupyter notebooks
│   ├── combo_intelligence.ipynb
│   ├── demand_forecast.ipynb
│   ├── churn_prediction.ipynb
│   ├── anomaly_detection.ipynb
│   └── menu_optimization.ipynb
│
├── schema.sql                        # DB schema (18 tables)
├── final_static_seed.sql            # Static seed data
├── generate_data_final (1).py       # Synthetic data generator
├── context.md
├── plan.md
├── features_1.md
└── VOICE_INTEGRATION_CONTEXT.md
```

---

## 🗄️ Database Schema

### Core Tables (18 total)

#### Static Tables (Menu & Configuration)
- **restaurants**: Restaurant profile and settings
- **menu_categories**: Starter, Main, Bread, Rice, Drink, Dessert
- **menu_items**: 30 items with tags (bestseller, spicy, chef_special)
- **menu_variants**: Half/Full, Small/Large variants (52 total)
- **menu_addons**: Extra cheese, extra gravy, etc.
- **menu_combos**: 8 meal deals and combo offers
- **combo_items**: Items included in each combo
- **ingredients**: 25 raw ingredients with stock levels
- **recipes**: Bill of Materials (ingredient quantities per item)
- **offers**: 10 promotional offers

#### Transactional Tables
- **customers**: 500 customers with segments and churn risk
- **orders**: ~30,000 orders across 1 year
- **order_items**: ~75,000 line items with revenue and food cost
- **order_addons**: ~15,000 addon selections
- **order_payments**: ~32,000 payment records (Cash/UPI/Card/Wallet)
- **kot**: Kitchen Order Tickets
- **kot_items**: Line items for each KOT
- **offer_redemptions**: ~3,000 offer usages
- **feedback**: ~9,000 customer ratings with sentiment
- **inventory_log**: Ingredient consumption, restock, wastage logs

### Key Relationships
```
orders → customers
orders → order_items → menu_items → menu_variants
order_items → order_addons → menu_addons
orders → kot → kot_items
orders → order_payments
orders → offer_redemptions → offers
orders → feedback
order_items → recipes → ingredients → inventory_log
```

---

## 🚀 Installation

### Prerequisites
- **Node.js** 18+ and npm
- **Python** 3.10+
- **PostgreSQL** 16+
- **Git**

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/AI-Powered-Revenue-Voice-Copilot-for-Restaurants.git
cd AI-Powered-Revenue-Voice-Copilot-for-Restaurants
```

### 2. Database Setup

#### Create Database
```bash
psql -U postgres
CREATE DATABASE postgres;
\c postgres
```

#### Run Schema
```bash
psql -U postgres -d postgres -f schema.sql
```

#### Seed Static Data
```bash
psql -U postgres -d postgres -f final_static_seed.sql
```

#### Generate Synthetic Data (Optional)
```bash
python "generate_data_final (1).py"
```

### 3. Backend Setup

```bash
cd backend
npm install

# Create .env file
cat > .env << EOF
DB_HOST=localhost
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=postgres
JWT_SECRET=your_secret_key_here
NODE_PORT=3000
ML_SERVICE_URL=http://localhost:8000
EOF

npm start
```

### 4. Frontend Setup

```bash
cd frontend/Frontend_mined
npm install
npm run dev
```

### 5. ML Service Setup

```bash
cd ml_service
pip install -r requirements.txt
python main.py
```

### 6. AI Voice Service Setup

```bash
cd ai_service
pip install -r requirements.txt

# Install Ollama (if using local LLM)
# Visit: https://ollama.ai/download
ollama pull qwen2.5:7b-instruct

python main.py
```

---

## 🏃 Running the Application

### Start All Services

Open 4 terminal windows:

#### Terminal 1: Backend
```bash
cd backend
npm start
# Running on http://localhost:3000
```

#### Terminal 2: Frontend
```bash
cd frontend/Frontend_mined
npm run dev
# Running on http://localhost:5173
```

#### Terminal 3: ML Service
```bash
cd ml_service
python main.py
# Running on http://localhost:8000
```

#### Terminal 4: AI Voice Service
```bash
cd ai_service
python main.py
# Running on http://localhost:8001
```

### Access the Application
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:3000/api
- **ML Service**: http://localhost:8000/docs
- **Voice Service**: http://localhost:8001/docs

---

## 📡 API Documentation

### Module 1: Revenue Intelligence

#### Contribution Margin
```http
GET /api/revenue/contribution-margin
```
Returns item-level profitability analysis with margin percentages.

#### Menu Engineering
```http
GET /api/revenue/menu-engineering
```
BCG matrix classification: Stars, Puzzles, Plowhorses, Dogs.

#### Top Combos
```http
GET /api/revenue/top-combos
```
Association rule mining for frequently ordered item combinations.

#### Demand Forecast
```http
GET /api/revenue/demand-forecast?days=7
```
LightGBM predictions for next N days per item.

#### Price Recommendations
```http
GET /api/revenue/price-recommendations
```
Data-driven pricing suggestions based on demand elasticity.

#### Anomaly Detection
```http
GET /api/revenue/anomalies
```
Isolation Forest detection of unusual sales patterns.

#### Churn Prediction
```http
GET /api/customers/churn-risk
```
XGBoost predictions for customers at risk of churning.

### Module 2: Voice Ordering

#### Transcribe Audio
```http
POST /api/voice/transcribe
Content-Type: multipart/form-data

audio: <file>
```

#### Detect Intent
```http
POST /api/voice/intent
Content-Type: application/json

{
  "text": "मुझे एक बटर चिकन चाहिए"
}
```

#### Process Voice Turn
```http
POST /api/voice/process-turn
Content-Type: application/json

{
  "text": "मुझे एक बटर चिकन चाहिए",
  "session_id": "abc123"
}
```

#### Confirm Order
```http
POST /api/voice/confirm-order
Content-Type: application/json

{
  "session_id": "abc123",
  "table_number": 5
}
```

### General Endpoints

```http
GET  /api/menu/items
POST /api/orders
GET  /api/orders/today
GET  /api/kot/pending
PUT  /api/kot/:id/status
```

---

## 🤖 AI/ML Models

### 1. Demand Forecasting (LightGBM)
- **Input**: Day, hour, month, lag features, festival flags
- **Output**: Predicted quantity per item
- **Retrain**: Monthly on new sales data

### 2. Anomaly Detection (Isolation Forest)
- **Input**: Daily revenue, order count, AOV
- **Output**: Anomaly score (0-1)
- **Threshold**: 95th percentile for alerts

### 3. Churn Prediction (XGBoost)
- **Input**: Days since visit, visit frequency, lifetime spend
- **Output**: Churn probability (0-1)
- **Threshold**: 0.7 for high-risk flagging

### 4. Intent Classification (DistilBERT)
- **Input**: Voice-transcribed text (Hindi+English)
- **Output**: Intent label (greeting, order, modify, confirm, cancel)
- **Languages**: Supports code-mixed Hindi-English

### 5. Semantic Menu Matching (Sentence Transformers + FAISS)
- **Input**: Spoken item name (e.g., "butter chicken")
- **Output**: Top 3 matched menu items with similarity scores
- **Model**: all-MiniLM-L6-v2 embeddings

### 6. Menu Optimization (Association Rules)
- **Algorithm**: FP-Growth with Apriori
- **Input**: Transaction history
- **Output**: Frequent itemsets and combo suggestions

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Commit your changes**
   ```bash
   git commit -m 'Add amazing feature'
   ```
4. **Push to the branch**
   ```bash
   git push origin feature/amazing-feature
   ```
5. **Open a Pull Request**

---

## 📄 License

This project is licensed under the **MIT License**.

---

## 🙏 Acknowledgments

- **PetPooja** for the problem statement and inspiration
- **OpenAI** for Whisper speech recognition
- **Hugging Face** for transformer models
- **LightGBM** and **XGBoost** teams for ML frameworks
- **FastAPI** and **React** communities

---

## 🔮 Future Roadmap

- [ ] Mobile app (React Native)
- [ ] Multi-restaurant support (chain management)
- [ ] Real-time inventory sync with suppliers
- [ ] Advanced churn intervention campaigns
- [ ] WhatsApp ordering integration
- [ ] Dynamic pricing based on occupancy
- [ ] Customer sentiment analysis from reviews
- [ ] Multi-language support (Tamil, Bengali, Telugu)
- [ ] Integration with food delivery platforms
- [ ] Predictive maintenance for kitchen equipment

---

<div align="center">
  <strong>Built with ❤️ for the Restaurant Industry</strong>
  <br><br>
  <a href="#-table-of-contents">⬆️ Back to Top</a>
</div>


# AI Restaurant Copilot 🍽️🤖

A modern, SaaS-style frontend application built for restaurant owners to maximize margins and automate phone orders using AI-powered voice taking, Point of Sale (POS) data intelligence, and smart recommendations.

## ✨ Features

- **Voice Ordering Automation:** Take calls smoothly and map them automatically to your POS.
- **Revenue Intelligence:** Granular insights into menu profitability and hourly sales trends.
- **Smart Recommendations:** Uses Apriori combo detection for suggesting high-value upsells.
- **Beautiful UI:** A dark-mode, futuristic glassmorphism interface inspired by modern SaaS platforms.
- **Scroll-Linked Animation:** Includes an optimized, preloaded high-fidelity frame-by-frame hero animation triggered via scrolling.

## 🛠️ Tech Stack

- **Framework:** [React 18](https://react.dev/)
- **Build Tool:** [Vite](https://vitejs.dev/)
- **Styling:** [Tailwind CSS](https://tailwindcss.com/)
- **Components:** Simulated [Shadcn UI](https://ui.shadcn.com/) standard elements.
- **Icons:** [Lucide React](https://lucide.dev/)
- **Routing:** [React Router v6+](https://reactrouter.com/)

## 🚀 Getting Started

### Prerequisites

Make sure you have [Node.js](https://nodejs.org/) (Version 18+ recommended) installed.

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/parth-to-syntax/Frontend_mined.git
   ```

2. Navigate to the project directory:
   ```bash
   cd Frontend_mined
   ```

3. Install all dependencies:
   ```bash
   npm install
   ```

4. Start the development server:
   ```bash
   npm run dev
   ```

Open your browser and visit `http://localhost:5173` to view the application in action.

## 📂 Project Structure

```bash
├── public/                 # Static public assets
├── src/
│   ├── assets/             # Images, frame sequences, and raw media
│   ├── components/         # Reusable UI components
│   ├── data/               # Mock data for analytics & dashboard
│   ├── pages/              # Application views (Landing, Dashboard, Login, etc.)
│   ├── index.css           # Global Tailwind & root CSS imports
│   ├── App.jsx             # Main Router structure
│   └── main.jsx            # Application entry
├── tailwind.config.js      # Tailwind customization config
├── vite.config.js          # Vite configuration
└── package.json            # Scripts & Dependency management
```

## 📜 Available Scripts

- **`npm run dev`**: Spawns the Vite local development server.
- **`npm run build`**: Bundles the application for production deployment into the `dist/` folder.
- **`npm run preview`**: Boots a local HTTP server to preview your production bundle locally.
- **`npm run test`**: Runs the Playwright E2E testing suite.

## 📝 License

© 2026 AI Restaurant Copilot.

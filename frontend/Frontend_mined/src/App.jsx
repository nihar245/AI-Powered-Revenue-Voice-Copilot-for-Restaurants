import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Signup from './pages/Signup'
import AppLayout from './components/AppLayout'
import Dashboard from './pages/Dashboard'
import Orders from './pages/Orders'
import VoiceOrder from './pages/VoiceOrder'
import Analytics from './pages/Analytics'
import Revenue from './pages/Revenue'
import Inventory from './pages/Inventory'
import Customers from './pages/Customers'
import KitchenDisplay from './pages/KitchenDisplay'
import Products from './pages/Products'
import Reports from './pages/Reports'

import { POSProvider } from './context/POSContext'

function App() {
  return (
    <POSProvider>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />

          {/* App routes wrapped in layout */}
          <Route path="/dashboard" element={<AppLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="orders" element={<Orders />} />
            <Route path="products" element={<Products />} />
            <Route path="voice" element={<VoiceOrder />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="revenue" element={<Revenue />} />
            <Route path="inventory" element={<Inventory />} />
            <Route path="customers" element={<Customers />} />
            <Route path="kitchen" element={<KitchenDisplay />} />
            <Route path="reports" element={<Reports />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </POSProvider>
  )
}

export default App

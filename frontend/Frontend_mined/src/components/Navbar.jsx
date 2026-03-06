import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  ClipboardList,
  Mic,
  BarChart3,
  LogOut,
  Zap,
  Menu,
  X,
  TrendingUp,
  Users,
  ChefHat,
  UtensilsCrossed,
  FileText,
} from 'lucide-react'
import { useState } from 'react'

const navItems = [
  { label: 'Dashboard',      icon: LayoutDashboard, path: '/dashboard' },
  { label: 'Orders',         icon: ClipboardList,   path: '/dashboard/orders' },
  { label: 'Products',       icon: UtensilsCrossed, path: '/dashboard/products' },
  { label: 'Analytics',      icon: BarChart3,       path: '/dashboard/analytics' },
  { label: 'Revenue Intel',  icon: TrendingUp,      path: '/dashboard/revenue' },
  { label: 'Reports',        icon: FileText,        path: '/dashboard/reports' },
  { label: 'Customers',      icon: Users,           path: '/dashboard/customers' },
  { label: 'Kitchen Display', icon: ChefHat,         path: '/dashboard/kitchen' },
  { label: 'Voice Ordering', icon: Mic,             path: '/dashboard/voice' },
]

export default function Navbar() {
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)

  const handleLogout = () => {
    navigate('/')
  }

  return (
    <>
      {/* ── Desktop Sidebar ── */}
      <aside className="hidden lg:flex flex-col w-64 min-h-screen bg-white border-r border-surface-200 px-4 py-6 shrink-0 shadow-card">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-2 mb-10">
          <div className="w-8 h-8 rounded-lg bg-primary-600 flex items-center justify-center shadow-red-btn">
            <Zap size={16} className="text-white" />
          </div>
          <span className="font-bold text-sm leading-tight text-surface-900">
            AI Restaurant<br />
            <span className="text-primary-600 font-semibold">Copilot</span>
          </span>
        </div>

        {/* Nav links */}
        <nav className="flex-1 space-y-1">
          {navItems.map(({ label, icon: Icon, path }) => (
            <NavLink
              key={path}
              to={path}
              end={path === '/dashboard'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200
                ${isActive
                  ? 'bg-primary-50 text-primary-600 border border-primary-200 font-semibold'
                  : 'text-surface-500 hover:text-surface-900 hover:bg-surface-100'
                }`
              }
            >
              <Icon size={16} className="shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Logout */}
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                     text-surface-400 hover:text-primary-600 hover:bg-primary-50 transition-all duration-200 mt-4"
        >
          <LogOut size={16} />
          Logout
        </button>
      </aside>

      {/* ── Mobile Top Bar ── */}
      <header className="lg:hidden flex items-center justify-between px-4 py-3 bg-white border-b border-surface-200 w-full shadow-card">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-primary-600 flex items-center justify-center">
            <Zap size={13} className="text-white" />
          </div>
          <span className="font-semibold text-sm text-surface-900">AI Copilot</span>
        </div>
        <button
          onClick={() => setMobileOpen(v => !v)}
          className="text-surface-400 hover:text-surface-700 p-1"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </header>

      {/* ── Mobile Dropdown ── */}
      {mobileOpen && (
        <div className="lg:hidden absolute top-[52px] left-0 right-0 z-50 bg-white border-b border-surface-200 px-4 py-3 space-y-1 animate-fade-in shadow-card-md">
          {navItems.map(({ label, icon: Icon, path }) => (
            <NavLink
              key={path}
              to={path}
              end={path === '/dashboard'}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200
                ${isActive
                  ? 'bg-primary-50 text-primary-600 border border-primary-200 font-semibold'
                  : 'text-surface-500 hover:text-surface-900 hover:bg-surface-100'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
          <button
            onClick={() => { setMobileOpen(false); handleLogout() }}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium
                       text-surface-400 hover:text-primary-600 hover:bg-primary-50 transition-all duration-200"
          >
            <LogOut size={16} />
            Logout
          </button>
        </div>
      )}
    </>
  )
}

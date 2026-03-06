import { useState, useEffect } from 'react'
import {
  ShoppingBag,
  TrendingUp,
  IndianRupee,
  Star,
  ArrowUpRight,
  Zap,
} from 'lucide-react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts'
import { usePOS } from '../context/POSContext'
import { apiFetch, DATA_DATE } from '../config'

export default function Dashboard() {
  const { dashboardKPIs } = usePOS()
  const [hourlyOrders, setHourlyOrders] = useState([])
  const [topItems, setTopItems] = useState([])
  const [weeklyRevenue, setWeeklyRevenue] = useState([])

  useEffect(() => {
    const qd = DATA_DATE ? `?date=${DATA_DATE}` : ''
    Promise.all([
      apiFetch(`/dashboard/hourly-orders${qd}`).catch(() => []),
      apiFetch(`/dashboard/top-items${qd}`).catch(() => []),
      apiFetch(`/dashboard/weekly-revenue${qd}`).catch(() => []),
    ]).then(([h, t, w]) => {
      setHourlyOrders(h)
      setTopItems(t)
      setWeeklyRevenue(w)
    })
  }, [])

  const fmtChange = (v) => {
    if (v == null) return { text: 'N/A', cls: 'text-surface-400 bg-surface-50 border-surface-200' }
    const sign = v >= 0 ? '+' : ''
    return v >= 0
      ? { text: `${sign}${v}%`, cls: 'text-emerald-600 bg-emerald-50 border-emerald-200' }
      : { text: `${v}%`, cls: 'text-red-600 bg-red-50 border-red-200' }
  }

  const ch = dashboardKPIs.changes || {}
  const kpis = [
    {
      label: 'Total Orders',
      value: dashboardKPIs.totalOrdersToday,
      icon: ShoppingBag,
      color: 'text-primary-600',
      bg: 'bg-primary-50',
      change: fmtChange(ch.orders).text,
      changeColor: fmtChange(ch.orders).cls,
    },
    {
      label: 'Total Revenue',
      value: `₹${dashboardKPIs.totalRevenue.toLocaleString()}`,
      icon: IndianRupee,
      color: 'text-emerald-600',
      bg: 'bg-emerald-50',
      change: fmtChange(ch.revenue).text,
      changeColor: fmtChange(ch.revenue).cls,
    },
    {
      label: 'Avg Order Value',
      value: `₹${dashboardKPIs.avgOrderValue}`,
      icon: TrendingUp,
      color: 'text-violet-600',
      bg: 'bg-violet-50',
      change: fmtChange(ch.aov).text,
      changeColor: fmtChange(ch.aov).cls,
    },
    {
      label: 'Top Selling Item',
      value: dashboardKPIs.topSellingItem,
      icon: Star,
      color: 'text-amber-600',
      bg: 'bg-amber-50',
      change: 'trending',
      changeColor: 'text-amber-600 bg-amber-50 border-amber-200',
    },
  ]

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null
    return (
      <div className="card px-3 py-2 text-xs shadow-card-md">
        <p className="text-surface-400 mb-1">{label}</p>
        {payload.map((p, i) => (
          <p key={i} style={{ color: p.color }} className="font-semibold">
            {p.name}: {typeof p.value === 'number' && p.name?.toLowerCase().includes('revenue') ? `₹${p.value.toLocaleString()}` : p.value}
          </p>
        ))}
      </div>
    )
  }

  return (
    <div className="p-6 space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900">Dashboard</h1>
          <p className="text-surface-400 text-sm mt-0.5">
            Today · {new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
          </p>
        </div>
        <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-700 px-3 py-1.5 rounded-full text-xs font-semibold">
          <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
          Live
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {kpis.map(({ label, value, icon: Icon, color, bg, changeColor, change }) => (
          <div key={label} className="card-hover p-5">
            <div className="flex items-start justify-between mb-4">
              <div className={`w-9 h-9 ${bg} rounded-xl flex items-center justify-center`}>
                <Icon size={17} className={color} />
              </div>
              <span className={`text-xs border px-2 py-0.5 rounded-full flex items-center gap-1 ${changeColor}`}>
                <ArrowUpRight size={10} />{change}
              </span>
            </div>
            <p className="text-surface-400 text-xs font-medium mb-1">{label}</p>
            <p className={`text-xl font-bold ${color} truncate`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid xl:grid-cols-5 gap-6">
        {/* Orders over time */}
        <div className="xl:col-span-3 card p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="font-semibold text-surface-900">Orders Over Time</h2>
              <p className="text-surface-400 text-xs mt-0.5">Hourly breakdown · today</p>
            </div>
            <div className="flex items-center gap-1 text-primary-600 text-xs font-medium">
              <Zap size={12} /> AI monitored
            </div>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={hourlyOrders} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}>
              <defs>
                <linearGradient id="ordersGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#e11d48" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#e11d48" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="time" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area type="monotone" dataKey="orders" name="Orders" stroke="#e11d48" strokeWidth={2} fill="url(#ordersGrad)" dot={false} activeDot={{ r: 4, fill: '#e11d48' }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Top selling items */}
        <div className="xl:col-span-2 card p-6">
          <div className="mb-6">
            <h2 className="font-semibold text-surface-900">Top Selling Items</h2>
            <p className="text-surface-400 text-xs mt-0.5">By order count · today</p>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={topItems} layout="vertical" margin={{ top: 0, right: 5, bottom: 0, left: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
              <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="name" tick={{ fill: '#64748b', fontSize: 11 }} tickLine={false} axisLine={false} width={80} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="orders" name="Orders" fill="#e11d48" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Weekly Revenue */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="font-semibold text-surface-900">Weekly Revenue</h2>
            <p className="text-surface-400 text-xs mt-0.5">Last 7 days</p>
          </div>
          <span className="text-emerald-600 text-sm font-semibold">
            ₹{weeklyRevenue.reduce((a, b) => a + b.revenue, 0).toLocaleString()} total
          </span>
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={weeklyRevenue} margin={{ top: 5, right: 5, bottom: 0, left: -10 }}>
            <defs>
              <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#f43f5e" stopOpacity={0.9} />
                <stop offset="100%" stopColor="#be123c" stopOpacity={0.7} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="day" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="revenue" name="Revenue" fill="url(#revGrad)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

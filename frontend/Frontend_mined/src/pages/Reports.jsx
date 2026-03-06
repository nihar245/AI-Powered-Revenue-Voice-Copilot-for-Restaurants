import { useState, useEffect, useRef, useCallback } from 'react'
import {
  AreaChart, Area,
  BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Legend,
} from 'recharts'
import { apiFetch } from '../config'
import {
  TrendingUp, ShoppingBag, IndianRupee, Percent,
  Printer, RefreshCw, Tag, Zap, UtensilsCrossed, CreditCard,
} from 'lucide-react'

// ── Colour palette for charts ─────────────────────────────────────────────────
const COLORS = ['#0ea5e9','#10b981','#8b5cf6','#f59e0b','#e11d48','#06b6d4','#14b8a6','#f97316']

// ── Custom tooltip ─────────────────────────────────────────────────────────────
const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="card px-3 py-2 text-xs shadow-card-md">
      <p className="text-surface-400 font-medium mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }} className="font-semibold">
          {p.name}: {typeof p.value === 'number' && p.name?.toLowerCase().includes('revenue')
            ? `₹${p.value.toLocaleString()}`
            : p.value}
        </p>
      ))}
    </div>
  )
}

// ── Number formatters ───────────────────────────────────────────────────────────
const fmtRupee = v => `₹${Number(v || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`
const fmtNum   = v => Number(v || 0).toLocaleString('en-IN')

// ── Hour label ─────────────────────────────────────────────────────────────────
const fmtHour = h => {
  if (h === 0) return '12 AM'
  if (h < 12)  return `${h} AM`
  if (h === 12) return '12 PM'
  return `${h - 12} PM`
}

export default function Reports() {
  const [period, setPeriod]   = useState('30d')
  const [data,   setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const printRef = useRef(null)

  const fetchData = useCallback(() => {
    setLoading(true)
    apiFetch(`/reports/summary?period=${period}`)
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [period])

  useEffect(() => { fetchData() }, [fetchData])

  const handlePrint = () => window.print()

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full" />
      </div>
    )
  }

  if (!data) {
    return (
      <div className="p-6 text-center text-surface-500">
        Failed to load report data.
      </div>
    )
  }

  const { kpi, daily_trend, category_breakdown, top_items, payment_methods, channels, hourly_pattern, day_of_week } = data

  // Format hourly data to fill all 24 hours
  const fullHourly = Array.from({ length: 24 }, (_, h) => {
    const found = hourly_pattern.find(r => r.hour === h)
    return { hour: fmtHour(h), orders: found?.orders || 0, revenue: found?.revenue || 0 }
  })

  // KPI cards config
  const kpiCards = [
    { label: 'Total Revenue',     value: fmtRupee(kpi.total_revenue),    icon: IndianRupee, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'Total Orders',      value: fmtNum(kpi.completed_orders),   icon: ShoppingBag, color: 'text-primary-600', bg: 'bg-primary-50' },
    { label: 'Avg Order Value',   value: fmtRupee(kpi.avg_order_value),  icon: TrendingUp,  color: 'text-violet-600',  bg: 'bg-violet-50' },
    { label: 'Gross Profit',      value: fmtRupee(kpi.gross_profit),     icon: Percent,     color: 'text-emerald-600', bg: 'bg-emerald-50',
      sub: `${kpi.gross_margin_pct}% margin` },
    { label: 'GST / Tax Collected', value: fmtRupee(kpi.total_tax),      icon: Tag,         color: 'text-amber-600',   bg: 'bg-amber-50' },
    { label: 'Food Cost',         value: fmtRupee(kpi.total_food_cost),  icon: UtensilsCrossed, color: 'text-rose-600', bg: 'bg-rose-50',
      sub: kpi.total_revenue > 0 ? `${(kpi.total_food_cost / kpi.total_revenue * 100).toFixed(1)}% of revenue` : '' },
    { label: 'Upsell Revenue',    value: fmtRupee(kpi.upsell_revenue),   icon: Zap,         color: 'text-indigo-600',  bg: 'bg-indigo-50',
      sub: `${fmtNum(kpi.upsell_items)} upsell items` },
    { label: 'Cancellation Rate', value: `${kpi.cancellation_rate}%`,    icon: RefreshCw,   color: 'text-red-600',     bg: 'bg-red-50',
      sub: `${fmtNum(kpi.cancelled_orders)} cancelled` },
  ]

  const periodLabel = { '7d': 'Last 7 Days', '30d': 'Last 30 Days', '90d': 'Last 90 Days', all: 'All Time' }[period]

  return (
    <>
      {/* ── Print Styles (injected inline, only active during print) ──────── */}
      <style>{`
        @media print {
          body * { visibility: hidden; }
          #reports-print-area, #reports-print-area * { visibility: visible; }
          #reports-print-area { position: absolute; inset: 0; padding: 20px; }
          .no-print { display: none !important; }
          .card { box-shadow: none !important; border: 1px solid #e2e8f0 !important; }
          .recharts-wrapper { page-break-inside: avoid; }
        }
      `}</style>

      <div className="p-6 space-y-6 animate-fade-in" id="reports-print-area" ref={printRef}>

        {/* ── Page Header ──────────────────────────────────────────────────── */}
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-surface-900">Reports</h1>
            <p className="text-surface-400 text-sm mt-0.5">
              Comprehensive business report · {periodLabel}
            </p>
          </div>
          <div className="flex items-center gap-3 no-print">
            {/* Period Selector */}
            <div className="flex gap-1 bg-surface-100 p-1 rounded-lg">
              {[
                { id: '7d',  label: '7 Days' },
                { id: '30d', label: '30 Days' },
                { id: '90d', label: '90 Days' },
                { id: 'all', label: 'All Time' },
              ].map(({ id, label }) => (
                <button key={id} onClick={() => setPeriod(id)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                    period === id
                      ? 'bg-white text-primary-600 shadow-card border border-surface-200'
                      : 'text-surface-500 hover:text-surface-700'
                  }`}>
                  {label}
                </button>
              ))}
            </div>
            {/* Export PDF */}
            <button onClick={handlePrint}
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors">
              <Printer size={15} /> Export PDF
            </button>
          </div>
        </div>

        {/* ── Print date line (only shows on print) ──────────────────────── */}
        <div className="hidden print:block text-xs text-surface-400">
          Generated on {new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })} · Period: {periodLabel}
        </div>

        {/* ── KPI Cards ────────────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {kpiCards.map(({ label, value, icon: Icon, color, bg, sub }) => (
            <div key={label} className="card p-4">
              <div className={`w-9 h-9 ${bg} rounded-lg flex items-center justify-center mb-3`}>
                <Icon size={18} className={color} />
              </div>
              <p className="text-xs text-surface-400 font-medium">{label}</p>
              <p className={`text-xl font-bold mt-0.5 ${color}`}>{value}</p>
              {sub && <p className="text-[10px] text-surface-400 mt-0.5">{sub}</p>}
            </div>
          ))}
        </div>

        {/* ── Revenue Trend ─────────────────────────────────────────────────── */}
        <div className="card p-6">
          <h2 className="font-semibold text-surface-900 mb-1">Revenue Trend</h2>
          <p className="text-surface-400 text-xs mb-5">Daily revenue and order count · {periodLabel}</p>
          {daily_trend.length === 0 ? (
            <p className="text-center text-surface-400 text-sm py-12">No data for this period</p>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={daily_trend} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#0ea5e9" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis yAxisId="rev" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false}
                  tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                <YAxis yAxisId="ord" orientation="right" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltip />} />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                <Area yAxisId="rev" type="monotone" dataKey="revenue" name="Revenue" stroke="#0ea5e9" fill="url(#revGrad)" strokeWidth={2} dot={false} />
                <Area yAxisId="ord" type="monotone" dataKey="orders" name="Orders" stroke="#10b981" fill="none" strokeWidth={2} strokeDasharray="4 2" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* ── Top Items + Category breakdown ───────────────────────────────── */}
        <div className="grid xl:grid-cols-2 gap-6">

          {/* Top 10 Items */}
          <div className="card p-6">
            <h2 className="font-semibold text-surface-900 mb-1">Top 10 Items by Revenue</h2>
            <p className="text-surface-400 text-xs mb-5">Units sold shown alongside revenue</p>
            {top_items.length === 0 ? (
              <p className="text-center text-surface-400 text-sm py-8">No data for this period</p>
            ) : (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart
                  data={top_items}
                  layout="vertical"
                  margin={{ top: 0, right: 10, bottom: 0, left: 90 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                  <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false}
                    tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                  <YAxis type="category" dataKey="name" tick={{ fill: '#475569', fontSize: 10 }} tickLine={false} axisLine={false} width={86} />
                  <Tooltip formatter={(v, n) => n === 'revenue' ? [fmtRupee(v), 'Revenue'] : [fmtNum(v), 'Units']} />
                  <Bar dataKey="revenue" name="revenue" radius={[0, 4, 4, 0]}>
                    {top_items.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Category Breakdown */}
          <div className="card p-6">
            <h2 className="font-semibold text-surface-900 mb-1">Category Breakdown</h2>
            <p className="text-surface-400 text-xs mb-5">Revenue and units per category</p>
            {category_breakdown.length === 0 ? (
              <p className="text-center text-surface-400 text-sm py-8">No data for this period</p>
            ) : (
              <>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={category_breakdown} margin={{ top: 5, right: 5, bottom: 40, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="category" tick={{ fill: '#94a3b8', fontSize: 10 }} angle={-30} textAnchor="end" tickLine={false} axisLine={false} />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                    <Tooltip formatter={(v, n) => n === 'revenue' ? [fmtRupee(v), 'Revenue'] : [fmtNum(v), 'Units']} />
                    <Bar dataKey="revenue" name="revenue" radius={[4, 4, 0, 0]}>
                      {category_breakdown.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div className="mt-3 space-y-1.5">
                  {category_breakdown.map((c, i) => {
                    const pct = kpi.total_revenue > 0 ? ((c.revenue / kpi.total_revenue) * 100).toFixed(1) : 0
                    return (
                      <div key={i} className="flex items-center gap-3 text-xs">
                        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: COLORS[i % COLORS.length] }} />
                        <span className="text-surface-700 font-medium w-32 truncate">{c.category}</span>
                        <div className="flex-1 h-1.5 bg-surface-100 rounded-full overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: COLORS[i % COLORS.length] }} />
                        </div>
                        <span className="text-surface-500 w-10 text-right">{pct}%</span>
                        <span className="text-surface-400 w-8 text-right">{fmtNum(c.units_sold)} u</span>
                      </div>
                    )
                  })}
                </div>
              </>
            )}
          </div>
        </div>

        {/* ── Payment Methods + Channel Split ──────────────────────────────── */}
        <div className="grid xl:grid-cols-2 gap-6">

          {/* Payment Methods */}
          <div className="card p-6">
            <div className="flex items-center gap-2 mb-4">
              <CreditCard size={16} className="text-primary-500" />
              <h2 className="font-semibold text-surface-900">Payment Methods</h2>
            </div>
            {payment_methods.length === 0 ? (
              <p className="text-center text-surface-400 text-sm py-8">No data</p>
            ) : (
              <div className="space-y-3">
                {payment_methods.map((pm, i) => {
                  const pct = kpi.total_revenue > 0 ? ((pm.revenue / kpi.total_revenue) * 100).toFixed(1) : 0
                  return (
                    <div key={i} className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 text-white text-xs font-bold"
                        style={{ background: COLORS[i % COLORS.length] }}>
                        {(pm.payment_method || 'N/A').slice(0, 2).toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-semibold text-surface-700 capitalize">{pm.payment_method || 'Unknown'}</span>
                          <span className="text-xs font-bold text-surface-900">{fmtRupee(pm.revenue)}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-surface-100 rounded-full overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${pct}%`, background: COLORS[i % COLORS.length] }} />
                          </div>
                          <span className="text-[10px] text-surface-400 w-8 text-right">{pct}%</span>
                          <span className="text-[10px] text-surface-400">{fmtNum(pm.orders)} orders</span>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Channel Split */}
          <div className="card p-6">
            <h2 className="font-semibold text-surface-900 mb-4">Order Channels</h2>
            {channels.length === 0 ? (
              <p className="text-center text-surface-400 text-sm py-8">No data</p>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3 mb-4">
                  {channels.map((ch, i) => (
                    <div key={i} className="rounded-xl p-3 border border-surface-100" style={{ background: COLORS[i % COLORS.length] + '12' }}>
                      <p className="text-xs text-surface-500 capitalize font-medium mb-1">{ch.channel || 'Unknown'}</p>
                      <p className="text-lg font-bold text-surface-900">{fmtRupee(ch.revenue)}</p>
                      <p className="text-[10px] text-surface-400 mt-0.5">
                        {fmtNum(ch.orders)} orders · AOV {fmtRupee(ch.avg_order_value)}
                      </p>
                    </div>
                  ))}
                </div>
                <ResponsiveContainer width="100%" height={110}>
                  <BarChart data={channels} margin={{ top: 0, right: 5, bottom: 0, left: -15 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="channel" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                    <Tooltip formatter={v => [fmtRupee(v), 'Revenue']} />
                    <Bar dataKey="revenue" radius={[4, 4, 0, 0]}>
                      {channels.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </>
            )}
          </div>
        </div>

        {/* ── Hourly Pattern ────────────────────────────────────────────────── */}
        <div className="card p-6">
          <h2 className="font-semibold text-surface-900 mb-1">Hourly Order Pattern</h2>
          <p className="text-surface-400 text-xs mb-5">Total orders by hour of day across the period</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={fullHourly} margin={{ top: 5, right: 5, bottom: 0, left: -15 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="hour" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} interval={1} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="orders" name="Orders" radius={[3, 3, 0, 0]}>
                {fullHourly.map((entry, i) => (
                  <Cell key={i} fill={entry.orders > 0 ? '#0ea5e9' : '#e2e8f0'} fillOpacity={entry.orders > 0 ? 0.9 : 0.4} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* ── Day of Week ────────────────────────────────────────────────────── */}
        <div className="card p-6">
          <h2 className="font-semibold text-surface-900 mb-1">Day of Week Performance</h2>
          <p className="text-surface-400 text-xs mb-5">Revenue and order count by weekday</p>
          {day_of_week.length === 0 ? (
            <p className="text-center text-surface-400 text-sm py-8">No data for this period</p>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={day_of_week} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="day" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis yAxisId="rev" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false}
                  tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                <YAxis yAxisId="ord" orientation="right" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} />
                <Tooltip content={<ChartTooltip />} />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                <Bar yAxisId="rev" dataKey="revenue" name="Revenue" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                <Bar yAxisId="ord" dataKey="orders"  name="Orders"  fill="#f59e0b" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* ── Detailed Tables ────────────────────────────────────────────────── */}
        <div className="card p-6 overflow-x-auto">
          <h2 className="font-semibold text-surface-900 mb-4">Top Items — Detail Table</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-200">
                {['#', 'Item', 'Category', 'Units Sold', 'Revenue', 'Food Cost', 'Gross Profit', 'Margin %'].map(h => (
                  <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-4">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {top_items.map((row, i) => {
                const gp     = row.revenue - row.food_cost
                const margin = row.revenue > 0 ? ((gp / row.revenue) * 100).toFixed(1) : 0
                return (
                  <tr key={i} className="hover:bg-surface-50 transition-colors">
                    <td className="py-2.5 pr-4 text-surface-400 font-mono text-xs">{i + 1}</td>
                    <td className="py-2.5 pr-4 text-surface-900 font-semibold text-xs">{row.name}</td>
                    <td className="py-2.5 pr-4 text-surface-500 text-xs">{row.category}</td>
                    <td className="py-2.5 pr-4 text-primary-600 font-bold text-xs">{fmtNum(row.units_sold)}</td>
                    <td className="py-2.5 pr-4 text-surface-900 font-semibold text-xs">{fmtRupee(row.revenue)}</td>
                    <td className="py-2.5 pr-4 text-rose-600 text-xs">{fmtRupee(row.food_cost)}</td>
                    <td className="py-2.5 pr-4 text-emerald-600 font-semibold text-xs">{fmtRupee(gp)}</td>
                    <td className="py-2.5">
                      <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                        margin >= 50 ? 'text-emerald-700 bg-emerald-50' :
                        margin >= 30 ? 'text-amber-700 bg-amber-50' : 'text-red-700 bg-red-50'
                      }`}>{margin}%</span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* ── Footer (print only) ────────────────────────────────────────────── */}
        <div className="hidden print:block text-[10px] text-surface-400 text-center border-t pt-4">
          Petpooja Reports · Confidential · Generated {new Date().toLocaleString()}
        </div>

      </div>
    </>
  )
}

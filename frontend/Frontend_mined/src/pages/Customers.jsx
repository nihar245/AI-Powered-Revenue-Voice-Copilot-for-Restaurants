import { useState, useEffect, useRef } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { apiFetch } from '../config'
import { Users, AlertCircle, TrendingDown, Star, X, Search, Plus, ChevronRight, RefreshCw } from 'lucide-react'

const segmentColors = {
  VIP: '#8b5cf6',
  Regular: '#10b981',
  Occasional: '#f59e0b',
  Lost: '#e11d48',
  New: '#3b82f6',
}

const riskColor = (score) => {
  if (score >= 0.7) return 'text-red-600'
  if (score >= 0.4) return 'text-amber-600'
  return 'text-emerald-600'
}

const riskBar = (score) => {
  if (score >= 0.7) return 'bg-red-500'
  if (score >= 0.4) return 'bg-amber-400'
  return 'bg-emerald-500'
}

const PERIODS = [
  { id: 'all', label: 'All Time' },
  { id: '90d', label: '90 Days' },
  { id: '30d', label: '30 Days' },
  { id: '7d', label: '7 Days' },
]

// ── Add Customer Modal ──────────────────────────────────────────────────
function AddCustomerModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ phone: '', name: '', email: '', dob: '', is_veg: false, is_jain: false })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.phone.trim()) { setError('Phone is required'); return }
    setLoading(true); setError(null)
    try {
      const res = await apiFetch('/customers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      onCreated(res)
      onClose()
    } catch (err) {
      setError(err?.message || 'Failed to create customer')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-fade-in">
      <div className="bg-white w-full max-w-md rounded-2xl shadow-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-surface-200 flex items-center justify-between bg-zinc-50">
          <h2 className="text-base font-bold text-zinc-900">Add New Customer</h2>
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600 transition-colors p-1"><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>}

          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="block text-xs font-semibold text-surface-500 uppercase tracking-widest mb-1">Phone *</label>
              <input type="tel" value={form.phone} onChange={e => set('phone', e.target.value)}
                placeholder="+91 98765 43210"
                className="w-full bg-surface-50 border border-surface-200 px-3 py-2 rounded-lg text-sm focus:ring-1 focus:ring-primary-500 outline-none" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-surface-500 uppercase tracking-widest mb-1">Name</label>
              <input type="text" value={form.name} onChange={e => set('name', e.target.value)}
                placeholder="Full name"
                className="w-full bg-surface-50 border border-surface-200 px-3 py-2 rounded-lg text-sm focus:ring-1 focus:ring-primary-500 outline-none" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-surface-500 uppercase tracking-widest mb-1">Email</label>
              <input type="email" value={form.email} onChange={e => set('email', e.target.value)}
                placeholder="email@example.com"
                className="w-full bg-surface-50 border border-surface-200 px-3 py-2 rounded-lg text-sm focus:ring-1 focus:ring-primary-500 outline-none" />
            </div>
            <div>
              <label className="block text-xs font-semibold text-surface-500 uppercase tracking-widest mb-1">Date of Birth</label>
              <input type="date" value={form.dob} onChange={e => set('dob', e.target.value)}
                className="w-full bg-surface-50 border border-surface-200 px-3 py-2 rounded-lg text-sm focus:ring-1 focus:ring-primary-500 outline-none" />
            </div>
            <div className="flex items-center gap-4 self-end pb-1">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.is_veg} onChange={e => set('is_veg', e.target.checked)}
                  className="w-4 h-4 rounded text-emerald-500" />
                <span className="text-sm text-emerald-600 font-medium">Veg</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.is_jain} onChange={e => set('is_jain', e.target.checked)}
                  className="w-4 h-4 rounded" />
                <span className="text-sm text-surface-600 font-medium">Jain</span>
              </label>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-surface-600 border border-surface-200 rounded-lg hover:bg-surface-50 transition-colors">Cancel</button>
            <button type="submit" disabled={loading}
              className="px-5 py-2 text-sm font-semibold bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50">
              {loading ? 'Saving…' : 'Add Customer'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Customer Profile Drawer ─────────────────────────────────────────────
function CustomerDrawer({ customerId, onClose }) {
  const [customer, setCustomer] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!customerId) return
    setLoading(true)
    apiFetch(`/customers/${customerId}`)
      .then(setCustomer)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [customerId])

  const channelLabel = { dine_in: 'Dine-in', takeaway: 'Takeaway', zomato: 'Zomato', swiggy: 'Swiggy', phone: 'Phone' }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30 backdrop-blur-sm animate-fade-in" onClick={onClose}>
      <div className="w-full max-w-md bg-white h-full shadow-2xl overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="sticky top-0 bg-white border-b border-surface-200 px-6 py-4 flex items-center justify-between z-10">
          <h2 className="font-bold text-surface-900 text-base">Customer Profile</h2>
          <button onClick={onClose} className="text-surface-400 hover:text-surface-600 transition-colors"><X size={18} /></button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48 text-surface-400 text-sm">Loading…</div>
        ) : !customer ? (
          <div className="flex items-center justify-center h-48 text-red-500 text-sm">Customer not found</div>
        ) : (
          <div className="p-6 space-y-6">
            {/* Identity */}
            <div className="flex items-start gap-4">
              <div className="w-14 h-14 rounded-full flex items-center justify-center text-xl font-bold text-white shrink-0"
                style={{ background: segmentColors[customer.segment] || '#94a3b8' }}>
                {(customer.name || customer.phone || '?')[0].toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-lg font-bold text-surface-900">{customer.name || '—'}</h3>
                <p className="text-sm text-surface-500">{customer.phone}</p>
                {customer.email && <p className="text-xs text-surface-400 truncate">{customer.email}</p>}
                <span className="inline-block mt-1.5 text-xs px-2 py-0.5 rounded-full border font-semibold"
                  style={{ color: segmentColors[customer.segment], borderColor: (segmentColors[customer.segment] || '#94a3b8') + '55', background: (segmentColors[customer.segment] || '#94a3b8') + '15' }}>
                  {customer.segment}
                </span>
              </div>
            </div>

            {/* Stats grid */}
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Total Visits', value: customer.total_visits },
                { label: 'Total Spent', value: `₹${Number(customer.total_spent || 0).toLocaleString()}` },
                { label: 'Avg Order', value: `₹${Number(customer.avg_order_val || 0).toFixed(0)}` },
                { label: 'Loyalty Points', value: customer.loyalty_points ?? 0 },
              ].map(({ label, value }) => (
                <div key={label} className="bg-surface-50 rounded-xl p-3 border border-surface-100">
                  <p className="text-xs text-surface-400 font-medium">{label}</p>
                  <p className="text-lg font-bold text-surface-900 mt-0.5">{value}</p>
                </div>
              ))}
            </div>

            {/* Details */}
            <div className="space-y-2 text-sm">
              {customer.first_visit && (
                <div className="flex justify-between">
                  <span className="text-surface-400">First Visit</span>
                  <span className="font-medium text-surface-700">{new Date(customer.first_visit).toLocaleDateString()}</span>
                </div>
              )}
              {customer.last_visit && (
                <div className="flex justify-between">
                  <span className="text-surface-400">Last Visit</span>
                  <span className="font-medium text-surface-700">{new Date(customer.last_visit).toLocaleDateString()}</span>
                </div>
              )}
              {customer.favourite_item && (
                <div className="flex justify-between">
                  <span className="text-surface-400">Favourite Item</span>
                  <span className="font-medium text-violet-600">{customer.favourite_item}</span>
                </div>
              )}
              {customer.favourite_payment && (
                <div className="flex justify-between">
                  <span className="text-surface-400">Preferred Payment</span>
                  <span className="font-medium text-surface-700 capitalize">{customer.favourite_payment}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-surface-400">Churn Risk</span>
                <span className={`font-semibold ${riskColor(customer.churn_risk_score)}`}>
                  {Math.round((customer.churn_risk_score || 0) * 100)}%
                </span>
              </div>
              {(customer.is_veg || customer.is_jain) && (
                <div className="flex justify-between">
                  <span className="text-surface-400">Preference</span>
                  <div className="flex gap-1.5">
                    {customer.is_veg && <span className="text-xs px-2 py-0.5 bg-emerald-50 text-emerald-600 border border-emerald-200 rounded-full font-medium">Veg</span>}
                    {customer.is_jain && <span className="text-xs px-2 py-0.5 bg-amber-50 text-amber-600 border border-amber-200 rounded-full font-medium">Jain</span>}
                  </div>
                </div>
              )}
            </div>

            {/* Recent Orders */}
            {customer.recent_orders && customer.recent_orders.length > 0 && (
              <div>
                <h4 className="font-semibold text-surface-900 mb-3 text-sm">Recent Orders</h4>
                <div className="space-y-2">
                  {customer.recent_orders.map(order => (
                    <div key={order.order_id} className="bg-surface-50 rounded-lg p-3 border border-surface-100">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-mono text-primary-600 font-semibold">#{order.order_id}</span>
                        <span className="text-xs font-bold text-surface-900">₹{Number(order.total).toFixed(0)}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <p className="text-xs text-surface-500 truncate flex-1 mr-2">
                          {(order.items || []).filter(i => i.item_name).map(i => `${i.qty}x ${i.item_name}`).join(', ') || '—'}
                        </p>
                        <span className="text-xs text-surface-400 shrink-0">{new Date(order.placed_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main Component ──────────────────────────────────────────────────────
export default function Customers() {
  const [segments, setSegments] = useState([])
  const [churnRisk, setChurnRisk] = useState({ data: [] })
  const [directory, setDirectory] = useState([])
  const [tab, setTab] = useState('segments')
  const [churnThreshold, setChurnThreshold] = useState(0.6)
  const [period, setPeriod] = useState('all')
  const [dirSearch, setDirSearch] = useState('')
  const [showAddModal, setShowAddModal] = useState(false)
  const [profileId, setProfileId] = useState(null)
  const [syncing, setSyncing] = useState(false)
  const dirSearchTimer = useRef(null)

  const refreshAll = () => {
    apiFetch('/customers/segments').catch(() => []).then(setSegments)
    apiFetch(`/customers/churn-risk?threshold=${churnThreshold}`)
      .catch(() => ({ data: [] }))
      .then(r => setChurnRisk(r || { data: [] }))
  }

  useEffect(() => {
    apiFetch('/customers/segments').catch(() => []).then(setSegments)
  }, [])

  useEffect(() => {
    apiFetch(`/customers/churn-risk?threshold=${churnThreshold}`)
      .catch(() => ({ data: [] }))
      .then(r => setChurnRisk(r || { data: [] }))
  }, [churnThreshold])

  // Directory: reload when period or search changes (debounced for search)
  useEffect(() => {
    if (tab !== 'directory') return
    clearTimeout(dirSearchTimer.current)
    dirSearchTimer.current = setTimeout(() => {
      const qs = new URLSearchParams({ period })
      if (dirSearch.trim()) qs.set('q', dirSearch.trim())
      apiFetch(`/customers/list?${qs}`)
        .catch(() => [])
        .then(rows => setDirectory(Array.isArray(rows) ? rows : []))
    }, 200)
    return () => clearTimeout(dirSearchTimer.current)
  }, [tab, period, dirSearch])

  const totalCustomers = segments.reduce((s, r) => s + r.count, 0)
  const vipCount = segments.find(s => s.segment === 'VIP')?.count || 0
  const lostCount = segments.find(s => s.segment === 'Lost')?.count || 0
  const churnCount = churnRisk?.data?.length || 0

  const tabs = [
    { id: 'segments', label: 'Segments', icon: Users },
    { id: 'churn', label: 'Churn Risk', icon: AlertCircle },
    { id: 'directory', label: 'Directory', icon: Search },
  ]

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-surface-900">Customer Analytics</h1>
          <p className="text-surface-400 text-sm mt-0.5">Segment breakdown · churn risk · LTV insights</p>
        </div>
      <div className="flex items-center gap-2">
        <button
          onClick={async () => {
            setSyncing(true)
            try {
              await apiFetch('/customers/recalculate-segments', { method: 'POST' })
              refreshAll()
            } catch { /* silent */ } finally {
              setSyncing(false)
            }
          }}
          disabled={syncing}
          title="Recalculate segments and churn scores for all customers"
          className="flex items-center gap-2 border border-surface-300 hover:bg-surface-100 text-surface-600 font-medium px-3 py-2 rounded-lg transition-colors disabled:opacity-50 text-sm"
        >
          <RefreshCw size={14} className={syncing ? 'animate-spin' : ''} />
          {syncing ? 'Syncing…' : 'Sync Segments'}
        </button>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white font-medium px-4 py-2 rounded-lg shadow transition-colors text-sm"
        >
          <Plus size={15} /> Add Customer
        </button>
      </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Total Customers', value: totalCustomers, color: 'text-primary-600', icon: Users },
          { label: 'VIP Customers', value: vipCount, color: 'text-violet-600', icon: Star },
          { label: 'Lost Customers', value: lostCount, color: 'text-red-600', icon: TrendingDown },
          { label: `At-Risk (>${Math.round(churnThreshold * 100)}%)`, value: churnCount, color: 'text-amber-600', icon: AlertCircle },
        ].map(({ label, value, color, icon: Icon }) => (
          <div key={label} className="card p-4">
            <div className="flex items-center gap-2 mb-2">
              <Icon size={14} className={color} />
              <p className="text-xs text-surface-400 font-medium">{label}</p>
            </div>
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Segment info callout */}
      <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 text-xs text-blue-700 space-y-0.5">
        <p><strong>Lost</strong> — customers whose last visit was more than 90 days ago.</p>
        <p><strong>At-Risk</strong> — customers with a churn score above the threshold (score = days since last visit ÷ 180, capped at 1). Use the slider in the Churn Risk tab to adjust.</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-100 p-1 rounded-lg w-fit">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              tab === id
                ? 'bg-white text-primary-600 shadow-card border border-surface-200'
                : 'text-surface-500 hover:text-surface-700'
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* Period filter (shown on Churn + Directory tabs) */}
      {tab !== 'segments' && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-surface-400 font-medium mr-1">Period:</span>
          {PERIODS.map(p => (
            <button
              key={p.id}
              onClick={() => setPeriod(p.id)}
              className={`text-xs font-medium px-3 py-1.5 rounded-full border transition-all ${
                period === p.id
                  ? 'bg-primary-50 text-primary-600 border-primary-200 font-semibold'
                  : 'text-surface-500 border-surface-200 bg-white hover:bg-surface-50'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      )}

      {/* ── Tab: Segments ── */}
      {tab === 'segments' && (
        <div className="space-y-6">
          <div className="grid lg:grid-cols-2 gap-6">
            <div className="card p-6">
              <h2 className="font-semibold text-surface-900 mb-5">Segment Distribution</h2>
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={segments}
                    dataKey="count"
                    nameKey="segment"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    label={({ segment, count }) => `${segment}: ${count}`}
                    labelLine={false}
                  >
                    {segments.map((entry, i) => (
                      <Cell key={i} fill={segmentColors[entry.segment] || '#94a3b8'} />
                    ))}
                  </Pie>
                  <Legend formatter={(value) => <span className="text-xs text-surface-600">{value}</span>} />
                  <Tooltip formatter={(v, name) => [v, name]} />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="card p-6">
              <h2 className="font-semibold text-surface-900 mb-5">Avg Spend per Segment</h2>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={segments} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="segment" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickFormatter={v => `₹${v}`} />
                  <Tooltip formatter={(v) => [`₹${v}`, 'Avg Spent']} />
                  <Bar dataKey="avg_spent" radius={[4, 4, 0, 0]}>
                    {segments.map((entry, i) => (
                      <Cell key={i} fill={segmentColors[entry.segment] || '#6366f1'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card p-6 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-200">
                  {['Segment', 'Count', 'Avg Spent', 'Avg Visits', 'Avg Churn Risk', 'Revenue Share'].map(h => (
                    <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-4">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100">
                {segments.map((row, i) => {
                  const totalSpend = segments.reduce((s, r) => s + r.avg_spent * r.count, 0)
                  const share = totalSpend > 0 ? Math.round((row.avg_spent * row.count) / totalSpend * 100) : 0
                  return (
                    <tr key={i} className="hover:bg-surface-50 transition-colors">
                      <td className="py-2.5 pr-4">
                        <span className="text-xs px-2 py-0.5 rounded-full border font-semibold"
                          style={{ color: segmentColors[row.segment], borderColor: segmentColors[row.segment] + '55', background: segmentColors[row.segment] + '15' }}>
                          {row.segment}
                        </span>
                      </td>
                      <td className="py-2.5 pr-4 text-surface-900 font-bold text-xs">{row.count}</td>
                      <td className="py-2.5 pr-4 text-emerald-600 font-semibold text-xs">₹{row.avg_spent}</td>
                      <td className="py-2.5 pr-4 text-surface-600 text-xs">{row.avg_visits}</td>
                      <td className="py-2.5 pr-4">
                        <div className="flex items-center gap-2">
                          <div className="w-12 h-1.5 bg-surface-200 rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${riskBar(row.avg_churn_risk)}`}
                              style={{ width: `${row.avg_churn_risk * 100}%` }} />
                          </div>
                          <span className={`text-xs font-semibold ${riskColor(row.avg_churn_risk)}`}>
                            {Math.round(row.avg_churn_risk * 100)}%
                          </span>
                        </div>
                      </td>
                      <td className="py-2.5">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 bg-surface-200 rounded-full overflow-hidden">
                            <div className="h-full rounded-full bg-primary-400" style={{ width: `${share}%` }} />
                          </div>
                          <span className="text-xs text-surface-600">{share}%</span>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Tab: Churn Risk ── */}
      {tab === 'churn' && (
        <div className="space-y-4">
          <div className="card p-4 flex items-center gap-4">
            <label className="text-sm text-surface-600 font-medium shrink-0">Risk Threshold:</label>
            <input
              type="range"
              min="0.1" max="0.9" step="0.05"
              value={churnThreshold}
              onChange={e => setChurnThreshold(parseFloat(e.target.value))}
              className="flex-1"
            />
            <span className="text-sm font-bold text-primary-600 w-12">{Math.round(churnThreshold * 100)}%</span>
          </div>

          <div className="card p-6 overflow-x-auto">
            <h2 className="font-semibold text-surface-900 mb-1">Customers at Churn Risk</h2>
            <p className="text-surface-400 text-xs mb-5">
              {churnRisk?.source === 'sql_fallback' ? 'Using pre-computed churn scores from DB' : 'ML model predictions'}
              {' · '}{churnCount} customers above {Math.round(churnThreshold * 100)}% threshold
            </p>

            {churnCount === 0 ? (
              <div className="py-10 text-center">
                <Users size={32} className="text-emerald-400 mx-auto mb-3" />
                <p className="text-emerald-600 font-semibold">No customers at risk at this threshold</p>
                <p className="text-surface-400 text-sm mt-1">Lower the slider to see more customers.</p>
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-200">
                    {['Name', 'Segment', 'Visits', 'Total Spent', 'Last Visit', 'Fav Item', 'Churn Risk', ''].map(h => (
                      <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100">
                  {(churnRisk?.data || []).map((row, i) => (
                    <tr key={i} className="hover:bg-surface-50 transition-colors">
                      <td className="py-2.5 pr-3 text-surface-900 font-medium text-xs">{row.name || '—'}</td>
                      <td className="py-2.5 pr-3">
                        <span className="text-xs px-2 py-0.5 rounded-full border font-semibold"
                          style={{ color: segmentColors[row.segment] || '#94a3b8', borderColor: (segmentColors[row.segment] || '#94a3b8') + '55', background: (segmentColors[row.segment] || '#94a3b8') + '15' }}>
                          {row.segment}
                        </span>
                      </td>
                      <td className="py-2.5 pr-3 text-surface-600 text-xs">{row.total_visits}</td>
                      <td className="py-2.5 pr-3 text-emerald-600 font-semibold text-xs">₹{Number(row.total_spent).toLocaleString()}</td>
                      <td className="py-2.5 pr-3 text-surface-500 text-xs">
                        {row.last_visit ? new Date(row.last_visit).toLocaleDateString() : '—'}
                      </td>
                      <td className="py-2.5 pr-3 text-surface-600 text-xs">{row.favourite_item || '—'}</td>
                      <td className="py-2.5 pr-3">
                        <div className="flex items-center gap-2">
                          <div className="w-14 h-1.5 bg-surface-200 rounded-full overflow-hidden">
                            <div className={`h-full rounded-full ${riskBar(row.churn_risk_score)}`}
                              style={{ width: `${row.churn_risk_score * 100}%` }} />
                          </div>
                          <span className={`text-xs font-bold ${riskColor(row.churn_risk_score)}`}>
                            {Math.round(row.churn_risk_score * 100)}%
                          </span>
                        </div>
                      </td>
                      <td className="py-2.5">
                        <button onClick={() => setProfileId(row.customer_id)} className="text-primary-500 hover:text-primary-700 transition-colors">
                          <ChevronRight size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* ── Tab: Directory ── */}
      {tab === 'directory' && (
        <div className="space-y-4">
          <div className="relative w-72">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
            <input
              type="text"
              placeholder="Search name or phone…"
              value={dirSearch}
              onChange={e => setDirSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-white border border-surface-200 rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>

          <div className="card overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface-50">
                <tr className="border-b border-surface-200">
                  {['Name', 'Phone', 'Segment', 'Visits', 'Total Spent', 'Last Visit', 'Fav Item', 'Churn', ''].map(h => (
                    <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider px-4 py-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100">
                {directory.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="text-center text-surface-400 text-sm py-10">
                      {dirSearch ? 'No customers match your search.' : 'No customers found for this period.'}
                    </td>
                  </tr>
                ) : directory.map((row, i) => (
                  <tr key={i} className="hover:bg-surface-50 transition-colors cursor-pointer" onClick={() => setProfileId(row.customer_id)}>
                    <td className="px-4 py-3 text-surface-900 font-medium text-xs">{row.name || '—'}</td>
                    <td className="px-4 py-3 text-surface-500 text-xs font-mono">{row.phone}</td>
                    <td className="px-4 py-3">
                      <span className="text-xs px-2 py-0.5 rounded-full border font-semibold"
                        style={{ color: segmentColors[row.segment] || '#94a3b8', borderColor: (segmentColors[row.segment] || '#94a3b8') + '55', background: (segmentColors[row.segment] || '#94a3b8') + '15' }}>
                        {row.segment}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-surface-600 text-xs">{row.total_visits}</td>
                    <td className="px-4 py-3 text-emerald-600 font-semibold text-xs">₹{Number(row.total_spent || 0).toLocaleString()}</td>
                    <td className="px-4 py-3 text-surface-500 text-xs">
                      {row.last_visit ? new Date(row.last_visit).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-4 py-3 text-surface-600 text-xs">{row.favourite_item || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-semibold ${riskColor(row.churn_risk_score)}`}>
                        {Math.round((row.churn_risk_score || 0) * 100)}%
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <ChevronRight size={14} className="text-surface-300" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modals */}
      {showAddModal && (
        <AddCustomerModal
          onClose={() => setShowAddModal(false)}
          onCreated={(newCustomer) => {
            if (tab === 'directory') setDirectory(prev => [newCustomer, ...prev])
            refreshAll()
          }}
        />
      )}

      {profileId && (
        <CustomerDrawer
          customerId={profileId}
          onClose={() => setProfileId(null)}
        />
      )}
    </div>
  )
}

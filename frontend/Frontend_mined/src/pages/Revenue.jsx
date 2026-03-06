import { useState, useEffect } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  LineChart, Line, Area, AreaChart,
} from 'recharts'
import { apiFetch } from '../config'
import { TrendingUp, Tag, CreditCard, ArrowUpRight, AlertTriangle, Activity, ShoppingCart } from 'lucide-react'

const methodColors = {
  cash: '#10b981',
  upi: '#6366f1',
  credit_card: '#f59e0b',
  debit_card: '#3b82f6',
  wallet: '#ec4899',
}
const methodLabel = {
  cash: 'Cash',
  upi: 'UPI',
  credit_card: 'Credit Card',
  debit_card: 'Debit Card',
  wallet: 'Wallet',
}
const classColor = { Star: '#10b981', Puzzle: '#8b5cf6', Plowhorse: '#e11d48', Dog: '#f97316' }

const CurrencyTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="card px-3 py-2 text-xs shadow-card-md">
      <p className="font-semibold text-surface-900 mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: <strong>₹{Number(p.value).toLocaleString()}</strong>
        </p>
      ))}
    </div>
  )
}

export default function Revenue() {
  const [contributionMargin, setContributionMargin] = useState([])
  const [priceRecs, setPriceRecs] = useState([])
  const [aov, setAov] = useState({ byChannel: [], byDayOfWeek: [], byHour: [], byPaymentMethod: [], byWeekType: [] })
  const [anomalies, setAnomalies] = useState({ data: [] })
  const [demandForecast, setDemandForecast] = useState({ forecasts: [] })
  const [upsell, setUpsell] = useState({ items: [] })
  const [upsellStats, setUpsellStats] = useState(null)
  const [tab, setTab] = useState('margin')
  const [period, setPeriod] = useState('all')

  useEffect(() => {
    Promise.all([
      apiFetch(`/revenue/contribution-margin?period=${period}`).catch(() => []),
      apiFetch(`/revenue/price-recommendations?period=${period}`).catch(() => []),
      apiFetch(`/revenue/aov?period=${period}`).catch(() => ({ byChannel: [], byDayOfWeek: [], byHour: [], byPaymentMethod: [], byWeekType: [] })),
      apiFetch('/revenue/anomalies').catch(() => ({ data: [] })),
      apiFetch('/revenue/demand-forecast').catch(() => ({ forecasts: [] })),
      apiFetch('/revenue/upsell-recommendations').catch(() => ({ items: [] })),
      apiFetch(`/revenue/upsell-stats?period=${period}`).catch(() => null),
    ]).then(([cm, pr, a, an, df, up, us]) => {
      setContributionMargin(Array.isArray(cm) ? cm : [])
      setPriceRecs(Array.isArray(pr) ? pr : [])
      setAov(a || { byChannel: [], byDayOfWeek: [], byHour: [], byPaymentMethod: [], byWeekType: [] })
      setAnomalies(an || { data: [] })
      setDemandForecast(df || { forecasts: [] })
      setUpsell(up || { items: [] })
      setUpsellStats(us || null)
    })
  }, [period])

  // Aggregate CM by item for the top-20 display
  const cmByItem = Object.values(
    contributionMargin.reduce((acc, row) => {
      if (!acc[row.item_name]) acc[row.item_name] = { name: row.item_name, revenue: 0, margin: 0 }
      acc[row.item_name].revenue += row.total_revenue || 0
      acc[row.item_name].margin = Math.max(acc[row.item_name].margin, row.margin_pct || 0)
      return acc
    }, {})
  )
    .sort((a, b) => b.revenue - a.revenue)
    .slice(0, 20)

  const anomalyData = Array.isArray(anomalies?.data) ? anomalies.data : []
  const anomalyCount = anomalyData.filter(d => d.is_anomaly).length
  const forecastData = Array.isArray(demandForecast?.forecasts) ? demandForecast.forecasts : []
  const upsellItems = Array.isArray(upsell?.items) ? upsell.items : []

  const tabs = [
    { id: 'margin', label: 'Contribution Margin', icon: TrendingUp },
    { id: 'price', label: 'Price Recommendations', icon: Tag },
    { id: 'aov', label: 'AOV Intelligence', icon: CreditCard },
    { id: 'anomalies', label: `Anomalies (${anomalyCount})`, icon: AlertTriangle },
    { id: 'forecast', label: 'Demand Forecast', icon: Activity },
    { id: 'upsell', label: `Upsell (${upsellItems.length})`, icon: ShoppingCart },
  ]

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-surface-900">Revenue Intelligence</h1>
          <p className="text-surface-400 text-sm mt-0.5">Margin analysis · data-driven price suggestions · AOV deep dive</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-surface-400 font-medium">Period:</span>
          <div className="flex gap-1 bg-surface-100 p-1 rounded-lg">
            {[{id:'all',label:'All Time'},{id:'90d',label:'90 Days'},{id:'30d',label:'30 Days'},{id:'7d',label:'7 Days'}].map(({id,label}) => (
              <button key={id} onClick={() => setPeriod(id)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                  period === id ? 'bg-white text-primary-600 shadow-card border border-surface-200' : 'text-surface-500 hover:text-surface-700'
                }`}>{label}</button>
            ))}
          </div>
        </div>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'SKUs Tracked', value: contributionMargin.length, color: 'text-primary-600' },
          { label: 'Price Suggestions', value: priceRecs.length, color: 'text-violet-600' },
          { label: 'Avg AOV (dine-in)', value: `₹${Math.round(aov.byChannel.find(c => c.channel === 'dine_in')?.avg_order_value || 0)}`, color: 'text-emerald-600' },
          { label: 'Weekend AOV', value: `₹${Math.round(aov.byWeekType.find(w => w.week_type === 'Weekend')?.avg_order_value || 0)}`, color: 'text-amber-600' },
        ].map(({ label, value, color }) => (
          <div key={label} className="card p-4">
            <p className="text-xs text-surface-400 font-medium">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
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

      {/* ── Tab: Contribution Margin ── */}
      {tab === 'margin' && (
        <div className="space-y-6">
          <div className="card p-6">
            <h2 className="font-semibold text-surface-900 mb-1">Top Items by Revenue &amp; Margin %</h2>
            <p className="text-surface-400 text-xs mb-5">Bars = total revenue · colour = margin % (green = high)</p>
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={cmByItem} margin={{ top: 5, right: 20, bottom: 60, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} angle={-40} textAnchor="end" interval={0} />
                <YAxis yAxisId="rev" orientation="left" tick={{ fill: '#94a3b8', fontSize: 11 }} tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                <YAxis yAxisId="pct" orientation="right" tick={{ fill: '#94a3b8', fontSize: 11 }} tickFormatter={v => `${v}%`} domain={[0, 100]} />
                <Tooltip content={<CurrencyTooltip />} />
                <Bar yAxisId="rev" dataKey="revenue" name="Revenue" fill="#6366f1" radius={[3, 3, 0, 0]} />
                <Bar yAxisId="pct" dataKey="margin" name="Margin %" fill="#10b981" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card p-6 overflow-x-auto">
            <h2 className="font-semibold text-surface-900 mb-4">Full Contribution Margin Table</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-200">
                  {['Item', 'Variant', 'Price', 'Food Cost', 'Margin ₹', 'Margin %', 'Qty Sold', 'Revenue'].map(h => (
                    <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-4">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100">
                {contributionMargin.slice(0, 40).map((row, i) => (
                  <tr key={i} className="hover:bg-surface-50 transition-colors">
                    <td className="py-2.5 pr-4 text-surface-900 font-medium text-xs">{row.item_name}</td>
                    <td className="py-2.5 pr-4 text-surface-500 text-xs">{row.variant_name}</td>
                    <td className="py-2.5 pr-4 text-surface-700 text-xs">₹{row.selling_price}</td>
                    <td className="py-2.5 pr-4 text-surface-500 text-xs">₹{row.food_cost}</td>
                    <td className="py-2.5 pr-4 font-semibold text-emerald-600 text-xs">₹{row.margin?.toFixed(2)}</td>
                    <td className="py-2.5 pr-4 text-xs">
                      <span className={`px-2 py-0.5 rounded-full border text-xs font-medium ${
                        row.margin_pct >= 60 ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
                          : row.margin_pct >= 35 ? 'text-amber-700 bg-amber-50 border-amber-200'
                          : 'text-red-700 bg-red-50 border-red-200'
                      }`}>
                        {row.margin_pct?.toFixed(1)}%
                      </span>
                    </td>
                    <td className="py-2.5 pr-4 text-surface-700 text-xs">{row.qty_sold}</td>
                    <td className="py-2.5 text-primary-600 font-semibold text-xs">₹{Number(row.total_revenue).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Tab: Price Recommendations ── */}
      {tab === 'price' && (
        <div className="card p-6 overflow-x-auto">
          <h2 className="font-semibold text-surface-900 mb-1">Data-Driven Price Change Suggestions</h2>
          <p className="text-surface-400 text-xs mb-5">Suggestions based on BCG classification · final decision is admin's</p>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-200">
                {['Item', 'Variant', 'Class', 'Current ₹', 'Suggested ₹', 'Change', 'Reason'].map(h => (
                  <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-4">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {priceRecs.map((row, i) => {
                const diff = row.suggested_price - row.current_price
                const pct = ((diff / row.current_price) * 100).toFixed(0)
                return (
                  <tr key={i} className="hover:bg-surface-50 transition-colors">
                    <td className="py-2.5 pr-4 text-surface-900 font-medium text-xs">{row.item_name}</td>
                    <td className="py-2.5 pr-4 text-surface-500 text-xs">{row.variant_name}</td>
                    <td className="py-2.5 pr-4">
                      <span className="text-xs px-2 py-0.5 rounded-full border font-semibold"
                        style={{ color: classColor[row.classification], borderColor: classColor[row.classification] + '55', background: classColor[row.classification] + '15' }}>
                        {row.classification}
                      </span>
                    </td>
                    <td className="py-2.5 pr-4 text-surface-700 text-xs">₹{row.current_price}</td>
                    <td className="py-2.5 pr-4 font-bold text-primary-600 text-xs">₹{row.suggested_price}</td>
                    <td className="py-2.5 pr-4">
                      <span className={`text-xs font-semibold flex items-center gap-1 ${diff > 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                        <ArrowUpRight size={12} style={{ transform: diff < 0 ? 'rotate(90deg)' : undefined }} />
                        {diff > 0 ? '+' : ''}{pct}%
                      </span>
                    </td>
                    <td className="py-2.5 text-surface-500 text-xs max-w-xs">{row.reason}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {priceRecs.length === 0 && (
            <p className="text-center text-surface-400 text-sm py-8">No price suggestions — all items are already well-optimised.</p>
          )}
        </div>
      )}

      {/* ── Tab: AOV Intelligence ── */}
      {tab === 'aov' && (
        <div className="space-y-6">
          {/* Weekend vs Weekday */}
          <div className="grid sm:grid-cols-2 gap-4">
            {aov.byWeekType.map(w => (
              <div key={w.week_type} className="card p-5 flex items-center gap-4">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-white text-lg font-bold ${w.week_type === 'Weekend' ? 'bg-violet-500' : 'bg-primary-500'}`}>
                  {w.week_type === 'Weekend' ? 'W/E' : 'W/D'}
                </div>
                <div>
                  <p className="text-xs text-surface-400">{w.week_type}</p>
                  <p className="text-2xl font-bold text-surface-900">₹{w.avg_order_value}</p>
                  <p className="text-xs text-surface-400">{w.order_count.toLocaleString()} orders</p>
                </div>
              </div>
            ))}
          </div>

          {/* Payment Method Breakdown */}
          <div className="card p-6">
            <h2 className="font-semibold text-surface-900 mb-5">AOV by Payment Method</h2>
            <div className="space-y-3">
              {aov.byPaymentMethod.map(pm => {
                const max = Math.max(...aov.byPaymentMethod.map(p => p.avg_order_value))
                const pct = max > 0 ? (pm.avg_order_value / max) * 100 : 0
                return (
                  <div key={pm.payment_method} className="flex items-center gap-3">
                    <span className="text-xs text-surface-600 font-medium w-24 shrink-0">{methodLabel[pm.payment_method] || pm.payment_method}</span>
                    <div className="flex-1 h-5 bg-surface-100 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{ width: `${pct}%`, background: methodColors[pm.payment_method] || '#6366f1' }}
                      />
                    </div>
                    <span className="text-xs font-bold text-surface-900 w-20 text-right">₹{pm.avg_order_value}</span>
                    <span className="text-xs text-surface-400 w-16 text-right">{pm.order_count} orders</span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* AOV by Channel */}
          <div className="card p-6">
            <h2 className="font-semibold text-surface-900 mb-5">AOV by Channel</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={aov.byChannel} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="channel" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickFormatter={v => `₹${v}`} />
                <Tooltip formatter={(v) => [`₹${v}`, 'Avg Order Value']} />
                <Bar dataKey="avg_order_value" name="Avg Order Value" fill="#6366f1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* AOV by Day of Week */}
          <div className="card p-6">
            <h2 className="font-semibold text-surface-900 mb-5">AOV by Day of Week</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={aov.byDayOfWeek} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="day" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickFormatter={v => `₹${v}`} />
                <Tooltip formatter={(v) => [`₹${v}`, 'AOV']} />
                <Bar dataKey="avg_order_value" name="AOV" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── Tab: Anomaly Detection ── */}
      {tab === 'anomalies' && (
        <div className="space-y-6">
          <div className="card p-4 bg-red-50 border border-red-200">
            <div className="flex items-start gap-3">
              <AlertTriangle size={16} className="text-red-600 mt-0.5 shrink-0" />
              <div>
                <p className="text-red-800 font-semibold text-sm">Revenue Anomaly Detection</p>
                <p className="text-red-600 text-xs mt-0.5">
                  {anomalies?.source === 'sql_fallback'
                    ? 'Using z-score detection (|z| > 2). Run Isolation Forest notebook for better accuracy.'
                    : 'Isolation Forest model — flags top 5% of days as anomalies regardless of distribution.'}
                  {' · '}{anomalyCount} anomalies detected across {anomalyData.length} days.
                </p>
              </div>
            </div>
          </div>

          {/* Revenue timeline chart */}
          <div className="card p-6">
            <h2 className="font-semibold text-surface-900 mb-1">Daily Revenue — Anomalies Highlighted</h2>
            <p className="text-surface-400 text-xs mb-5">Red dots indicate anomalous days</p>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={anomalyData.slice(-90)} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="day" tick={{ fill: '#94a3b8', fontSize: 10 }} tickFormatter={v => v?.slice(5)} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                <Tooltip formatter={(v, name) => [name === 'revenue' ? `₹${Number(v).toLocaleString()}` : v, name]} />
                <Area type="monotone" dataKey="revenue" stroke="#6366f1" fill="#6366f1" fillOpacity={0.1} strokeWidth={1.5} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Anomaly table */}
          <div className="card p-6 overflow-x-auto">
            <h2 className="font-semibold text-surface-900 mb-4">Anomalous Days</h2>
            {anomalyCount === 0 ? (
              <p className="text-center text-surface-400 text-sm py-8">No anomalies detected — revenue patterns appear stable.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-200">
                    {['Date', 'Day', 'Orders', 'Revenue', 'Avg Order Value', 'Score', 'Possible Reason'].map(h => (
                      <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-4">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100">
                  {anomalyData.filter(d => d.is_anomaly).map((row, i) => {
                    const dayTypeColors = {
                      Festival: 'text-amber-700 bg-amber-50 border-amber-200',
                      Weekend: 'text-blue-700 bg-blue-50 border-blue-200',
                      Friday: 'text-violet-700 bg-violet-50 border-violet-200',
                      Weekday: 'text-surface-600 bg-surface-100 border-surface-200',
                    }
                    return (
                      <tr key={i} className="hover:bg-red-50/50 transition-colors">
                        <td className="py-2.5 pr-4 text-surface-900 font-medium text-xs">{row.day}</td>
                        <td className="py-2.5 pr-4">
                          <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${dayTypeColors[row.day_type] || dayTypeColors.Weekday}`}>
                            {row.day_type || 'Weekday'}
                          </span>
                        </td>
                        <td className="py-2.5 pr-4 text-surface-700 text-xs">{row.order_count || row.daily_orders}</td>
                        <td className="py-2.5 pr-4 text-primary-600 font-semibold text-xs">₹{Number(row.revenue || row.daily_revenue).toLocaleString()}</td>
                        <td className="py-2.5 pr-4 text-surface-600 text-xs">₹{Math.round(row.avg_order_val || 0)}</td>
                        <td className="py-2.5 pr-4 text-red-600 font-bold text-xs">{(row.z_score || row.anomaly_score || 0).toFixed(2)}</td>
                        <td className="py-2.5 text-xs text-surface-600">{row.day_label || '—'}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* ── Tab: Demand Forecast ── */}
      {tab === 'forecast' && (
        <div className="space-y-6">
          <div className="card p-4 bg-primary-50 border border-primary-200">
            <div className="flex items-start gap-3">
              <Activity size={16} className="text-primary-600 mt-0.5 shrink-0" />
              <div>
                <p className="text-primary-800 font-semibold text-sm">Demand Forecast</p>
                <p className="text-primary-600 text-xs mt-0.5">
                  {demandForecast?.source === 'unavailable'
                    ? 'ML service not running — start FastAPI on port 8000 and run the LightGBM demand_forecast notebook.'
                    : `${demandForecast?.model || 'LightGBM'} model · ${forecastData.length}-day horizon`}
                </p>
              </div>
            </div>
          </div>

          {forecastData.length === 0 ? (
            <div className="card p-12 text-center">
              <Activity size={32} className="text-surface-300 mx-auto mb-3" />
              <p className="text-surface-500 font-semibold">Forecast Unavailable</p>
              <p className="text-surface-400 text-sm mt-1">Run the demand_forecast notebook and start the ML service to see predictions.</p>
            </div>
          ) : (
            <>
              {/* Order forecast chart */}
              <div className="card p-6">
                <h2 className="font-semibold text-surface-900 mb-1">Predicted Daily Orders</h2>
                <p className="text-surface-400 text-xs mb-5">Next {forecastData.length} days</p>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={forecastData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 10 }} tickFormatter={v => v?.slice(5)} />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <Tooltip formatter={(v) => [v, 'Predicted Orders']} />
                    <Line type="monotone" dataKey="predicted_orders" stroke="#6366f1" strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Revenue forecast chart */}
              <div className="card p-6">
                <h2 className="font-semibold text-surface-900 mb-1">Predicted Daily Revenue</h2>
                <p className="text-surface-400 text-xs mb-5">Next {forecastData.length} days</p>
                <ResponsiveContainer width="100%" height={250}>
                  <AreaChart data={forecastData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 10 }} tickFormatter={v => v?.slice(5)} />
                    <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                    <Tooltip formatter={(v) => [`₹${Number(v).toLocaleString()}`, 'Predicted Revenue']} />
                    <Area type="monotone" dataKey="predicted_revenue" stroke="#10b981" fill="#10b981" fillOpacity={0.15} strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* Forecast table */}
              <div className="card p-6 overflow-x-auto">
                <h2 className="font-semibold text-surface-900 mb-4">Forecast Details</h2>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-200">
                      {['Date', 'Day', 'Predicted Orders', 'Predicted Revenue'].map(h => (
                        <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-4">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-100">
                    {forecastData.map((row, i) => {
                      const d = new Date(row.date)
                      const dayName = d.toLocaleDateString('en-IN', { weekday: 'short' })
                      return (
                        <tr key={i} className="hover:bg-surface-50 transition-colors">
                          <td className="py-2.5 pr-4 text-surface-900 font-medium text-xs">{row.date}</td>
                          <td className="py-2.5 pr-4 text-surface-500 text-xs">{dayName}</td>
                          <td className="py-2.5 pr-4 text-primary-600 font-bold text-xs">{row.predicted_orders}</td>
                          <td className="py-2.5 pr-4 text-emerald-600 font-semibold text-xs">₹{Number(row.predicted_revenue).toLocaleString()}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Tab: Upsell Recommendations ── */}
      {tab === 'upsell' && (
        <div className="space-y-6">
          {/* Live Performance KPIs */}
          {upsellStats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: 'Upsell Orders', value: upsellStats.summary?.orders_with_upsell ?? 0, color: 'text-violet-600' },
                { label: 'Items Upsold', value: upsellStats.summary?.total_upsell_items ?? 0, color: 'text-primary-600' },
                { label: 'Revenue from Upsell', value: `₹${Math.round(upsellStats.summary?.total_upsell_revenue ?? 0).toLocaleString()}`, color: 'text-emerald-600' },
                { label: 'Avg Upsell Value', value: `₹${Math.round(upsellStats.summary?.avg_upsell_value ?? 0)}`, color: 'text-amber-600' },
              ].map(({ label, value, color }) => (
                <div key={label} className="card p-4 border border-violet-100">
                  <p className="text-xs text-surface-400 font-medium">{label}</p>
                  <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
                </div>
              ))}
            </div>
          )}

          {/* Top upsold items (from actual order data) */}
          {upsellStats?.top_items?.length > 0 && (
            <div className="card p-6">
              <h2 className="font-semibold text-surface-900 mb-1">Top Upsold Items — Actual Conversions</h2>
              <p className="text-surface-400 text-xs mb-4">Items staff successfully added via AI upsell prompts</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-200">
                      {['Item', 'Times Upsold', 'Revenue Generated'].map(h => (
                        <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-4">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-100">
                    {upsellStats.top_items.map((row, i) => (
                      <tr key={i} className="hover:bg-surface-50">
                        <td className="py-2.5 pr-4 font-medium text-xs">{row.item_name}</td>
                        <td className="py-2.5 pr-4 text-violet-600 font-bold text-xs">{row.times_upsold}</td>
                        <td className="py-2.5 pr-4 text-emerald-600 font-bold text-xs">₹{Number(row.revenue_generated).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className="card p-4 bg-violet-50 border border-violet-200">
            <div className="flex items-start gap-3">
              <ShoppingCart size={16} className="text-violet-600 mt-0.5 shrink-0" />
              <div>
                <p className="text-violet-800 font-semibold text-sm">Upsell Recommendations</p>
                <p className="text-violet-600 text-xs mt-0.5">
                  {upsell?.type === 'co_occurrence'
                    ? 'Based on co-purchase patterns in order history'
                    : 'Global popular items — high margin cross-sell opportunities'}
                </p>
              </div>
            </div>
          </div>

          {upsellItems.length === 0 ? (
            <div className="card p-12 text-center">
              <ShoppingCart size={32} className="text-surface-300 mx-auto mb-3" />
              <p className="text-surface-500 font-semibold">No Upsell Data</p>
              <p className="text-surface-400 text-sm mt-1">Ensure orders exist in the database to generate recommendations.</p>
            </div>
          ) : (
            <>
              {/* Upsell bar chart */}
              <div className="card p-6">
                <h2 className="font-semibold text-surface-900 mb-1">Top Upsell Items by Co-occurrence</h2>
                <p className="text-surface-400 text-xs mb-5">Items frequently bought together — ranked by pair frequency</p>
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={upsellItems.slice(0, 12)} layout="vertical" margin={{ top: 5, right: 20, bottom: 5, left: 100 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                    <YAxis dataKey="name" type="category" tick={{ fill: '#64748b', fontSize: 11 }} width={90} />
                    <Tooltip formatter={(v, n) => [n === 'co_count' ? v : `₹${v}`, n === 'co_count' ? 'Co-purchases' : 'Avg Price']} />
                    <Bar dataKey="co_count" fill="#8b5cf6" radius={[0, 4, 4, 0]} name="Co-purchases" />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Margin vs Price scatter-like chart */}
              <div className="card p-6">
                <h2 className="font-semibold text-surface-900 mb-1">Price & Margin Overview</h2>
                <p className="text-surface-400 text-xs mb-5">Average price and margin percentage for recommended items</p>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={upsellItems.slice(0, 12)} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} angle={-30} textAnchor="end" height={60} />
                    <YAxis yAxisId="price" tick={{ fill: '#94a3b8', fontSize: 11 }} tickFormatter={v => `₹${v}`} />
                    <YAxis yAxisId="margin" orientation="right" tick={{ fill: '#94a3b8', fontSize: 11 }} tickFormatter={v => `${v}%`} />
                    <Tooltip />
                    <Bar yAxisId="price" dataKey="avg_price" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Avg Price (₹)" />
                    <Bar yAxisId="margin" dataKey="margin" fill="#10b981" radius={[4, 4, 0, 0]} name="Margin %" />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Upsell table */}
              <div className="card p-6 overflow-x-auto">
                <h2 className="font-semibold text-surface-900 mb-4">All Recommendations</h2>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-surface-200">
                      {['Item', 'Category', 'Co-purchases', 'Avg Price', 'Margin'].map(h => (
                        <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-4">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-100">
                    {upsellItems.map((item, i) => (
                      <tr key={i} className="hover:bg-surface-50 transition-colors">
                        <td className="py-2.5 pr-4 text-surface-900 font-medium text-xs">{item.name}</td>
                        <td className="py-2.5 pr-4">
                          <span className="px-2 py-0.5 bg-surface-100 text-surface-600 rounded-full text-xs">{item.category}</span>
                        </td>
                        <td className="py-2.5 pr-4 text-violet-600 font-bold text-xs">{item.co_count}</td>
                        <td className="py-2.5 pr-4 text-surface-700 text-xs">₹{Number(item.avg_price).toFixed(0)}</td>
                        <td className="py-2.5 pr-4">
                          <span className={`font-semibold text-xs ${item.margin >= 50 ? 'text-emerald-600' : item.margin >= 30 ? 'text-amber-600' : 'text-red-500'}`}>
                            {Number(item.margin).toFixed(1)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

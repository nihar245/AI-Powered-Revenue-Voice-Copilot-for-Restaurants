import { useState, useEffect } from 'react'
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
  Cell,
  BarChart,
  Bar,
} from 'recharts'
import { apiFetch } from '../config'
import { TrendingDown, Link2, AlertTriangle, Info, Zap, Star, ShieldAlert, DollarSign } from 'lucide-react'

const recBadgeList = [
  { match: 'Promote', cls: 'text-emerald-700 bg-emerald-50 border-emerald-200', icon: '↑' },
  { match: 'Bundle', cls: 'text-blue-700 bg-blue-50 border-blue-200', icon: '+' },
  { match: 'combo', cls: 'text-violet-700 bg-violet-50 border-violet-200', icon: '+' },
  { match: 'Review', cls: 'text-amber-700 bg-amber-50 border-amber-200', icon: '⚠' },
  { match: 'Reduce', cls: 'text-amber-700 bg-amber-50 border-amber-200', icon: '↓' },
  { match: 'Increase', cls: 'text-emerald-700 bg-emerald-50 border-emerald-200', icon: '↑' },
]
const getRecBadge = (rec) => {
  const found = recBadgeList.find(b => rec && rec.toLowerCase().includes(b.match.toLowerCase()));
  return found || { cls: 'text-surface-500 bg-surface-100 border-surface-200', icon: '·' };
}

const salesBadge = {
  Low: 'text-red-700 bg-red-50 border-red-200',
  Medium: 'text-amber-700 bg-amber-50 border-amber-200',
  High: 'text-emerald-700 bg-emerald-50 border-emerald-200',
}

const marginBadge = {
  Low: 'text-red-700 bg-red-50 border-red-200',
  Medium: 'text-amber-700 bg-amber-50 border-amber-200',
  High: 'text-emerald-700 bg-emerald-50 border-emerald-200',
}

const ScatterTooltip = ({ active, payload }) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  if (!d) return null
  return (
    <div className="card px-3 py-2 text-xs shadow-card-md">
      <p className="font-semibold text-surface-900 mb-1">{d.name}</p>
      <p className="text-surface-400">Popularity: <span className="text-primary-600 font-semibold">{d.popularity}%</span></p>
      <p className="text-surface-400">Margin: <span className="text-emerald-600 font-semibold">{d.margin}%</span></p>
      <p className="text-surface-400">Revenue: <span className="text-violet-600 font-semibold">₹{d.revenue.toLocaleString()}</span></p>
    </div>
  )
}

// Colour each dot based on quadrant
const getColor = (d) => {
  if (d.popularity >= 60 && d.margin >= 60) return '#10b981' // star
  if (d.popularity >= 60 && d.margin < 60) return '#e11d48' // plow horse
  if (d.popularity < 60 && d.margin >= 60) return '#8b5cf6' // puzzle
  return '#f97316' // dog
}

const classColors = {
  'Fast Mover': '#10b981',
  'Normal': '#6366f1',
  'Slow Mover': '#f59e0b',
  'Dead': '#e11d48',
}
const riskLevelColor = {
  High: 'text-red-700 bg-red-50 border-red-200',
  Medium: 'text-amber-700 bg-amber-50 border-amber-200',
  Low: 'text-emerald-700 bg-emerald-50 border-emerald-200',
}

export default function Analytics() {
  const [menuProfitability, setMenuProfitability] = useState([])
  const [comboRecommendations, setComboRecommendations] = useState([])
  const [underperformingItems, setUnderperformingItems] = useState([])
  const [popularityScores, setPopularityScores] = useState([])
  const [hiddenStars, setHiddenStars] = useState({ count: 0, items: [] })
  const [riskItems, setRiskItems] = useState({ count: 0, items: [] })
  const [menuOpt, setMenuOpt] = useState(null)
  const [activeTab, setActiveTab] = useState('matrix')
  const [period, setPeriod] = useState('all')

  useEffect(() => {
    Promise.all([
      apiFetch(`/analytics/menu-profitability?period=${period}`).catch(() => []),
      apiFetch(`/analytics/combo-recommendations?period=${period}`).catch(() => []),
      apiFetch(`/analytics/underperforming-items?period=${period}`).catch(() => []),
      apiFetch(`/analytics/popularity-scoring?period=${period}`).catch(() => []),
      apiFetch(`/analytics/hidden-stars?period=${period}`).catch(() => ({ count: 0, items: [] })),
      apiFetch(`/analytics/risk-detection?period=${period}`).catch(() => ({ count: 0, items: [] })),
      apiFetch('/analytics/menu-optimization').catch(() => null),
    ]).then(([mp, cr, ui, ps, hs, rd, mo]) => {
      setMenuProfitability(mp)
      setComboRecommendations(cr)
      setUnderperformingItems(ui)
      setPopularityScores(Array.isArray(ps) ? ps : [])
      setHiddenStars(hs || { count: 0, items: [] })
      setRiskItems(rd || { count: 0, items: [] })
      setMenuOpt(mo && !mo.source ? mo : null)
    })
  }, [period])

  const analyticsTabs = [
    { id: 'matrix', label: 'BCG Matrix', icon: Star },
    { id: 'combos', label: 'Combos & Underperforming', icon: Link2 },
    { id: 'popularity', label: 'Popularity Scoring', icon: Zap },
    { id: 'hiddenStars', label: `Hidden Stars (${hiddenStars.count})`, icon: Star },
    { id: 'risk', label: `Risk Detection (${riskItems.count})`, icon: ShieldAlert },
    ...(menuOpt ? [{ id: 'mlopt', label: `ML Price Optimization (${menuOpt.price_recommendations?.length || 0})`, icon: DollarSign }] : []),
  ]

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-surface-900">Analytics</h1>
          <p className="text-surface-400 text-sm mt-0.5">Menu intelligence powered by AI &amp; Apriori analysis</p>
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

      {/* ── KPI Strip ── */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        {[
          { label: 'Items Analysed', value: menuProfitability.length, color: 'text-primary-600' },
          { label: 'Hidden Stars', value: hiddenStars.count, color: 'text-violet-600' },
          { label: 'Fast Movers', value: popularityScores.filter(p => p.classification === 'Fast Mover').length, color: 'text-emerald-600' },
          { label: 'At-Risk Items', value: riskItems.count, color: 'text-red-600' },
          { label: 'Combos Found', value: comboRecommendations.length, color: 'text-amber-600' },
        ].map(({ label, value, color }) => (
          <div key={label} className="card p-4 text-center">
            <p className={`text-2xl font-bold ${color}`}>{value}</p>
            <p className="text-surface-400 text-xs mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* ── Sub-tabs ── */}
      <div className="flex gap-1 bg-surface-100 p-1 rounded-lg flex-wrap">
        {analyticsTabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-all ${
              activeTab === id
                ? 'bg-white text-primary-600 shadow-card border border-surface-200'
                : 'text-surface-500 hover:text-surface-700'
            }`}
          >
            <Icon size={13} />
            {label}
          </button>
        ))}
      </div>

      {/* ── Tab: BCG Matrix ── */}
      {activeTab === 'matrix' && <>
      {/* ── Scatter: Profitability Matrix ── */}
      <div className="card p-6">
        <div className="flex items-start justify-between flex-wrap gap-3 mb-6">
          <div>
            <h2 className="font-semibold text-surface-900">Menu Profitability Matrix</h2>
            <p className="text-surface-400 text-xs mt-0.5">Margin vs Popularity · circle size = revenue</p>
          </div>
          <div className="flex items-center gap-4 flex-wrap text-xs">
            {[
              { c: '#10b981', label: 'Star (high pop, high margin)' },
              { c: '#e11d48', label: 'Plow Horse' },
              { c: '#8b5cf6', label: 'Puzzle' },
              { c: '#f97316', label: 'Dog' },
            ].map(({ c, label }) => (
              <span key={label} className="flex items-center gap-1.5 text-surface-500">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: c }} />
                {label}
              </span>
            ))}
          </div>
        </div>

        <ResponsiveContainer width="100%" height={320}>
          <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            {/* Quadrant lines */}
            <XAxis
              type="number"
              dataKey="popularity"
              name="Popularity"
              domain={[0, 100]}
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              label={{ value: 'Popularity →', position: 'insideBottom', offset: -10, fill: '#94a3b8', fontSize: 11 }}
            />
            <YAxis
              type="number"
              dataKey="margin"
              name="Margin"
              domain={[0, 100]}
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              label={{ value: '← Margin', angle: -90, position: 'insideLeft', offset: 20, fill: '#94a3b8', fontSize: 11 }}
            />
            <ZAxis type="number" dataKey="revenue" range={[40, 400]} />
            <Tooltip content={<ScatterTooltip />} />
            <Scatter data={menuProfitability} fill="#0ea5e9">
              {menuProfitability.map((entry, i) => (
                <Cell key={i} fill={getColor(entry)} fillOpacity={0.85} />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>

        {/* Quadrant info */}
        <div className="mt-4 p-3 bg-surface-50 rounded-lg border border-surface-200 flex items-start gap-2">
          <Info size={13} className="text-surface-400 mt-0.5 shrink-0" />
          <p className="text-surface-500 text-xs">
            <strong className="text-surface-600">Stars</strong> should be featured more prominently.{' '}
            <strong className="text-surface-600">Puzzles</strong> have high margin but low popularity — promote them.{' '}
            <strong className="text-surface-600">Dogs</strong> should be reviewed or removed.
          </p>
        </div>
      </div>

      </>}

      {/* ── Tab: Combos & Underperforming ── */}
      {activeTab === 'combos' && (
        <div className="grid lg:grid-cols-2 gap-6">
          {/* Combo Recommendations */}
          <div className="card p-6">
            <div className="flex items-center gap-2 mb-5">
              <Link2 size={15} className="text-primary-600" />
              <div>
                <h2 className="font-semibold text-surface-900 text-sm">Combo Recommendations</h2>
                <p className="text-surface-400 text-xs">Real order co-occurrence · all item pairs · ranked by lift score</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-200">
                    {['Item A', 'Item B', 'Times Paired', 'Confidence', 'Lift'].map(h => (
                      <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-4">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100">
                  {comboRecommendations.map((row, i) => (
                    <tr key={i} className="hover:bg-surface-50 transition-colors">
                      <td className="py-2.5 pr-4 text-surface-900 font-medium text-xs">{row.itemA}</td>
                      <td className="py-2.5 pr-4 text-primary-600 text-xs">{row.itemB}</td>
                      <td className="py-2.5 pr-4 text-surface-600 font-semibold text-xs">{row.pairCount}</td>
                      <td className="py-2.5 pr-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="w-16 h-1.5 bg-surface-200 rounded-full overflow-hidden">
                            <div className="h-full bg-primary-500 rounded-full" style={{ width: `${row.confidence}%` }} />
                          </div>
                          <span className="text-emerald-600 font-semibold text-xs w-8 text-right">{row.confidence}%</span>
                        </div>
                      </td>
                      <td className="py-2.5 text-right text-violet-600 text-xs font-semibold">{row.lift}x</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Underperforming Items */}
          <div className="card p-6">
            <div className="flex items-center gap-2 mb-5">
              <AlertTriangle size={15} className="text-amber-500" />
              <div>
                <h2 className="font-semibold text-surface-900 text-sm">Underperforming Items</h2>
                <p className="text-surface-400 text-xs">AI-generated improvement recommendations</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-200">
                    {['Item', 'Sales', 'Margin', 'Action'].map(h => (
                      <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100">
                  {underperformingItems.map((row, i) => {
                    const { cls, icon } = getRecBadge(row.recommendation)
                    return (
                      <tr key={i} className="hover:bg-surface-50 transition-colors">
                        <td className="py-2.5 pr-3 text-surface-900 font-medium text-xs">{row.name}</td>
                        <td className="py-2.5 pr-3">
                          <span className={`text-xs px-2 py-0.5 rounded-full border ${salesBadge[row.sales]}`}>{row.sales}</span>
                        </td>
                        <td className="py-2.5 pr-3">
                          <span className={`text-xs px-2 py-0.5 rounded-full border ${marginBadge[row.margin]}`}>{row.margin}</span>
                        </td>
                        <td className="py-2.5 text-xs text-surface-600 max-w-[220px] leading-snug">{row.recommendation}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── Tab: Popularity Scoring ── */}
      {activeTab === 'popularity' && (
        <div className="space-y-6">
          {/* Classification summary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {['Fast Mover', 'Normal', 'Slow Mover', 'Dead'].map(cls => {
              const count = popularityScores.filter(p => p.classification === cls).length
              return (
                <div key={cls} className="card p-4">
                  <div className="w-3 h-3 rounded-full mb-2" style={{ background: classColors[cls] }} />
                  <p className="text-2xl font-bold" style={{ color: classColors[cls] }}>{count}</p>
                  <p className="text-xs text-surface-400 mt-1">{cls}</p>
                </div>
              )
            })}
          </div>

          {/* Classification methodology */}
          <div className="card p-4 bg-surface-50 border border-surface-200">
            <p className="text-xs font-semibold text-surface-600 mb-2">How items are classified</p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="flex items-start gap-2">
                <span className="w-2.5 h-2.5 rounded-full mt-0.5 shrink-0" style={{ background: '#10b981' }} />
                <div><p className="font-semibold text-emerald-700">Fast Mover</p><p className="text-surface-500">Top 25% by units sold</p></div>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-2.5 h-2.5 rounded-full mt-0.5 shrink-0" style={{ background: '#6366f1' }} />
                <div><p className="font-semibold text-indigo-700">Normal</p><p className="text-surface-500">25th – 60th percentile</p></div>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-2.5 h-2.5 rounded-full mt-0.5 shrink-0" style={{ background: '#f59e0b' }} />
                <div><p className="font-semibold text-amber-700">Slow Mover</p><p className="text-surface-500">Bottom 40% by units sold</p></div>
              </div>
              <div className="flex items-start gap-2">
                <span className="w-2.5 h-2.5 rounded-full mt-0.5 shrink-0" style={{ background: '#94a3b8' }} />
                <div><p className="font-semibold text-surface-500">Dead</p><p className="text-surface-500">0 units sold in period</p></div>
              </div>
            </div>
          </div>

          {/* Bar chart: top 20 by sales */}
          <div className="card p-6">
            <h2 className="font-semibold text-surface-900 mb-1">Sales Velocity — Top 20 Items</h2>
            <p className="text-surface-400 text-xs mb-5">Total units sold · colour = mover classification</p>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart
                data={popularityScores.slice(0, 20)}
                margin={{ top: 5, right: 20, bottom: 70, left: 10 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} angle={-40} textAnchor="end" interval={0} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <Tooltip formatter={(v, name, props) => [v, 'Units Sold']} />
                <Bar dataKey="total_sold" radius={[4, 4, 0, 0]}>
                  {popularityScores.slice(0, 20).map((entry, i) => (
                    <Cell key={i} fill={classColors[entry.classification] || '#6366f1'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Full table */}
          <div className="card p-6 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-200">
                  {['Rank', 'Item', 'Category', 'Units Sold', 'Velocity/Day', 'Order Freq', 'Rank %', 'Classification'].map(h => (
                    <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-4">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100">
                {popularityScores.map((row, i) => (
                  <tr key={i} className="hover:bg-surface-50 transition-colors">
                    <td className="py-2.5 pr-4 text-surface-400 font-mono text-xs">#{row.rank}</td>
                    <td className="py-2.5 pr-4 text-surface-900 font-medium text-xs">{row.name}</td>
                    <td className="py-2.5 pr-4 text-surface-500 text-xs">{row.category}</td>
                    <td className="py-2.5 pr-4 text-primary-600 font-bold text-xs">{row.total_sold}</td>
                    <td className="py-2.5 pr-4 text-xs font-semibold text-surface-700">
                      {typeof row.velocity_per_day === 'number' ? `${row.velocity_per_day.toFixed(1)}/d` : '—'}
                    </td>
                    <td className="py-2.5 pr-4 text-surface-600 text-xs">{row.order_frequency}</td>
                    <td className="py-2.5 pr-4">
                      <div className="flex items-center gap-2">
                        <div className="w-12 h-1.5 bg-surface-200 rounded-full overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${row.rank_pct}%`, background: classColors[row.classification] }} />
                        </div>
                        <span className="text-xs text-surface-600">{row.rank_pct}%</span>
                      </div>
                    </td>
                    <td className="py-2.5">
                      <span className="text-xs px-2 py-0.5 rounded-full border font-semibold"
                        style={{ color: classColors[row.classification], borderColor: classColors[row.classification] + '55', background: classColors[row.classification] + '18' }}>
                        {row.classification}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Tab: Hidden Stars ── */}
      {activeTab === 'hiddenStars' && (
        <div className="space-y-4">
          <div className="card p-4 bg-violet-50 border border-violet-200">
            <div className="flex items-start gap-3">
              <Star size={16} className="text-violet-600 mt-0.5 shrink-0" />
              <div>
                <p className="text-violet-800 font-semibold text-sm">What are Hidden Stars?</p>
                <p className="text-violet-600 text-xs mt-0.5">
                  Items with <strong>above-median contribution margin</strong> but <strong>below-median sales velocity</strong>.
                  These are your most profitable undiscovered items — promote them to maximise revenue without raising costs.
                </p>
              </div>
            </div>
          </div>

          <div className="card p-6 overflow-x-auto">
            <h2 className="font-semibold text-surface-900 mb-1">Hidden Stars — {hiddenStars.count} Items Found</h2>
            <p className="text-surface-400 text-xs mb-5">Median contribution margin baseline: ₹{hiddenStars.median_cm}</p>
            {hiddenStars.items.length === 0 ? (
              <p className="text-center text-surface-400 py-8">No hidden stars detected — all high-margin items are already popular.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-200">
                    {['Item', 'Category', 'Avg Price', 'Margin %', 'CM / Unit', 'Units Sold', 'Ordered With', 'Action'].map(h => (
                      <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-4">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100">
                  {hiddenStars.items.map((row, i) => (
                    <tr key={i} className="hover:bg-surface-50 transition-colors">
                      <td className="py-2.5 pr-4 text-surface-900 font-medium text-xs">{row.name}</td>
                      <td className="py-2.5 pr-4 text-surface-500 text-xs">{row.category}</td>
                      <td className="py-2.5 pr-4 text-surface-700 text-xs">₹{row.avg_price}</td>
                      <td className="py-2.5 pr-4">
                        <span className="text-xs px-2 py-0.5 rounded-full border font-semibold text-violet-700 bg-violet-50 border-violet-200">
                          {row.margin_pct}%
                        </span>
                      </td>
                      <td className="py-2.5 pr-4 text-emerald-600 font-bold text-xs">₹{row.cm_per_unit}</td>
                      <td className="py-2.5 pr-4 text-surface-600 text-xs">{row.sales_velocity}</td>
                      <td className="py-2.5 pr-4">
                        {row.combo_partners?.length > 0 ? (
                          <div className="flex flex-wrap gap-1">
                            {row.combo_partners.map((p, j) => (
                              <span key={j} className="text-xs px-2 py-0.5 bg-violet-50 text-violet-700 rounded-full border border-violet-200">{p}</span>
                            ))}
                          </div>
                        ) : (
                          <span className="text-surface-300 text-xs">—</span>
                        )}
                      </td>
                      <td className="py-2.5 text-xs text-violet-600 font-medium max-w-[180px] leading-snug">{row.promotion_advice}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* ── Tab: Risk Detection ── */}
      {activeTab === 'risk' && (
        <div className="space-y-4">
          <div className="card p-4 bg-red-50 border border-red-200">
            <div className="flex items-start gap-3">
              <ShieldAlert size={16} className="text-red-600 mt-0.5 shrink-0" />
              <div>
                <p className="text-red-800 font-semibold text-sm">Low Margin · High Volume Risk</p>
                <p className="text-red-600 text-xs mt-0.5">
                  These items (BCG Plowhorses) drive high order volumes but have thin contribution margins.
                  Revenue is at risk if food costs rise. Risk Score = volume × margin gap.
                </p>
              </div>
            </div>
          </div>

          <div className="card p-6 overflow-x-auto">
            <h2 className="font-semibold text-surface-900 mb-1">At-Risk Items — {riskItems.count} Detected</h2>
            <p className="text-surface-400 text-xs mb-5">Sorted by risk score · highest first</p>
            {riskItems.items.length === 0 ? (
              <p className="text-center text-surface-400 py-8">No high-risk items — margin health looks good.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-200">
                    {['Item', 'Category', 'Units Sold', 'Margin %', 'CM/Unit', 'Revenue', 'Risk Score', 'Risk Level', 'Action'].map(h => (
                      <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100">
                  {riskItems.items.map((row, i) => (
                    <tr key={i} className={`hover:bg-surface-50 transition-colors ${row.risk_level === 'High' ? 'bg-red-50/50' : ''}`}>
                      <td className="py-2.5 pr-3 text-surface-900 font-medium text-xs">{row.name}</td>
                      <td className="py-2.5 pr-3 text-surface-500 text-xs">{row.category}</td>
                      <td className="py-2.5 pr-3 text-primary-600 font-bold text-xs">{row.sales_velocity}</td>
                      <td className="py-2.5 pr-3">
                        <span className="text-xs px-2 py-0.5 rounded-full border font-semibold text-red-700 bg-red-50 border-red-200">
                          {row.margin_pct}%
                        </span>
                      </td>
                      <td className="py-2.5 pr-3 text-surface-600 text-xs">₹{row.cm_per_unit}</td>
                      <td className="py-2.5 pr-3 text-surface-700 text-xs">₹{Number(row.total_revenue).toLocaleString()}</td>
                      <td className="py-2.5 pr-3">
                        <div className="flex items-center gap-2">
                          <div className="w-12 h-1.5 bg-surface-200 rounded-full overflow-hidden">
                            <div className="h-full bg-red-500 rounded-full" style={{ width: `${row.risk_score}%` }} />
                          </div>
                          <span className="text-xs font-bold text-red-600">{row.risk_score}</span>
                        </div>
                      </td>
                      <td className="py-2.5 pr-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${riskLevelColor[row.risk_level]}`}>
                          {row.risk_level}
                        </span>
                      </td>
                      <td className="py-2.5 text-xs text-surface-500 max-w-[180px]">{row.action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* ── Tab: ML Menu Optimization ── */}
      {activeTab === 'mlopt' && menuOpt && (
        <div className="space-y-4">
          <div className="card p-4 bg-emerald-50 border border-emerald-200">
            <div className="flex items-start gap-3">
              <DollarSign size={16} className="text-emerald-600 mt-0.5 shrink-0" />
              <div>
                <p className="text-emerald-800 font-semibold text-sm">ML-Powered Price Optimization</p>
                <p className="text-emerald-600 text-xs mt-0.5">
                  BCG classification + price elasticity analysis · {menuOpt.price_recommendations?.length || 0} items
                  {' · '}{menuOpt.fpgrowth_combos?.length || 0} FP-Growth combos detected
                </p>
              </div>
            </div>
          </div>

          {/* Price Recommendations */}
          <div className="card p-6 overflow-x-auto">
            <h2 className="font-semibold text-surface-900 mb-1">Price Recommendations</h2>
            <p className="text-surface-400 text-xs mb-5">ML-driven suggested prices based on BCG class, margin, and elasticity</p>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-200">
                  {['Item', 'Category', 'BCG Class', 'Current Price', 'Suggested Price', 'Change', 'Margin %', 'Action'].map(h => (
                    <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100">
                {(menuOpt.price_recommendations || []).map((row, i) => {
                  const badge = getRecBadge(row.action)
                  return (
                    <tr key={i} className="hover:bg-surface-50 transition-colors">
                      <td className="py-2.5 pr-3 text-surface-900 font-medium text-xs">{row.name}</td>
                      <td className="py-2.5 pr-3 text-surface-500 text-xs">{row.category}</td>
                      <td className="py-2.5 pr-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${
                          row.bcg_class === 'Star' ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
                          : row.bcg_class === 'Puzzle' ? 'text-violet-700 bg-violet-50 border-violet-200'
                          : row.bcg_class === 'Dog' ? 'text-red-700 bg-red-50 border-red-200'
                          : 'text-amber-700 bg-amber-50 border-amber-200'
                        }`}>{row.bcg_class}</span>
                      </td>
                      <td className="py-2.5 pr-3 text-surface-700 text-xs">₹{row.current_price}</td>
                      <td className="py-2.5 pr-3 text-primary-600 font-bold text-xs">₹{row.suggested_price}</td>
                      <td className="py-2.5 pr-3">
                        <span className={`text-xs font-bold ${row.price_change_pct > 0 ? 'text-emerald-600' : row.price_change_pct < 0 ? 'text-red-600' : 'text-surface-400'}`}>
                          {row.price_change_pct > 0 ? '+' : ''}{row.price_change_pct}%
                        </span>
                      </td>
                      <td className="py-2.5 pr-3 text-surface-600 text-xs">{row.margin_pct}%</td>
                      <td className="py-2.5">
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${badge.cls}`}>
                          {badge.icon} {row.action}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* FP-Growth Combos */}
          {(menuOpt.fpgrowth_combos || []).filter(c => c.size > 1).length > 0 && (
            <div className="card p-6 overflow-x-auto">
              <h2 className="font-semibold text-surface-900 mb-1">FP-Growth Frequent Itemsets</h2>
              <p className="text-surface-400 text-xs mb-5">Item combinations frequently ordered together (min support 2%)</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {(menuOpt.fpgrowth_combos || []).filter(c => c.size > 1).map((combo, i) => (
                  <div key={i} className="p-3 rounded-lg border border-surface-200 bg-surface-50">
                    <div className="flex items-center gap-2 flex-wrap">
                      {(Array.isArray(combo.items) ? combo.items : [combo.items]).map((item, j) => (
                        <span key={j} className="text-xs px-2 py-1 rounded-full bg-violet-100 text-violet-700 font-medium">{item}</span>
                      ))}
                    </div>
                    <p className="text-xs text-surface-400 mt-2">Support: {(combo.support * 100).toFixed(1)}%</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Upsell Pairs */}
          {(menuOpt.upsell_pairs || []).length > 0 && (
            <div className="card p-6 overflow-x-auto">
              <h2 className="font-semibold text-surface-900 mb-1">Top Upsell Pairs</h2>
              <p className="text-surface-400 text-xs mb-5">Items frequently co-ordered · sorted by co-occurrence count</p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-200">
                    {['Item A', 'Item B', 'Co-occurrences', 'Lift'].map(h => (
                      <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-100">
                  {(menuOpt.upsell_pairs || []).slice(0, 20).map((row, i) => (
                    <tr key={i} className="hover:bg-surface-50 transition-colors">
                      <td className="py-2.5 pr-3 text-surface-900 font-medium text-xs">{row.name_a}</td>
                      <td className="py-2.5 pr-3 text-surface-900 font-medium text-xs">{row.name_b}</td>
                      <td className="py-2.5 pr-3 text-primary-600 font-bold text-xs">{row.co_occurrences}</td>
                      <td className="py-2.5 pr-3 text-violet-600 font-semibold text-xs">{Number(row.lift).toFixed(3)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

import { useState, useEffect } from 'react'
import { apiFetch } from '../config'
import { AlertTriangle, Package, TrendingUp, Zap, ClipboardList, Plus, RotateCcw, X } from 'lucide-react'

const urgencyColor = {
  High: 'text-red-700 bg-red-50 border-red-200',
  Medium: 'text-amber-700 bg-amber-50 border-amber-200',
  Low: 'text-emerald-700 bg-emerald-50 border-emerald-200',
}
const bcgColor = {
  Star: 'text-emerald-700 bg-emerald-50 border-emerald-200',
  Puzzle: 'text-violet-700 bg-violet-50 border-violet-200',
  Plowhorse: 'text-red-700 bg-red-50 border-red-200',
  Dog: 'text-amber-700 bg-amber-50 border-amber-200',
}

export default function Inventory() {
  const [signals, setSignals] = useState([])
  const [alerts, setAlerts] = useState([])
  const [stock, setStock] = useState([])
  const [log, setLog] = useState([])
  const [tab, setTab] = useState('signals')
  const [stockFilter, setStockFilter] = useState('')
  const [restockModal, setRestockModal] = useState(null)   // { ing_id, name, unit }
  const [restockQty, setRestockQty] = useState('')
  const [restockReason, setRestockReason] = useState('')
  const [showAddModal, setShowAddModal] = useState(false)
  const [newIng, setNewIng] = useState({ name: '', unit: 'kg', current_stock: '', min_stock: '', reorder_qty: '', cost_per_unit: '' })
  const [saving, setSaving] = useState(false)

  const reload = () => {
    Promise.all([
      apiFetch('/inventory/performance-signals').catch(() => ({ signals: [], low_stock_count: 0 })),
      apiFetch('/inventory/alerts').catch(() => []),
      apiFetch('/inventory/stock').catch(() => []),
      apiFetch('/inventory/log').catch(() => []),
    ]).then(([ps, al, st, lg]) => {
      setSignals(ps?.signals || [])
      setAlerts(Array.isArray(al) ? al : [])
      setStock(Array.isArray(st) ? st : [])
      setLog(Array.isArray(lg) ? lg : [])
    })
  }

  useEffect(() => { reload() }, [])

  const handleRestock = async () => {
    if (!restockQty || Number(restockQty) <= 0) return
    setSaving(true)
    try {
      await apiFetch('/inventory/restock', {
        method: 'POST',
        body: JSON.stringify({ ing_id: restockModal.ing_id, qty: Number(restockQty), reason: restockReason || 'Manual restock' }),
      })
      setRestockModal(null)
      setRestockQty('')
      setRestockReason('')
      reload()
    } catch (e) { console.error(e) }
    setSaving(false)
  }

  const handleAddIngredient = async () => {
    if (!newIng.name || !newIng.unit) return
    setSaving(true)
    try {
      await apiFetch('/inventory/ingredients', {
        method: 'POST',
        body: JSON.stringify({
          name: newIng.name,
          unit: newIng.unit,
          current_stock: Number(newIng.current_stock) || 0,
          min_stock: Number(newIng.min_stock) || 0,
          reorder_qty: Number(newIng.reorder_qty) || 0,
          cost_per_unit: Number(newIng.cost_per_unit) || 0,
        }),
      })
      setShowAddModal(false)
      setNewIng({ name: '', unit: 'kg', current_stock: '', min_stock: '', reorder_qty: '', cost_per_unit: '' })
      reload()
    } catch (e) { console.error(e) }
    setSaving(false)
  }

  const highUrgencyCount = signals.filter(s => s.urgency === 'High').length
  const filteredStock = stock.filter(s => s.name.toLowerCase().includes(stockFilter.toLowerCase()))

  const tabs = [
    { id: 'signals', label: 'Performance Signals', icon: TrendingUp },
    { id: 'alerts', label: `Low Stock Alerts (${alerts.length})`, icon: AlertTriangle },
    { id: 'stock', label: 'Full Stock View', icon: Package },
    { id: 'log', label: `Activity Log (${log.length})`, icon: ClipboardList },
  ]

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-surface-900">Inventory Intelligence</h1>
        <p className="text-surface-400 text-sm mt-0.5">Inventory-linked performance signals · stock health · reorder alerts</p>
      </div>

      {/* Action buttons */}
      <div className="flex gap-3">
        <button onClick={() => setShowAddModal(true)} className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors">
          <Plus size={16} /> Add Ingredient
        </button>
      </div>

      {/* KPI strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Items at Risk', value: signals.length, color: 'text-red-600', icon: AlertTriangle },
          { label: 'High Urgency', value: highUrgencyCount, color: 'text-red-500', icon: Zap },
          { label: 'Low Stock Ingredients', value: alerts.length, color: 'text-amber-600', icon: Package },
          { label: 'Total SKUs Tracked', value: stock.length, color: 'text-primary-600', icon: Package },
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

      {/* ── Tab: Performance Signals ── */}
      {tab === 'signals' && (
        <div className="card p-6 overflow-x-auto">
          <h2 className="font-semibold text-surface-900 mb-1">Menu Items at Supply Risk</h2>
          <p className="text-surface-400 text-xs mb-5">
            Star &amp; Plowhorse items affected by low-stock ingredients — action needed to prevent revenue loss
          </p>
          {signals.length === 0 ? (
            <div className="py-12 text-center">
              <Package size={32} className="text-emerald-400 mx-auto mb-3" />
              <p className="text-emerald-600 font-semibold">All clear — no supply risk detected</p>
              <p className="text-surface-400 text-sm mt-1">All ingredients are above minimum stock levels.</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-200">
                  {['Menu Item', 'Category', 'BCG Class', 'Sales', 'Low Ingredient', 'Stock %', 'Urgency', 'Action'].map(h => (
                    <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100">
                {signals.map((row, i) => (
                  <tr key={i} className={`hover:bg-surface-50 transition-colors ${row.urgency === 'High' ? 'bg-red-50/50' : ''}`}>
                    <td className="py-2.5 pr-3 text-surface-900 font-medium text-xs">{row.item_name}</td>
                    <td className="py-2.5 pr-3 text-surface-500 text-xs">{row.category}</td>
                    <td className="py-2.5 pr-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${bcgColor[row.bcg_class] || 'text-surface-600 bg-surface-50 border-surface-200'}`}>
                        {row.bcg_class}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3 text-surface-700 text-xs">{row.sales_velocity} units</td>
                    <td className="py-2.5 pr-3 text-red-600 font-medium text-xs">{row.ingredient}</td>
                    <td className="py-2.5 pr-3">
                      <div className="flex items-center gap-2">
                        <div className="w-14 h-1.5 bg-surface-200 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${row.stock_pct < 25 ? 'bg-red-500' : 'bg-amber-400'}`}
                            style={{ width: `${Math.min(row.stock_pct, 100)}%` }}
                          />
                        </div>
                        <span className="text-xs text-surface-600">{row.stock_pct}%</span>
                      </div>
                    </td>
                    <td className="py-2.5 pr-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${urgencyColor[row.urgency]}`}>
                        {row.urgency}
                      </span>
                    </td>
                    <td className="py-2.5 text-xs text-surface-500">Reorder {row.ingredient} immediately</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Tab: Low Stock Alerts ── */}
      {tab === 'alerts' && (
        <div className="card p-6 overflow-x-auto">
          <h2 className="font-semibold text-surface-900 mb-1">Ingredients Below Minimum Stock</h2>
          <p className="text-surface-400 text-xs mb-5">Sorted by stock % — most critical first</p>
          {alerts.length === 0 ? (
            <div className="py-12 text-center">
              <Package size={32} className="text-emerald-400 mx-auto mb-3" />
              <p className="text-emerald-600 font-semibold">All ingredients are well-stocked</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-200">
                  {['Ingredient', 'Unit', 'Current Stock', 'Min Stock', 'Stock Level', 'Reorder Qty', 'Last Restocked', 'Action'].map(h => (
                    <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100">
                {alerts.map((row, i) => {
                  const pct = row.min_stock > 0 ? Math.round((row.current_stock / row.min_stock) * 100) : 0
                  return (
                    <tr key={i} className="hover:bg-surface-50 transition-colors">
                      <td className="py-2.5 pr-3 text-surface-900 font-medium text-xs">{row.name}</td>
                      <td className="py-2.5 pr-3 text-surface-500 text-xs">{row.unit}</td>
                      <td className="py-2.5 pr-3 text-red-600 font-bold text-xs">{row.current_stock}</td>
                      <td className="py-2.5 pr-3 text-surface-600 text-xs">{row.min_stock}</td>
                      <td className="py-2.5 pr-3">
                        <div className="flex items-center gap-2">
                          <div className="w-14 h-1.5 bg-surface-200 rounded-full overflow-hidden">
                            <div className="h-full bg-red-500 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
                          </div>
                          <span className="text-xs text-red-600 font-semibold">{pct}%</span>
                        </div>
                      </td>
                      <td className="py-2.5 pr-3 text-amber-600 font-semibold text-xs">{row.reorder_qty} {row.unit}</td>
                      <td className="py-2.5 pr-3 text-surface-400 text-xs">
                        {row.last_restocked_at ? new Date(row.last_restocked_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="py-2.5">
                        <button
                          onClick={() => { setRestockModal({ ing_id: row.ing_id, name: row.name, unit: row.unit }); setRestockQty(String(row.reorder_qty || '')) }}
                          className="flex items-center gap-1 text-xs px-2.5 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-md hover:bg-emerald-100 transition-colors font-medium"
                        >
                          <RotateCcw size={12} /> Restock
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Tab: Full Stock View ── */}
      {tab === 'stock' && (
        <div className="card p-6 overflow-x-auto">
          <div className="flex items-center justify-between mb-5 gap-4 flex-wrap">
            <div>
              <h2 className="font-semibold text-surface-900">All Ingredients Stock Overview</h2>
              <p className="text-surface-400 text-xs mt-0.5">{stock.length} ingredients tracked</p>
            </div>
            <input
              type="text"
              placeholder="Search ingredient..."
              value={stockFilter}
              onChange={e => setStockFilter(e.target.value)}
              className="border border-surface-200 rounded-lg px-3 py-1.5 text-sm text-surface-700 placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-primary-300 w-56"
            />
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-200">
                {['Ingredient', 'Unit', 'Current Stock', 'Min Stock', 'Health', 'Cost/Unit', 'Reorder Qty', 'Action'].map(h => (
                  <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {filteredStock.map((row, i) => {
                const ok = row.current_stock >= row.min_stock
                const pct = row.min_stock > 0 ? Math.round((row.current_stock / row.min_stock) * 100) : 100
                return (
                  <tr key={i} className="hover:bg-surface-50 transition-colors">
                    <td className="py-2.5 pr-3 text-surface-900 font-medium text-xs">{row.name}</td>
                    <td className="py-2.5 pr-3 text-surface-500 text-xs">{row.unit}</td>
                    <td className={`py-2.5 pr-3 font-bold text-xs ${ok ? 'text-emerald-600' : 'text-red-600'}`}>{row.current_stock}</td>
                    <td className="py-2.5 pr-3 text-surface-600 text-xs">{row.min_stock}</td>
                    <td className="py-2.5 pr-3">
                      <div className="flex items-center gap-2">
                        <div className="w-14 h-1.5 bg-surface-200 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${ok ? 'bg-emerald-500' : 'bg-red-500'}`}
                            style={{ width: `${Math.min(pct, 100)}%` }} />
                        </div>
                        <span className={`text-xs font-semibold ${ok ? 'text-emerald-600' : 'text-red-600'}`}>{pct}%</span>
                      </div>
                    </td>
                    <td className="py-2.5 pr-3 text-surface-600 text-xs">₹{row.cost_per_unit}</td>
                    <td className="py-2.5 pr-3 text-surface-600 text-xs">{row.reorder_qty} {row.unit}</td>
                    <td className="py-2.5">
                      <button
                        onClick={() => setRestockModal({ ing_id: row.ing_id, name: row.name, unit: row.unit })}
                        className="flex items-center gap-1 text-xs px-2.5 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-md hover:bg-emerald-100 transition-colors font-medium"
                      >
                        <RotateCcw size={12} /> Restock
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Tab: Activity Log ── */}
      {tab === 'log' && (
        <div className="card p-6 overflow-x-auto">
          <h2 className="font-semibold text-surface-900 mb-1">Inventory Change History</h2>
          <p className="text-surface-400 text-xs mb-5">Recent stock movements — restocks, usage, wastage & adjustments</p>
          {log.length === 0 ? (
            <div className="py-12 text-center">
              <ClipboardList size={32} className="text-surface-300 mx-auto mb-3" />
              <p className="text-surface-500 font-semibold">No activity logged yet</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-200">
                  {['#', 'Ingredient', 'Change Type', 'Qty Changed', 'Reason', 'Logged At'].map(h => (
                    <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100">
                {log.map((row, i) => {
                  const typeColors = {
                    restock: 'text-emerald-700 bg-emerald-50 border-emerald-200',
                    usage: 'text-blue-700 bg-blue-50 border-blue-200',
                    wastage: 'text-red-700 bg-red-50 border-red-200',
                    adjustment: 'text-amber-700 bg-amber-50 border-amber-200',
                  }
                  const color = typeColors[row.change_type] || 'text-surface-600 bg-surface-50 border-surface-200'
                  return (
                    <tr key={row.log_id || i} className="hover:bg-surface-50 transition-colors">
                      <td className="py-2.5 pr-3 text-surface-400 text-xs">{row.log_id}</td>
                      <td className="py-2.5 pr-3 text-surface-900 font-medium text-xs">{row.ingredient}</td>
                      <td className="py-2.5 pr-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${color}`}>
                          {row.change_type}
                        </span>
                      </td>
                      <td className={`py-2.5 pr-3 font-bold text-xs ${row.qty_changed >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                        {row.qty_changed >= 0 ? '+' : ''}{row.qty_changed}
                      </td>
                      <td className="py-2.5 pr-3 text-surface-500 text-xs">{row.reason || '—'}</td>
                      <td className="py-2.5 text-surface-400 text-xs">
                        {row.logged_at ? new Date(row.logged_at).toLocaleString() : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Restock Modal ── */}
      {restockModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6 relative animate-fade-in">
            <button onClick={() => { setRestockModal(null); setRestockQty(''); setRestockReason('') }} className="absolute top-4 right-4 text-surface-400 hover:text-surface-600"><X size={18} /></button>
            <h3 className="text-lg font-bold text-surface-900 mb-1">Restock {restockModal.name}</h3>
            <p className="text-surface-400 text-sm mb-5">Add stock quantity in {restockModal.unit}</p>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium text-surface-700 block mb-1">Quantity ({restockModal.unit})</label>
                <input type="number" min="0.001" step="any" value={restockQty} onChange={e => setRestockQty(e.target.value)}
                  className="w-full border border-surface-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300" placeholder="e.g. 10" autoFocus />
              </div>
              <div>
                <label className="text-sm font-medium text-surface-700 block mb-1">Reason (optional)</label>
                <input type="text" value={restockReason} onChange={e => setRestockReason(e.target.value)}
                  className="w-full border border-surface-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300" placeholder="e.g. Weekly purchase" />
              </div>
              <button onClick={handleRestock} disabled={saving || !restockQty}
                className="w-full py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-semibold hover:bg-emerald-700 disabled:opacity-50 transition-colors">
                {saving ? 'Restocking...' : 'Confirm Restock'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Add Ingredient Modal ── */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 relative animate-fade-in">
            <button onClick={() => setShowAddModal(false)} className="absolute top-4 right-4 text-surface-400 hover:text-surface-600"><X size={18} /></button>
            <h3 className="text-lg font-bold text-surface-900 mb-5">Add New Ingredient</h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <label className="text-sm font-medium text-surface-700 block mb-1">Name *</label>
                <input type="text" value={newIng.name} onChange={e => setNewIng({ ...newIng, name: e.target.value })}
                  className="w-full border border-surface-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300" placeholder="e.g. Saffron" autoFocus />
              </div>
              <div>
                <label className="text-sm font-medium text-surface-700 block mb-1">Unit *</label>
                <select value={newIng.unit} onChange={e => setNewIng({ ...newIng, unit: e.target.value })}
                  className="w-full border border-surface-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300">
                  {['kg', 'grams', 'litre', 'ml', 'pieces'].map(u => <option key={u} value={u}>{u}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-surface-700 block mb-1">Cost per Unit (₹)</label>
                <input type="number" min="0" step="any" value={newIng.cost_per_unit} onChange={e => setNewIng({ ...newIng, cost_per_unit: e.target.value })}
                  className="w-full border border-surface-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300" placeholder="0" />
              </div>
              <div>
                <label className="text-sm font-medium text-surface-700 block mb-1">Initial Stock</label>
                <input type="number" min="0" step="any" value={newIng.current_stock} onChange={e => setNewIng({ ...newIng, current_stock: e.target.value })}
                  className="w-full border border-surface-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300" placeholder="0" />
              </div>
              <div>
                <label className="text-sm font-medium text-surface-700 block mb-1">Min Stock</label>
                <input type="number" min="0" step="any" value={newIng.min_stock} onChange={e => setNewIng({ ...newIng, min_stock: e.target.value })}
                  className="w-full border border-surface-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300" placeholder="0" />
              </div>
              <div>
                <label className="text-sm font-medium text-surface-700 block mb-1">Reorder Qty</label>
                <input type="number" min="0" step="any" value={newIng.reorder_qty} onChange={e => setNewIng({ ...newIng, reorder_qty: e.target.value })}
                  className="w-full border border-surface-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300" placeholder="0" />
              </div>
            </div>
            <button onClick={handleAddIngredient} disabled={saving || !newIng.name || !newIng.unit}
              className="w-full mt-5 py-2.5 bg-primary-600 text-white rounded-lg text-sm font-semibold hover:bg-primary-700 disabled:opacity-50 transition-colors">
              {saving ? 'Adding...' : 'Add Ingredient'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

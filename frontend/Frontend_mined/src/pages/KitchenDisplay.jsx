import { useState, useEffect } from 'react'
import { apiFetch } from '../config'
import { ChefHat, Clock, AlertTriangle, Flame, Play, CheckCheck } from 'lucide-react'

const priorityStyle = {
  urgent: 'border-red-400 bg-red-50',
  high: 'border-amber-400 bg-amber-50',
  normal: 'border-surface-200 bg-white',
}
const priorityBadge = {
  urgent: 'text-red-700 bg-red-100 border-red-300',
  high: 'text-amber-700 bg-amber-100 border-amber-300',
  normal: 'text-surface-600 bg-surface-100 border-surface-200',
}
const statusBadge = {
  pending: 'text-amber-700 bg-amber-50 border-amber-200',
  preparing: 'text-blue-700 bg-blue-50 border-blue-200',
}

function elapsed(createdAt) {
  const diff = Math.floor((Date.now() - new Date(createdAt).getTime()) / 1000)
  if (diff < 60) return `${diff}s`
  if (diff < 3600) return `${Math.floor(diff / 60)}m`
  return `${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}m`
}

export default function KitchenDisplay() {
  const [kots, setKots] = useState([])
  const [loading, setLoading] = useState(true)
  const [updatingId, setUpdatingId] = useState(null)

  const fetchKots = () => {
    apiFetch('/kot/pending')
      .then(data => setKots(Array.isArray(data) ? data : []))
      .catch(() => setKots([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchKots()
    const interval = setInterval(fetchKots, 5000)
    return () => clearInterval(interval)
  }, [])

  const updateStatus = async (kotId, newStatus) => {
    setUpdatingId(kotId)
    try {
      await apiFetch(`/kot/${kotId}/status`, {
        method: 'PUT',
        body: JSON.stringify({ status: newStatus }),
      })
      if (newStatus === 'ready') {
        // Remove from display once ready
        setKots(prev => prev.filter(k => k.kot_id !== kotId))
      } else {
        setKots(prev => prev.map(k => k.kot_id === kotId ? { ...k, status: newStatus } : k))
      }
    } catch {
      // silently ignore — will re-sync on next 15s poll
    } finally {
      setUpdatingId(null)
    }
  }

  const pendingCount = kots.filter(k => k.status === 'pending').length
  const preparingCount = kots.filter(k => k.status === 'preparing').length

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 flex items-center gap-2">
            <ChefHat size={24} className="text-primary-600" />
            Kitchen Display
          </h1>
          <p className="text-surface-400 text-sm mt-0.5">Live KOT queue — auto-refreshes every 5s</p>
        </div>
        <div className="flex gap-3">
          <div className="card px-4 py-2 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            <span className="text-sm font-medium text-surface-700">{pendingCount} Pending</span>
          </div>
          <div className="card px-4 py-2 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
            <span className="text-sm font-medium text-surface-700">{preparingCount} Preparing</span>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="py-20 text-center">
          <div className="animate-spin mx-auto w-8 h-8 border-2 border-primary-200 border-t-primary-600 rounded-full" />
          <p className="text-surface-400 text-sm mt-4">Loading KOTs...</p>
        </div>
      ) : kots.length === 0 ? (
        <div className="py-20 text-center">
          <ChefHat size={48} className="text-emerald-300 mx-auto mb-4" />
          <p className="text-emerald-600 font-semibold text-lg">Kitchen Clear</p>
          <p className="text-surface-400 text-sm mt-1">No pending or preparing orders right now.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {kots.map(kot => (
            <div
              key={kot.kot_id}
              className={`rounded-xl border-2 p-5 shadow-card transition-all hover:shadow-lg ${priorityStyle[kot.priority] || priorityStyle.normal}`}
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-surface-900 font-bold text-sm">KOT #{kot.kot_id}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full border font-semibold ${statusBadge[kot.status] || ''}`}>
                    {kot.status}
                  </span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full border font-semibold flex items-center gap-1 ${priorityBadge[kot.priority] || priorityBadge.normal}`}>
                  {kot.priority === 'urgent' && <Flame size={10} />}
                  {kot.priority}
                </span>
              </div>

              {/* Meta */}
              <div className="flex items-center gap-4 text-xs text-surface-400 mb-4">
                <span>Order #{kot.order_id}</span>
                <span className="flex items-center gap-1">
                  <Clock size={11} />
                  {elapsed(kot.created_at)} ago
                </span>
              </div>

              {/* Items */}
              <div className="space-y-2">
                {(kot.items || []).map((item, i) => (
                  <div key={i} className="flex items-start justify-between bg-white/60 rounded-lg px-3 py-2 border border-surface-100">
                    <div className="flex-1">
                      <p className="text-surface-900 font-medium text-sm">
                        <span className="text-primary-600 font-bold mr-1">{item.qty}x</span>
                        {item.item_name}
                      </p>
                      {item.variant_name && (
                        <p className="text-surface-400 text-xs mt-0.5">Variant: {item.variant_name}</p>
                      )}
                      {item.addons && (
                        <p className="text-violet-500 text-xs mt-0.5">+ {item.addons}</p>
                      )}
                      {item.special_instructions && (
                        <p className="text-amber-600 text-xs mt-0.5 flex items-center gap-1">
                          <AlertTriangle size={10} />
                          {item.special_instructions}
                        </p>
                      )}
                    </div>
                    {item.status && (
                      <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ml-2 shrink-0 ${
                        item.status === 'pending' ? 'text-amber-600 bg-amber-50 border-amber-200' : 'text-blue-600 bg-blue-50 border-blue-200'
                      }`}>
                        {item.status}
                      </span>
                    )}
                  </div>
                ))}
              </div>

              {/* Status Action Button */}
              <div className="mt-4 pt-3 border-t border-surface-100">
                {kot.status === 'pending' ? (
                  <button
                    onClick={() => updateStatus(kot.kot_id, 'preparing')}
                    disabled={updatingId === kot.kot_id}
                    className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold text-sm py-2 rounded-lg transition-colors"
                  >
                    <Play size={13} />
                    {updatingId === kot.kot_id ? 'Updating…' : 'Start Preparing'}
                  </button>
                ) : kot.status === 'preparing' ? (
                  <button
                    onClick={() => updateStatus(kot.kot_id, 'ready')}
                    disabled={updatingId === kot.kot_id}
                    className="w-full flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-semibold text-sm py-2 rounded-lg transition-colors"
                  >
                    <CheckCheck size={13} />
                    {updatingId === kot.kot_id ? 'Updating…' : 'Mark Ready'}
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

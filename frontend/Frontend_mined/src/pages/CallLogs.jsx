import { useState, useEffect, useCallback } from 'react'
import {
  Phone,
  PhoneOff,
  PhoneCall,
  CheckCircle2,
  Clock,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  ShoppingBag,
  AlertCircle,
} from 'lucide-react'
import { API_URL } from '../config'

function formatDuration(start, end) {
  if (!start) return '—'
  const s = new Date(start)
  const e = end ? new Date(end) : new Date()
  const secs = Math.floor((e - s) / 1000)
  if (secs < 60) return `${secs}s`
  const m = Math.floor(secs / 60)
  const r = secs % 60
  return `${m}m ${r}s`
}

function formatTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('en-IN', {
    day:    '2-digit',
    month:  'short',
    year:   'numeric',
    hour:   '2-digit',
    minute: '2-digit',
    hour12: true,
  })
}

function StatusBadge({ status }) {
  const map = {
    in_progress:     { label: 'In Progress',  cls: 'bg-amber-100  text-amber-700  border-amber-200',  Icon: PhoneCall },
    order_confirmed: { label: 'Order Placed', cls: 'bg-emerald-100 text-emerald-700 border-emerald-200', Icon: CheckCircle2 },
    completed:       { label: 'Completed',    cls: 'bg-blue-100   text-blue-700   border-blue-200',   Icon: Phone },
    failed:          { label: 'Failed',       cls: 'bg-red-100    text-red-700    border-red-200',    Icon: PhoneOff },
    cancelled:       { label: 'Cancelled',    cls: 'bg-surface-100 text-surface-500 border-surface-200', Icon: PhoneOff },
  }
  const { label, cls, Icon } = map[status] || { label: status, cls: 'bg-surface-100 text-surface-500 border-surface-200', Icon: Phone }
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full border font-medium ${cls}`}>
      <Icon size={10} />
      {label}
    </span>
  )
}

function CallRow({ log }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border border-surface-200 rounded-lg overflow-hidden animate-fade-in">
      {/* Summary row */}
      <button
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center gap-4 px-5 py-3.5 hover:bg-surface-50 transition-colors text-left"
      >
        <div className="w-8 h-8 rounded-full bg-primary-50 border border-primary-100 flex items-center justify-center shrink-0">
          <Phone size={14} className="text-primary-600" />
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-surface-900 truncate">
            {log.caller || log.call_sid?.slice(0, 20) || 'Unknown caller'}
          </p>
          <p className="text-xs text-surface-400">{formatTime(log.start_time)}</p>
        </div>

        <div className="flex items-center gap-4 shrink-0">
          {log.order_number && (
            <div className="flex items-center gap-1 text-xs text-emerald-600 font-medium">
              <ShoppingBag size={11} />
              #{log.order_number}
            </div>
          )}
          {log.order_total && (
            <span className="text-sm font-bold text-surface-900">
              ₹{log.order_total.toFixed(0)}
            </span>
          )}
          <div className="flex items-center gap-1 text-xs text-surface-400">
            <Clock size={11} />
            {formatDuration(log.start_time, log.end_time)}
          </div>
          <span className="text-xs text-surface-400">{log.turns || 0} turns</span>
          <StatusBadge status={log.status} />
          {expanded ? <ChevronUp size={14} className="text-surface-400" /> : <ChevronDown size={14} className="text-surface-400" />}
        </div>
      </button>

      {/* Expanded transcript */}
      {expanded && (
        <div className="border-t border-surface-100 bg-surface-50 px-5 py-4 space-y-3">
          <p className="text-[10px] uppercase tracking-widest text-surface-400 font-semibold mb-2">Conversation Transcript</p>
          {(log.transcript || []).length === 0 ? (
            <p className="text-xs text-surface-400 italic">No transcript recorded.</p>
          ) : (
            <div className="space-y-2.5">
              {log.transcript.map((t, i) => (
                <div key={i} className="space-y-1">
                  {t.customer && (
                    <div className="flex items-start gap-2">
                      <span className="text-[10px] font-bold text-primary-500 uppercase w-14 shrink-0 mt-0.5">Customer</span>
                      <span className="text-xs text-surface-700 bg-white rounded px-2 py-1 border border-surface-200 flex-1">{t.customer}</span>
                    </div>
                  )}
                  {t.aria && (
                    <div className="flex items-start gap-2">
                      <span className="text-[10px] font-bold text-violet-500 uppercase w-14 shrink-0 mt-0.5">Aria</span>
                      <span className="text-xs text-surface-700 bg-violet-50 rounded px-2 py-1 border border-violet-100 flex-1">{t.aria}</span>
                    </div>
                  )}
                  {t.intent && t.intent !== 'greeting' && t.intent !== 'unknown' && (
                    <div className="flex justify-end">
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-200 text-surface-500 font-mono">{t.intent}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          <div className="pt-2 border-t border-surface-200 text-xs text-surface-400 flex flex-wrap gap-x-6 gap-y-1">
            <span>Call SID: <span className="font-mono text-surface-600">{log.call_sid}</span></span>
            <span>Start: {formatTime(log.start_time)}</span>
            {log.end_time && <span>End: {formatTime(log.end_time)}</span>}
          </div>
        </div>
      )}
    </div>
  )
}

export default function CallLogs() {
  const [logs,    setLogs]    = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  // ── stats must be defined BEFORE useEffect (which reads stats.active) ──
  const stats = {
    total:    logs.length,
    active:   logs.filter(l => l.status === 'in_progress').length,
    orders:   logs.filter(l => l.status === 'order_confirmed').length,
    revenue:  logs.reduce((s, l) => s + (l.order_total || 0), 0),
  }

  const fetchLogs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const token   = localStorage.getItem('token')
      const headers = token ? { Authorization: `Bearer ${token}` } : {}

      // Fetch live in-memory call logs (Python service) + persistent DB voice orders in parallel
      const [liveRes, histRes] = await Promise.allSettled([
        fetch(`${API_URL}/voice/call-logs?limit=100`,    { headers }),
        fetch(`${API_URL}/voice/phone-orders?limit=100`, { headers }),
      ])

      const live = (liveRes.status === 'fulfilled' && liveRes.value.ok)
        ? await liveRes.value.json() : []
      const hist = (histRes.status === 'fulfilled' && histRes.value.ok)
        ? await histRes.value.json() : []

      // Merge: live entries (with transcripts) take priority.
      // Add DB entries that are older than the oldest live entry so we don't duplicate
      // confirmed calls that are both in Python memory and the DB.
      const merged = Array.isArray(live) ? [...live] : []
      const oldestLiveTime = merged.length > 0
        ? Math.min(...merged.map(l => new Date(l.start_time || 0).getTime()))
        : Infinity

      if (Array.isArray(hist)) {
        for (const h of hist) {
          if (new Date(h.start_time || 0).getTime() < oldestLiveTime) {
            merged.push(h)
          }
        }
      }

      // Newest first
      merged.sort((a, b) => new Date(b.start_time || 0) - new Date(a.start_time || 0))
      setLogs(merged)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchLogs()
    // Poll faster when a live call is in progress
    const intervalMs = stats.active > 0 ? 5_000 : 15_000
    const id = setInterval(fetchLogs, intervalMs)
    return () => clearInterval(id)
  }, [fetchLogs, stats.active])

  return (
    <div className="p-6 animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-surface-900">Call Logs</h1>
          <p className="text-surface-400 text-sm mt-0.5">Inbound AI phone ordering history</p>
        </div>
        <button
          onClick={fetchLogs}
          disabled={loading}
          className="btn-ghost flex items-center gap-2 text-sm"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[
          { label: 'Total Calls',    value: stats.total,                       cls: 'text-surface-900' },
          { label: 'Active Now',     value: stats.active,                      cls: 'text-amber-600' },
          { label: 'Orders Placed',  value: stats.orders,                      cls: 'text-emerald-600' },
          { label: 'Phone Revenue',  value: `₹${stats.revenue.toFixed(0)}`,   cls: 'text-primary-600' },
        ].map(({ label, value, cls }) => (
          <div key={label} className="card p-4">
            <p className="text-xs text-surface-400 mb-1">{label}</p>
            <p className={`text-2xl font-bold ${cls}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 flex items-center gap-2 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
          <AlertCircle size={14} />
          {error}
        </div>
      )}

      {/* Live Active Call — shown prominently above the log list */}
      {stats.active > 0 && logs.filter(l => l.status === 'in_progress').map(log => (
        <div key={log.call_sid} className="mb-6 border-2 border-amber-300 rounded-xl overflow-hidden animate-fade-in">
          <div className="px-5 py-3 bg-amber-400/20 border-b border-amber-300 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse" />
              <PhoneCall size={14} className="text-amber-700" />
              <span className="text-sm font-bold text-amber-800">Live Call in Progress</span>
            </div>
            <div className="flex items-center gap-3 text-xs text-amber-600">
              <span>{log.turns || 0} turns</span>
              <span className="font-mono">{log.caller || log.call_sid?.slice(0, 16)}</span>
              <StatusBadge status={log.status} />
            </div>
          </div>

          <div className="p-5">
            {(log.transcript || []).length === 0 ? (
              <p className="text-sm text-amber-700 italic">Waiting for customer to speak…</p>
            ) : (
              <div className="space-y-3">
                <p className="text-[10px] uppercase tracking-widest text-surface-400 font-semibold">Live Conversation</p>
                {(log.transcript || []).slice(-6).map((t, i) => (
                  <div key={i} className="space-y-1">
                    {t.customer && (
                      <div className="flex items-start gap-2">
                        <span className="text-[10px] font-bold text-primary-500 uppercase w-14 shrink-0 mt-0.5">Customer</span>
                        <span className="text-xs text-surface-700 bg-white rounded px-2 py-1.5 border border-surface-200 flex-1 leading-snug">{t.customer}</span>
                      </div>
                    )}
                    {t.aria && (
                      <div className="flex items-start gap-2">
                        <span className="text-[10px] font-bold text-violet-500 uppercase w-14 shrink-0 mt-0.5">Aria</span>
                        <span className="text-xs text-surface-700 bg-violet-50 rounded px-2 py-1.5 border border-violet-100 flex-1 leading-snug">{t.aria}</span>
                      </div>
                    )}
                    {t.intent && t.intent !== 'greeting' && t.intent !== 'unknown' && (
                      <div className="flex justify-end">
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-200 text-surface-500 font-mono">{t.intent}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}

      {/* Log list */}
      {loading && logs.length === 0 ? (
        <div className="card p-12 text-center text-surface-400 text-sm">
          <RefreshCw size={20} className="animate-spin mx-auto mb-3 opacity-40" />
          Loading call logs…
        </div>
      ) : logs.length === 0 ? (
        <div className="card p-12 text-center">
          <Phone size={32} className="text-surface-300 mx-auto mb-3" />
          <p className="text-surface-500 font-medium">No calls yet</p>
          <p className="text-surface-400 text-sm mt-1">
            Call your Twilio number to start an AI ordering session.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {logs.map((log, i) => (
            <CallRow key={log.call_sid || i} log={log} />
          ))}
        </div>
      )}
    </div>
  )
}

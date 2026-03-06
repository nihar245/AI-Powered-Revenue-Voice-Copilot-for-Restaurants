import { useState, useEffect, useCallback } from 'react'
import {
  Phone,
  PhoneIncoming,
  PhoneOff,
  PhoneCall,
  Clock,
  User,
  ShoppingCart,
  RefreshCw,
  Send,
  MessageCircle,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
  IndianRupee,
} from 'lucide-react'

const AI_BASE = import.meta.env.VITE_AI_SERVICE_URL || 'http://localhost:8001'
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:3000/api'

export default function CallLogs() {
  const [activeCalls, setActiveCalls] = useState([])
  const [callHistory, setCallHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [simText, setSimText] = useState('')
  const [simCallSid, setSimCallSid] = useState('')
  const [simConversation, setSimConversation] = useState([])
  const [simOrder, setSimOrder] = useState({ items: [], total: 0 })
  const [simLoading, setSimLoading] = useState(false)
  const [tab, setTab] = useState('simulator')  // 'simulator' | 'active' | 'history' | 'setup'
  const [refreshing, setRefreshing] = useState(false)

  const fetchCalls = useCallback(async () => {
    try {
      const [activeRes, historyRes] = await Promise.all([
        fetch(`${AI_BASE}/api/call/active`),
        fetch(`${AI_BASE}/api/call/history`),
      ])
      if (activeRes.ok) setActiveCalls(await activeRes.json())
      if (historyRes.ok) setCallHistory(await historyRes.json())
    } catch (err) {
      console.error('Failed to fetch calls:', err)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchCalls()
    const interval = setInterval(fetchCalls, 10000)
    return () => clearInterval(interval)
  }, [fetchCalls])

  const handleRefresh = () => {
    setRefreshing(true)
    fetchCalls()
  }

  const handleSimulate = async () => {
    if (!simText.trim()) return
    setSimLoading(true)

    // Add user message instantly
    setSimConversation(prev => [...prev, { role: 'customer', text: simText }])
    const userText = simText
    setSimText('')

    try {
      const res = await fetch(`${AI_BASE}/api/call/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: userText,
          call_sid: simCallSid || undefined,
        }),
      })

      if (!res.ok) throw new Error('Simulation failed')

      const data = await res.json()

      // Store call_sid for subsequent turns
      if (!simCallSid) setSimCallSid(data.call_sid)

      // Add agent response
      setSimConversation(prev => [...prev, { role: 'agent', text: data.agent_text }])
      setSimOrder(data.order || { items: [], total: 0 })
    } catch (err) {
      setSimConversation(prev => [
        ...prev,
        { role: 'error', text: 'Failed to get response. Is the AI service running?' },
      ])
    } finally {
      setSimLoading(false)
    }
  }

  const handleNewSimulation = () => {
    setSimCallSid('')
    setSimConversation([])
    setSimOrder({ items: [], total: 0 })
    setSimText('')
  }

  const formatTime = (ts) => {
    if (!ts) return '—'
    return new Date(ts * 1000).toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const formatDuration = (seconds) => {
    if (!seconds) return '—'
    const m = Math.floor(seconds / 60)
    const s = Math.round(seconds % 60)
    return m > 0 ? `${m}m ${s}s` : `${s}s`
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 flex items-center gap-2">
            <Phone className="text-primary-600" size={24} />
            Call Integration
          </h1>
          <p className="text-surface-500 text-sm mt-1">
            Twilio voice calls · Simulate calls · View active & past conversations
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-surface-200 rounded-lg text-sm
                     font-medium text-surface-600 hover:bg-surface-50 transition-all disabled:opacity-50"
        >
          <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Active Calls"
          value={activeCalls.length}
          icon={PhoneCall}
          color="green"
        />
        <StatCard
          label="Total Calls"
          value={callHistory.length}
          icon={Phone}
          color="blue"
        />
        <StatCard
          label="Orders from Calls"
          value={callHistory.filter(c => c.order?.items?.length > 0).length}
          icon={ShoppingCart}
          color="amber"
        />
        <StatCard
          label="Total Revenue"
          value={`₹${callHistory.reduce((sum, c) => sum + (c.order?.total || 0), 0).toFixed(0)}`}
          icon={IndianRupee}
          color="primary"
        />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-100 p-1 rounded-lg w-fit">
        {[
          { key: 'simulator', label: 'Call Simulator', icon: MessageCircle },
          { key: 'active', label: `Active (${activeCalls.length})`, icon: PhoneCall },
          { key: 'history', label: 'Call History', icon: Clock },
          { key: 'setup', label: 'Twilio Setup', icon: Phone },
        ].map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all
              ${tab === key
                ? 'bg-white text-primary-600 shadow-sm'
                : 'text-surface-500 hover:text-surface-700'
              }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === 'simulator' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Chat Panel */}
          <div className="lg:col-span-2 bg-white rounded-xl border border-surface-200 shadow-card flex flex-col h-[600px]">
            <div className="p-4 border-b border-surface-200 flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-surface-900">Phone Call Simulator</h3>
                <p className="text-xs text-surface-400 mt-0.5">
                  Test the voice ordering flow without a real phone call
                  {simCallSid && <span className="ml-2 text-primary-500">SID: {simCallSid}</span>}
                </p>
              </div>
              <button
                onClick={handleNewSimulation}
                className="text-xs px-3 py-1.5 bg-surface-100 hover:bg-surface-200 text-surface-600
                           rounded-lg transition-all font-medium"
              >
                New Call
              </button>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {simConversation.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-surface-400">
                  <PhoneIncoming size={48} className="mb-3 opacity-30" />
                  <p className="text-sm">Start a simulated phone call</p>
                  <p className="text-xs mt-1">Type an order like "mujhe ek butter chicken chahiye"</p>
                </div>
              )}
              {simConversation.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${msg.role === 'customer' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed
                      ${msg.role === 'customer'
                        ? 'bg-primary-600 text-white rounded-br-md'
                        : msg.role === 'error'
                          ? 'bg-red-50 text-red-600 border border-red-200 rounded-bl-md'
                          : 'bg-surface-100 text-surface-800 rounded-bl-md'
                      }`}
                  >
                    {msg.text}
                  </div>
                </div>
              ))}
              {simLoading && (
                <div className="flex justify-start">
                  <div className="bg-surface-100 px-4 py-2.5 rounded-2xl rounded-bl-md flex items-center gap-2">
                    <Loader2 size={14} className="animate-spin text-primary-500" />
                    <span className="text-sm text-surface-500">Thinking...</span>
                  </div>
                </div>
              )}
            </div>

            {/* Input */}
            <div className="p-4 border-t border-surface-200">
              <form
                onSubmit={(e) => { e.preventDefault(); handleSimulate() }}
                className="flex gap-2"
              >
                <input
                  type="text"
                  value={simText}
                  onChange={(e) => setSimText(e.target.value)}
                  placeholder="Type what the caller would say..."
                  disabled={simLoading}
                  className="flex-1 px-4 py-2.5 border border-surface-200 rounded-lg text-sm
                             focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-400
                             disabled:opacity-50 disabled:cursor-not-allowed"
                />
                <button
                  type="submit"
                  disabled={simLoading || !simText.trim()}
                  className="px-4 py-2.5 bg-primary-600 text-white rounded-lg text-sm font-medium
                             hover:bg-primary-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed
                             flex items-center gap-2"
                >
                  <Send size={14} />
                  Send
                </button>
              </form>
            </div>
          </div>

          {/* Order Panel */}
          <div className="bg-white rounded-xl border border-surface-200 shadow-card p-5 h-fit">
            <h3 className="font-semibold text-surface-900 flex items-center gap-2 mb-4">
              <ShoppingCart size={16} className="text-primary-600" />
              Live Order
            </h3>

            {simOrder.items.length === 0 ? (
              <div className="text-center py-8">
                <ShoppingCart size={32} className="mx-auto text-surface-300 mb-2" />
                <p className="text-sm text-surface-400">No items yet</p>
                <p className="text-xs text-surface-300 mt-1">
                  Order will build as you chat
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {simOrder.items.map((item, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between py-2 border-b border-surface-100 last:border-0"
                  >
                    <div>
                      <p className="text-sm font-medium text-surface-800">
                        {item.quantity || 1}× {item.name}
                      </p>
                      {item.variant && (
                        <p className="text-xs text-surface-400">{item.variant}</p>
                      )}
                    </div>
                    <span className="text-sm font-semibold text-surface-900">
                      ₹{item.subtotal || item.price || 0}
                    </span>
                  </div>
                ))}
                <div className="flex items-center justify-between pt-2 border-t border-surface-200">
                  <span className="text-sm font-bold text-surface-900">Total</span>
                  <span className="text-lg font-bold text-primary-600">₹{simOrder.total}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === 'active' && (
        <div className="bg-white rounded-xl border border-surface-200 shadow-card">
          <div className="p-5 border-b border-surface-200">
            <h3 className="font-semibold text-surface-900">Active Calls</h3>
          </div>
          {activeCalls.length === 0 ? (
            <EmptyState
              icon={PhoneCall}
              title="No Active Calls"
              description="When someone calls your Twilio number, active calls will appear here."
            />
          ) : (
            <div className="divide-y divide-surface-100">
              {activeCalls.map((call) => (
                <CallRow key={call.call_sid} call={call} formatTime={formatTime} />
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'history' && (
        <div className="bg-white rounded-xl border border-surface-200 shadow-card">
          <div className="p-5 border-b border-surface-200">
            <h3 className="font-semibold text-surface-900">Call History</h3>
          </div>
          {callHistory.length === 0 ? (
            <EmptyState
              icon={Clock}
              title="No Call History"
              description="Past calls and simulated conversations will appear here."
            />
          ) : (
            <div className="divide-y divide-surface-100">
              {callHistory.map((call) => (
                <CallRow key={call.call_sid} call={call} formatTime={formatTime} formatDuration={formatDuration} showDuration />
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'setup' && <TwilioSetupGuide />}
    </div>
  )
}


/* ─── Sub-Components ────────────────────────────────── */

function StatCard({ label, value, icon: Icon, color }) {
  const colors = {
    green: 'bg-green-50 text-green-600',
    blue: 'bg-blue-50 text-blue-600',
    amber: 'bg-amber-50 text-amber-600',
    primary: 'bg-primary-50 text-primary-600',
  }
  return (
    <div className="bg-white rounded-xl border border-surface-200 shadow-card p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-surface-400 font-medium">{label}</p>
          <p className="text-2xl font-bold text-surface-900 mt-1">{value}</p>
        </div>
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${colors[color]}`}>
          <Icon size={18} />
        </div>
      </div>
    </div>
  )
}

function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-surface-400">
      <Icon size={40} className="opacity-30 mb-3" />
      <p className="font-medium text-surface-600">{title}</p>
      <p className="text-sm mt-1">{description}</p>
    </div>
  )
}

function CallRow({ call, formatTime, formatDuration, showDuration }) {
  const isActive = call.status === 'active'
  return (
    <div className="flex items-center justify-between px-5 py-4 hover:bg-surface-50 transition-colors">
      <div className="flex items-center gap-4">
        <div className={`w-10 h-10 rounded-full flex items-center justify-center
          ${isActive ? 'bg-green-100 text-green-600' : 'bg-surface-100 text-surface-500'}`}>
          {isActive ? <PhoneCall size={16} /> : <PhoneOff size={16} />}
        </div>
        <div>
          <p className="text-sm font-medium text-surface-800">{call.phone || 'Unknown'}</p>
          <p className="text-xs text-surface-400">
            {formatTime(call.started_at)} · {call.turns} turns
            {showDuration && formatDuration && ` · ${formatDuration(call.duration)}`}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-4">
        {call.order?.items?.length > 0 && (
          <span className="text-sm font-semibold text-primary-600">
            ₹{call.order.total || call.total || 0}
          </span>
        )}
        <span className={`text-xs px-2.5 py-1 rounded-full font-medium
          ${isActive
            ? 'bg-green-100 text-green-700'
            : 'bg-surface-100 text-surface-500'
          }`}>
          {isActive ? 'Active' : 'Ended'}
        </span>
      </div>
    </div>
  )
}

function TwilioSetupGuide() {
  return (
    <div className="bg-white rounded-xl border border-surface-200 shadow-card p-6 space-y-6">
      <div>
        <h3 className="text-lg font-bold text-surface-900">Twilio Integration Setup</h3>
        <p className="text-sm text-surface-500 mt-1">
          Connect real phone calls to your AI voice copilot in 5 minutes.
        </p>
      </div>

      <div className="space-y-4">
        <SetupStep
          number={1}
          title="Create a Twilio Account"
          description="Sign up at twilio.com and get a phone number with voice capabilities."
          status="info"
        />
        <SetupStep
          number={2}
          title="Install ngrok for Local Development"
          description={
            <span>
              Run <code className="bg-surface-100 px-1.5 py-0.5 rounded text-xs">ngrok http 8001</code> to
              expose your local AI service to the internet. Copy the HTTPS URL.
            </span>
          }
          status="info"
        />
        <SetupStep
          number={3}
          title="Configure Twilio Webhook"
          description={
            <span>
              In your Twilio console, set the phone number's Voice webhook to:
              <code className="block bg-surface-100 px-3 py-2 rounded-lg text-xs mt-2 font-mono">
                POST https://your-ngrok-url/api/call/incoming
              </code>
            </span>
          }
          status="info"
        />
        <SetupStep
          number={4}
          title="Set Status Callback (Optional)"
          description={
            <span>
              For call tracking, set the status callback URL to:
              <code className="block bg-surface-100 px-3 py-2 rounded-lg text-xs mt-2 font-mono">
                POST https://your-ngrok-url/api/call/status
              </code>
            </span>
          }
          status="info"
        />
        <SetupStep
          number={5}
          title="Test with a Real Call"
          description="Call your Twilio number. The AI will greet you and take your order in Hindi/English!"
          status="info"
        />
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <div className="flex gap-3">
          <AlertCircle size={18} className="text-amber-600 shrink-0 mt-0.5" />
          <div className="text-sm text-amber-800">
            <p className="font-semibold">Testing without Twilio</p>
            <p className="mt-1">
              Use the <strong>Call Simulator</strong> tab to test the entire conversation flow
              without needing a Twilio account. It uses the same AI pipeline.
            </p>
          </div>
        </div>
      </div>

      <div className="bg-surface-50 border border-surface-200 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-surface-800 mb-2">API Endpoints</h4>
        <div className="space-y-2 text-xs font-mono text-surface-600">
          <div className="flex gap-2">
            <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded font-semibold">POST</span>
            <span>/api/call/incoming</span>
            <span className="text-surface-400 ml-auto">Twilio voice webhook</span>
          </div>
          <div className="flex gap-2">
            <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded font-semibold">POST</span>
            <span>/api/call/gather</span>
            <span className="text-surface-400 ml-auto">Speech processing</span>
          </div>
          <div className="flex gap-2">
            <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded font-semibold">POST</span>
            <span>/api/call/simulate</span>
            <span className="text-surface-400 ml-auto">Test without Twilio</span>
          </div>
          <div className="flex gap-2">
            <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded font-semibold">GET</span>
            <span>/api/call/active</span>
            <span className="text-surface-400 ml-auto">Active calls list</span>
          </div>
          <div className="flex gap-2">
            <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded font-semibold">GET</span>
            <span>/api/call/history</span>
            <span className="text-surface-400 ml-auto">Call history</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function SetupStep({ number, title, description, status }) {
  const icons = {
    done: <CheckCircle size={18} className="text-green-500" />,
    error: <XCircle size={18} className="text-red-500" />,
    info: (
      <span className="w-6 h-6 rounded-full bg-primary-100 text-primary-600 text-xs font-bold flex items-center justify-center">
        {number}
      </span>
    ),
  }

  return (
    <div className="flex gap-3 p-4 bg-surface-50 rounded-lg border border-surface-100">
      <div className="shrink-0 mt-0.5">{icons[status]}</div>
      <div>
        <p className="text-sm font-semibold text-surface-800">{title}</p>
        <div className="text-sm text-surface-500 mt-0.5">{description}</div>
      </div>
    </div>
  )
}

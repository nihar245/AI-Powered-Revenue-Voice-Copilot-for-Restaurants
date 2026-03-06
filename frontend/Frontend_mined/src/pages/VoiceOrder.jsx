import { useState, useEffect, useRef } from 'react'
import {
  Mic,
  MicOff,
  Sparkles,
  CheckCircle2,
  ShoppingCart,
  RotateCcw,
  Zap,
  Languages,
} from 'lucide-react'
import { apiFetch } from '../config'

const DEMO_STEPS = [
  { delay: 500,  transcript: 'Ek paneer pizza...' },
  { delay: 1200, transcript: 'Ek paneer pizza aur ek coke dena...' },
  { delay: 2200, transcript: '"Ek paneer pizza aur ek coke dena"' },
  { delay: 2800, transcript: '"Ek paneer pizza aur ek coke dena"', done: true },
]

const DEMO_ITEMS = [
  { name: 'Paneer Pizza', size: 'Medium', price: 420 },
  { name: 'Coke', size: '300ml', price: 60 },
]

export default function VoiceOrder() {
  const [state, setState] = useState('idle')   // idle | listening | processing | done
  const [transcript, setTranscript] = useState('')
  const [items, setItems] = useState([])
  const [showUpsell, setShowUpsell] = useState(false)
  const [upsellAdded, setUpsellAdded] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [upsellCombo, setUpsellCombo] = useState(null) // { base, suggestion, price, confidence }
  const timers = useRef([])

  // Load top combo from real data
  useEffect(() => {
    apiFetch('/revenue/top-combos')
      .then(data => {
        if (Array.isArray(data) && data.length > 0) {
          const top = data[0]
          setUpsellCombo({
            base: top.itemA,
            suggestion: top.itemB,
            price: 100, // combo add-on display price; real price comes from variant
            confidence: Math.round(top.confidence || 70),
          })
        }
      })
      .catch(() => {})
  }, [])

  const clearTimers = () => { timers.current.forEach(clearTimeout); timers.current = [] }

  const startListening = () => {
    clearTimers()
    setState('listening')
    setTranscript('')
    setItems([])
    setShowUpsell(false)
    setUpsellAdded(false)
    setConfirmed(false)

    DEMO_STEPS.forEach(({ delay, transcript: t, done }) => {
      const id = setTimeout(() => {
        setTranscript(t)
        if (done) {
          setState('processing')
          const id2 = setTimeout(() => {
            setItems(DEMO_ITEMS)
            setState('done')
            const id3 = setTimeout(() => setShowUpsell(true), 600)
            timers.current.push(id3)
          }, 900)
          timers.current.push(id2)
        }
      }, delay)
      timers.current.push(id)
    })
  }

  const reset = () => {
    clearTimers()
    setState('idle')
    setTranscript('')
    setItems([])
    setShowUpsell(false)
    setUpsellAdded(false)
    setConfirmed(false)
  }

  useEffect(() => () => clearTimers(), [])

  const totalItems = [
    ...items,
    ...(upsellAdded && upsellCombo ? [{ name: upsellCombo.suggestion, size: 'Add-on', price: upsellCombo.price }] : []),
  ]
  const total = totalItems.reduce((s, i) => s + i.price, 0)

  return (
    <div className="p-6 animate-fade-in">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-surface-900">Voice Ordering</h1>
        <p className="text-surface-400 text-sm mt-0.5">AI-powered speech-to-order with upsell suggestions</p>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">

        {/* ── Left column: mic + transcript + items ── */}
        <div className="lg:col-span-2 space-y-5">

          {/* Language badge */}
          <div className="flex items-center gap-2 flex-wrap">
            {['Hindi', 'English', 'Tamil', 'Telugu'].map(lang => (
              <span key={lang} className={`text-xs px-3 py-1 rounded-full border font-medium transition-all
                ${lang === 'Hindi' ? 'bg-primary-50 text-primary-600 border-primary-200' : 'text-surface-500 border-surface-200 bg-surface-50'}
              `}>
                <Languages size={11} className="inline mr-1" />
                {lang}
              </span>
            ))}
          </div>

          {/* Microphone */}
          <div className="card p-8 flex flex-col items-center gap-6">
            <div className="relative">
              {/* Pulse rings when listening */}
              {state === 'listening' && (
                <>
                  <div className="absolute inset-[-16px] rounded-full bg-red-500/10 animate-ping" style={{ animationDuration: '1.5s' }} />
                  <div className="absolute inset-[-32px] rounded-full bg-red-500/5 animate-ping" style={{ animationDuration: '2s', animationDelay: '0.5s' }} />
                </>
              )}

              <button
                onClick={() => state === 'idle' ? startListening() : reset()}
                disabled={state === 'processing'}
                className={`relative w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl
                  ${state === 'listening'
                    ? 'bg-red-500 hover:bg-red-400 shadow-red-500/40 scale-110'
                    : state === 'done'
                      ? 'bg-emerald-500 hover:bg-red-500 shadow-emerald-500/30'
                      : state === 'processing'
                        ? 'bg-amber-500 shadow-amber-500/30'
                        : 'bg-primary-600 hover:bg-primary-700 shadow-red-btn hover:scale-105'
                  }
                `}
              >
                {state === 'processing' ? (
                  <span className="w-6 h-6 border-3 border-white/30 border-t-white rounded-full animate-spin" style={{ borderWidth: 3 }} />
                ) : state === 'done' ? (
                  <CheckCircle2 size={28} className="text-white" />
                ) : state === 'listening' ? (
                  <MicOff size={28} className="text-white" />
                ) : (
                  <Mic size={28} className="text-white" />
                )}
              </button>
            </div>

            <div className="text-center">
              <p className="text-surface-900 font-semibold text-sm">
                {state === 'idle' && 'Press to start voice ordering'}
                {state === 'listening' && 'Listening… speak your order'}
                {state === 'processing' && 'Processing with AI…'}
                {state === 'done' && 'Order detected! Review below'}
              </p>
              <p className="text-surface-400 text-xs mt-1">
                {state === 'idle' ? 'Supports Hindi, English & more' : 'Click the button again to reset'}
              </p>
            </div>
          </div>

          {/* Transcript */}
          {(transcript || state !== 'idle') && (
            <div className="card p-4 animate-fade-in">
              <p className="text-xs text-surface-400 uppercase tracking-wider font-semibold mb-2 flex items-center gap-1.5">
                <Zap size={11} className="text-primary-600" />
                Transcript
              </p>
              <div className="bg-surface-50 rounded-lg p-3 font-mono text-sm text-surface-700 min-h-[40px] border border-surface-200">
                {transcript || <span className="text-surface-400 italic">Waiting for speech…</span>}
                {state === 'listening' && (
                  <span className="inline-block w-2 h-4 bg-primary-500 ml-0.5 animate-pulse align-[-2px]" />
                )}
              </div>
            </div>
          )}

          {/* Detected Items */}
          {items.length > 0 && (
            <div className="card p-4 border-l-4 border-l-emerald-500 animate-slide-up">
              <p className="text-xs text-emerald-600 uppercase tracking-wider font-semibold mb-3 flex items-center gap-1.5">
                <CheckCircle2 size={12} />
                Detected Items
              </p>
              <div className="space-y-2">
                {items.map((item, i) => (
                  <div key={i} className="flex items-center justify-between bg-surface-50 rounded-lg px-3 py-2.5 border border-surface-200">
                    <div>
                      <p className="text-surface-900 text-sm font-medium">{item.name}</p>
                      <p className="text-surface-400 text-xs">{item.size}</p>
                    </div>
                    <span className="text-surface-500 text-sm font-semibold">₹{item.price}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Upsell suggestion */}
          {showUpsell && upsellCombo && !upsellAdded && !confirmed && (
            <div className="card p-4 border-l-4 border-l-violet-500 bg-violet-50/50 animate-slide-up">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles size={14} className="text-violet-600" />
                <p className="text-violet-600 text-sm font-semibold">AI Upsell Suggestion</p>
              </div>
              <p className="text-surface-600 text-sm mb-3">
                Add <span className="text-violet-600 font-semibold">{upsellCombo.suggestion}</span> combo?
                <span className="text-surface-400 text-xs ml-1">({upsellCombo.confidence}% customers add this)</span>
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setUpsellAdded(true)}
                  className="flex-1 btn-primary text-xs py-2"
                >
                  Yes, Add {upsellCombo.suggestion} (+₹{upsellCombo.price})
                </button>
                <button
                  onClick={() => setShowUpsell(false)}
                  className="px-3 btn-secondary text-xs py-2"
                >
                  Skip
                </button>
              </div>
            </div>
          )}

          {upsellAdded && upsellCombo && (
            <div className="flex items-center gap-2 text-emerald-400 text-sm animate-fade-in px-1">
              <CheckCircle2 size={14} />
              {upsellCombo.suggestion} added to order!
            </div>
          )}
        </div>

        {/* ── Right column: Order summary ── */}
        <div className="space-y-4">
          <div className="card overflow-hidden">
            {/* Header */}
            <div className="px-5 py-3.5 bg-surface-900 border-b border-surface-800 flex items-center gap-2">
              <ShoppingCart size={15} className="text-primary-400" />
              <span className="text-sm font-semibold text-white">Order Summary</span>
            </div>

            <div className="p-5">
              {totalItems.length === 0 ? (
                <p className="text-surface-400 text-sm text-center py-6">
                  Start voice ordering to see items here
                </p>
              ) : (
                <>
                  <div className="space-y-3 mb-4">
                    {totalItems.map((item, i) => (
                      <div key={i} className="flex items-center justify-between text-sm">
                        <div>
                          <p className="text-surface-900 font-medium">{item.name}</p>
                          <p className="text-surface-400 text-xs">{item.size}</p>
                        </div>
                        <span className="text-surface-500">₹{item.price}</span>
                      </div>
                    ))}
                  </div>

                  <div className="border-t border-dashed border-surface-200 pt-3 mb-4">
                    <div className="flex items-center justify-between">
                      <span className="text-surface-400 text-sm">Total</span>
                      <span className="text-surface-900 font-bold text-lg">₹{total}</span>
                    </div>
                  </div>

                  {!confirmed ? (
                    <button
                      onClick={() => setConfirmed(true)}
                      className="btn-primary w-full py-2.5 text-sm"
                    >
                      Confirm Order
                    </button>
                  ) : (
                    <div className="text-center">
                      <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-2">
                        <CheckCircle2 size={22} className="text-emerald-400" />
                      </div>
                      <p className="text-emerald-600 font-semibold text-sm">Order Confirmed!</p>
                      <p className="text-surface-400 text-xs mt-1">Sent to kitchen</p>
                      <button
                        onClick={reset}
                        className="mt-3 btn-ghost text-xs flex items-center gap-1.5 mx-auto"
                      >
                        <RotateCcw size={12} /> New Order
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          {/* AI stats */}
          {state !== 'idle' && (
            <div className="card p-4 space-y-2 animate-fade-in">
              <p className="text-xs text-surface-400 uppercase tracking-wider font-semibold">AI Metrics</p>
              {[
                { label: 'Language Detected', value: 'Hindi' },
                { label: 'Confidence', value: '94.2%' },
                { label: 'Processing Time', value: '0.9s' },
              ].map(({ label, value }) => (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-surface-400 text-xs">{label}</span>
                  <span className="text-primary-600 text-xs font-semibold">{value}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

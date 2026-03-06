import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Mic,
  MicOff,
  Sparkles,
  CheckCircle2,
  ShoppingCart,
  RotateCcw,
  Zap,
  X,
  AlertCircle,
  Volume2,
  MessageSquare,
  Timer,
  UtensilsCrossed,
  Leaf,
} from 'lucide-react'
import { API_URL } from '../config'

const SUPPORTED_LANGS = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'Hindi' },
  { code: 'ta', label: 'Tamil' },
  { code: 'te', label: 'Telugu' },
]

function formatCart(cart) {
  return (cart || []).map((item, i) => ({
    ...item,
    _key: `${item.product_id}-${i}`,
  }))
}

export default function VoiceOrder() {
  // --- state ---
  const [recording, setRecording]             = useState(false)
  const [processing, setProcessing]           = useState(false)
  const [transcript, setTranscript]           = useState('')
  const [responseText, setResponseText]       = useState('')
  const [cart, setCart]                       = useState([])
  const [cartTotal, setCartTotal]             = useState('₹0')
  const [cartEvents, setCartEvents]           = useState([])
  const [upsellChips, setUpsellChips]         = useState([])
  const [clarification, setClarification]     = useState(null)
  const [activeCombos, setActiveCombos]       = useState([])
  const [orderNumber, setOrderNumber]         = useState(null)
  const [confirmed, setConfirmed]             = useState(false)
  const [confirming, setConfirming]           = useState(false)
  const [language, setLanguage]               = useState('en')
  const [tableId, setTableId]                 = useState('T1')
  const [error, setError]                     = useState(null)
  const [playingAudio, setPlayingAudio]       = useState(false)
  const [intent, setIntent]                   = useState(null)
  const [timings, setTimings]                 = useState(null)
  const [upsellSuggestion, setUpsellSuggestion] = useState(null)
  const [turn, setTurn]                       = useState(0)
  const [menuCategories, setMenuCategories]   = useState([])
  const [menuLoading, setMenuLoading]         = useState(true)
  const [lastResponse, setLastResponse]       = useState(null)
  const [showRawJson, setShowRawJson]         = useState(false)

  // --- refs ---
  const sessionIdRef    = useRef(null)
  const mediaRecRef     = useRef(null)
  const chunksRef       = useRef([])
  const audioRef        = useRef(new Audio())

  // Generate session ID once per page load
  useEffect(() => {
    sessionIdRef.current = crypto.randomUUID()
    return () => {
      if (mediaRecRef.current && mediaRecRef.current.state !== 'inactive') {
        mediaRecRef.current.stop()
      }
    }
  }, [])

  // Fetch menu on mount
  useEffect(() => {
    const token = localStorage.getItem('token')
    fetch(`${API_URL}/voice/menu`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(data => setMenuCategories(data.categories || []))
      .catch(() => setMenuCategories([]))
      .finally(() => setMenuLoading(false))
  }, [])

  // --- audio playback helper ---
  const playAudioBase64 = useCallback((base64, mime = 'audio/wav') => {
    const audio = audioRef.current
    audio.src = `data:${mime};base64,${base64}`
    audio.onplay  = () => setPlayingAudio(true)
    audio.onended = () => setPlayingAudio(false)
    audio.onerror = () => setPlayingAudio(false)
    audio.play().catch(() => setPlayingAudio(false))
  }, [])

  // --- start recording ---
  const startRecording = useCallback(async () => {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : 'audio/ogg'

      const rec = new MediaRecorder(stream, { mimeType })
      chunksRef.current = []
      rec.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunksRef.current, { type: mimeType })
        await sendAudio(blob, mimeType)
      }
      rec.start()
      mediaRecRef.current = rec
      setRecording(true)
    } catch (e) {
      setError('Microphone access denied. Please allow microphone permission.')
    }
  }, [language, tableId])

  // --- stop recording ---
  const stopRecording = useCallback(() => {
    if (mediaRecRef.current && mediaRecRef.current.state === 'recording') {
      mediaRecRef.current.stop()
      setRecording(false)
      setProcessing(true)
    }
  }, [])

  // --- send audio to backend ---
  const sendAudio = useCallback(async (blob, mimeType) => {
    const token = localStorage.getItem('token')
    const form  = new FormData()
    form.append('audio',      blob, 'audio.webm')
    form.append('session_id', sessionIdRef.current)
    form.append('language',   language)
    form.append('table_id',   tableId)

    try {
      const res = await fetch(`${API_URL}/voice/process-turn`, {
        method:  'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body:    form,
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.error || `Server error ${res.status}`)
      }
      const data = await res.json()
      applyTurnResult(data)
    } catch (e) {
      setError(e.message || 'Failed to process voice turn')
    } finally {
      setProcessing(false)
    }
  }, [language, tableId])

  // --- apply response from voice-chat / add-item ---
  const applyTurnResult = useCallback((data) => {
    if (data.transcript)                              setTranscript(data.transcript)
    if (data.response_text || data.response_display)  setResponseText(data.response_display || data.response_text)
    if (Array.isArray(data.cart))  setCart(formatCart(data.cart))
    if (data.cart_total)          setCartTotal(data.cart_total)
    if (data.cart_events)         setCartEvents(prev => [...prev, ...data.cart_events].slice(-10))
    if (data.upsell_chips)        setUpsellChips(data.upsell_chips)
    if (data.active_combos)       setActiveCombos(data.active_combos)
    if (data.order_number)        setOrderNumber(data.order_number)
    setClarification(data.pending_clarification || null)
    if (data.audio_base64)        playAudioBase64(data.audio_base64, data.audio_mime || 'audio/wav')
    if (data.intent === 'confirm_order') setConfirmed(true)
    if (data.intent)                setIntent(data.intent)
    if (data.timings_ms)            setTimings(data.timings_ms)
    setUpsellSuggestion(data.upsell_suggestion || null)
    if (data.turn)                  setTurn(data.turn)
    // Store raw response for debug panel (strip the large audio blob)
    const { audio_base64: _omit, ...displayData } = data
    setLastResponse(displayData)
  }, [playAudioBase64])

  // --- upsell chip click ---
  const handleAddItem = useCallback(async (chip) => {
    setError(null)
    const token = localStorage.getItem('token')
    try {
      const res = await fetch(`${API_URL}/voice/add-item`, {
        method:  'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          product_id: chip.product_id,
          item_name:  chip.item_name,
          quantity:   1,
        }),
      })
      if (!res.ok) throw new Error(`Add item failed ${res.status}`)
      const data = await res.json()
      setCart(formatCart(data.cart))
      if (data.cart_total)  setCartTotal(data.cart_total)
      if (data.cart_events) setCartEvents(prev => [...prev, ...data.cart_events].slice(-10))
      if (data.upsell_chips) setUpsellChips(data.upsell_chips)
      setUpsellChips(chips => chips.filter(c => c.product_id !== chip.product_id))
    } catch (e) {
      setError(e.message)
    }
  }, [])

  // --- confirm order button ---
  const handleConfirm = useCallback(async () => {
    setConfirming(true)
    setError(null)
    const token = localStorage.getItem('token')
    try {
      const res = await fetch(`${API_URL}/voice/confirm-order`, {
        method:  'POST',
        headers: {
          'Content-Type':  'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ session_id: sessionIdRef.current }),
      })
      if (!res.ok) throw new Error(`Confirm failed ${res.status}`)
      const data = await res.json()
      setOrderNumber(data.order_number || null)
      if (data.cart_events) setCartEvents(prev => [...prev, ...data.cart_events].slice(-10))
      setCart([])
      setConfirmed(true)
    } catch (e) {
      setError(e.message)
    } finally {
      setConfirming(false)
    }
  }, [])

  // --- reset ---
  const reset = useCallback(() => {
    if (mediaRecRef.current && mediaRecRef.current.state !== 'inactive') {
      mediaRecRef.current.stop()
    }
    audioRef.current.pause()
    sessionIdRef.current = crypto.randomUUID()
    setRecording(false)
    setProcessing(false)
    setTranscript('')
    setResponseText('')
    setCart([])
    setCartTotal('₹0')
    setCartEvents([])
    setUpsellChips([])
    setClarification(null)
    setActiveCombos([])
    setOrderNumber(null)
    setConfirmed(false)
    setError(null)
    setPlayingAudio(false)
    setIntent(null)
    setTimings(null)
    setUpsellSuggestion(null)
    setTurn(0)
    setLastResponse(null)
    setShowRawJson(false)
  }, [])

  // ---- derived ----
  const micState = recording ? 'listening' : processing ? 'processing' : confirmed ? 'done' : 'idle'

  return (
    <div className="p-6 animate-fade-in">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-surface-900">Voice Ordering</h1>
        <p className="text-surface-400 text-sm mt-0.5">AI-powered speech-to-order — Gemini Live</p>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-4 flex items-center gap-2 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm animate-fade-in">
          <AlertCircle size={14} className="shrink-0" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto"><X size={14} /></button>
        </div>
      )}

      {/* Clarification banner */}
      {clarification && (
        <div className="mb-4 flex items-center gap-2 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-sm animate-fade-in">
          <AlertCircle size={14} className="shrink-0" />
          {clarification}
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Left column */}
        <div className="lg:col-span-2 space-y-5">

          {/* Microphone */}
          <div className="card p-8 flex flex-col items-center gap-6">
            <div className="relative">
              {micState === 'listening' && (
                <>
                  <div className="absolute inset-[-16px] rounded-full bg-red-500/10 animate-ping" style={{ animationDuration: '1.5s' }} />
                  <div className="absolute inset-[-32px] rounded-full bg-red-500/5 animate-ping" style={{ animationDuration: '2s', animationDelay: '0.5s' }} />
                </>
              )}
              <button
                onClick={() => {
                  if (micState === 'idle') startRecording()
                  else if (micState === 'listening') stopRecording()
                  else if (micState === 'done') reset()
                }}
                disabled={micState === 'processing' || confirmed}
                className={`relative w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl
                  ${micState === 'listening'
                    ? 'bg-red-500 hover:bg-red-400 shadow-red-500/40 scale-110'
                    : micState === 'done'
                      ? 'bg-emerald-500 shadow-emerald-500/30'
                      : micState === 'processing'
                        ? 'bg-amber-500 shadow-amber-500/30 cursor-wait'
                        : 'bg-primary-600 hover:bg-primary-700 shadow-red-btn hover:scale-105'}`}
              >
                {micState === 'processing' ? (
                  <span className="w-6 h-6 border-3 border-white/30 border-t-white rounded-full animate-spin" style={{ borderWidth: 3 }} />
                ) : micState === 'done' ? (
                  <CheckCircle2 size={28} className="text-white" />
                ) : micState === 'listening' ? (
                  <MicOff size={28} className="text-white" />
                ) : (
                  <Mic size={28} className="text-white" />
                )}
              </button>
            </div>
            <div className="text-center">
              <p className="text-surface-900 font-semibold text-sm">
                {micState === 'idle'       && 'Press to start voice ordering'}
                {micState === 'listening'  && 'Listening… press again to stop'}
                {micState === 'processing' && 'Processing with Gemini…'}
                {micState === 'done'       && 'Order placed! Press to start new order'}
              </p>
              <p className="text-surface-400 text-xs mt-1 flex items-center justify-center gap-1">
                {playingAudio && <><Volume2 size={11} className="text-primary-500 animate-pulse" /> Playing response…</>}
                {!playingAudio && `Session: ${(sessionIdRef.current || '').slice(0, 8)}…`}
              </p>
            </div>
          </div>

          {/* Transcript + AI Response */}
          {transcript && (
            <div className="card p-4 animate-fade-in space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-xs text-surface-400 uppercase tracking-wider font-semibold flex items-center gap-1.5">
                  <Zap size={11} className="text-primary-600" /> You said
                </p>
                {intent && (
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary-50 text-primary-600 border border-primary-100 font-mono capitalize">
                    {intent.replace(/_/g, ' ')}
                  </span>
                )}
              </div>
              <div className="bg-surface-50 rounded-lg p-3 font-mono text-sm text-surface-700 border border-surface-200">
                {transcript}
              </div>
              {responseText && (
                <div className="bg-gradient-to-r from-primary-50 to-violet-50 rounded-lg p-3 border border-primary-100 flex items-start gap-2">
                  <MessageSquare size={14} className="text-primary-500 mt-0.5 shrink-0" />
                  <p className="text-sm text-surface-800 leading-relaxed">{responseText}</p>
                </div>
              )}
            </div>
          )}

          {/* Upsell chips */}
          {upsellChips.length > 0 && (
            <div className="card p-4 border-l-4 border-l-violet-500 bg-violet-50/50 animate-slide-up">
              <div className="flex items-center gap-2 mb-2">
                <Sparkles size={14} className="text-violet-600" />
                <p className="text-violet-600 text-sm font-semibold">AI Suggestions</p>
              </div>
              {upsellSuggestion && (
                <p className="text-violet-700 text-xs mb-3 leading-relaxed">{upsellSuggestion}</p>
              )}
              <div className="flex flex-wrap gap-2">
                {upsellChips.map(chip => (
                  <button
                    key={chip.product_id}
                    onClick={() => handleAddItem(chip)}
                    className="text-xs px-3 py-1.5 rounded-full bg-violet-100 text-violet-700 border border-violet-200 hover:bg-violet-200 transition-colors"
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Active combo badges */}
          {activeCombos.length > 0 && (
            <div className="card p-4 border-l-4 border-l-emerald-400 animate-fade-in">
              <p className="text-xs text-emerald-600 font-semibold mb-2">Active Combos</p>
              <div className="flex flex-wrap gap-2">
                {activeCombos.map((c, i) => (
                  <span key={i} className="text-xs px-2 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">{c.description || c.name}</span>
                ))}
              </div>
            </div>
          )}

          {/* Event log */}
          {cartEvents.length > 0 && (
            <div className="card p-4 animate-fade-in">
              <p className="text-xs text-surface-400 uppercase tracking-wider font-semibold mb-2">Cart Events</p>
              <ul className="space-y-1">
                {cartEvents.map((e, i) => (
                  <li key={i} className="text-xs text-surface-600 flex items-center gap-1.5">
                    <span className="w-1 h-1 rounded-full bg-primary-400 shrink-0" />
                    {e}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Raw API Response */}
          {lastResponse && (
            <div className="card overflow-hidden animate-fade-in">
              <button
                onClick={() => setShowRawJson(v => !v)}
                className="w-full px-4 py-3 flex items-center justify-between bg-surface-50 hover:bg-surface-100 transition-colors border-b border-surface-200"
              >
                <span className="text-xs font-semibold text-surface-600 uppercase tracking-wider flex items-center gap-1.5">
                  <Zap size={11} className="text-amber-500" />
                  Raw API Response
                  <span className="ml-1 px-1.5 py-0.5 rounded bg-amber-100 text-amber-600 text-[10px] font-mono">
                    turn {lastResponse.turn}
                  </span>
                </span>
                <span className="text-surface-400 text-xs">{showRawJson ? '▲ hide' : '▼ show'}</span>
              </button>
              {showRawJson && (
                <pre className="p-4 text-[11px] leading-relaxed text-surface-700 bg-surface-950 overflow-x-auto max-h-[500px] overflow-y-auto font-mono whitespace-pre-wrap break-all" style={{ background: '#0f172a', color: '#94a3b8' }}>
                  {JSON.stringify(lastResponse, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>

        {/* Right column — order summary */}
        <div className="space-y-4">
          <div className="card overflow-hidden">
            <div className="px-5 py-3.5 bg-surface-900 border-b border-surface-800 flex items-center gap-2">
              <ShoppingCart size={15} className="text-primary-400" />
              <span className="text-sm font-semibold text-white">Order Summary</span>
            </div>

            <div className="p-5">
              {cart.length === 0 && !confirmed ? (
                <p className="text-surface-400 text-sm text-center py-6">Start voice ordering to see items here</p>
              ) : confirmed ? (
                <div className="text-center py-4">
                  <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-2">
                    <CheckCircle2 size={22} className="text-emerald-400" />
                  </div>
                  <p className="text-emerald-600 font-semibold text-sm">Order Confirmed!</p>
                  {orderNumber && (
                    <p className="text-surface-400 text-xs mt-1">Order #{orderNumber}</p>
                  )}
                  <p className="text-surface-400 text-xs mt-1">Sent to kitchen</p>
                  <button onClick={reset} className="mt-3 btn-ghost text-xs flex items-center gap-1.5 mx-auto">
                    <RotateCcw size={12} /> New Order
                  </button>
                </div>
              ) : (
                <>
                  <div className="space-y-3 mb-4">
                    {cart.map(item => {
                      // size is shown as variant label — exclude it from the inline modifier list
                      const modEntries = Object.entries(item.modifiers || {}).filter(
                        ([k, v]) => k !== 'add_ons' && k !== 'size' && v
                      )
                      const addOns = item.modifiers?.add_ons || []
                      // Prefer the live modifiers.size over the stale variant_name
                      const sizeLabel = item.modifiers?.size
                        ? item.modifiers.size.charAt(0).toUpperCase() + item.modifiers.size.slice(1)
                        : item.variant_name
                      return (
                        <div key={item._key} className="flex items-start justify-between text-sm">
                          <div className="flex-1 min-w-0">
                            <p className="text-surface-900 font-medium">{item.name}</p>
                            {sizeLabel && (
                              <p className="text-surface-500 text-xs">{sizeLabel}</p>
                            )}
                            <p className="text-surface-400 text-xs">
                              Qty: {item.quantity}
                              {modEntries.map(([, v]) => ` · ${v}`).join('')}
                            </p>
                            {addOns.length > 0 && (
                              <p className="text-surface-400 text-xs">{addOns.join(', ')}</p>
                            )}
                            {item.notes && (
                              <p className="text-surface-400 text-xs italic">"{item.notes}"</p>
                            )}
                          </div>
                          <span className="text-surface-500 shrink-0 ml-2">
                            ₹{(item.unit_price * item.quantity).toFixed(0)}
                          </span>
                        </div>
                      )
                    })}
                  </div>
                  {(() => {
                    const subtotal = cart.reduce((s, i) => s + i.unit_price * i.quantity, 0)
                    const taxAmt   = cart.reduce((s, i) => s + i.unit_price * i.quantity * (i.tax_rate ?? 5) / 100, 0)
                    return (
                      <div className="border-t border-dashed border-surface-200 pt-3 mb-4 space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="text-surface-400 text-xs">Subtotal</span>
                          <span className="text-surface-500 text-xs">₹{subtotal.toFixed(0)}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-surface-400 text-xs">Tax (5%)</span>
                          <span className="text-surface-500 text-xs">₹{taxAmt.toFixed(0)}</span>
                        </div>
                        <div className="flex items-center justify-between border-t border-surface-200 pt-1.5">
                          <span className="text-surface-700 text-sm font-semibold">Total</span>
                          <span className="text-surface-900 font-bold text-lg">{cartTotal}</span>
                        </div>
                      </div>
                    )
                  })()}
                  <button
                    onClick={handleConfirm}
                    disabled={confirming || cart.length === 0}
                    className="btn-primary w-full py-2.5 text-sm disabled:opacity-50"
                  >
                    {confirming ? 'Confirming…' : 'Confirm Order'}
                  </button>
                </>
              )}
            </div>
          </div>

          {/* AI metrics */}
          {transcript && (
            <div className="card p-4 space-y-2 animate-fade-in">
              <p className="text-xs text-surface-400 uppercase tracking-wider font-semibold flex items-center gap-1.5">
                <Timer size={11} /> Session Info
              </p>
              {[
                { label: 'Language', value: SUPPORTED_LANGS.find(l => l.code === language)?.label || language },
                { label: 'Model',    value: 'Gemini Live' },
                { label: 'Turn',     value: turn || '—' },
                ...(timings ? [
                  { label: 'Gemini',  value: `${timings.gemini_live_ms} ms` },
                  { label: 'Extract', value: `${timings.extract_ms} ms` },
                ] : []),
              ].map(({ label, value }) => (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-surface-400 text-xs">{label}</span>
                  <span className="text-primary-600 text-xs font-semibold">{value}</span>
                </div>
              ))}
            </div>
          )}

          {/* Menu reference */}
          <div className="card overflow-hidden">
            <div className="px-5 py-3.5 bg-surface-50 border-b border-surface-200 flex items-center gap-2">
              <UtensilsCrossed size={14} className="text-surface-500" />
              <span className="text-sm font-semibold text-surface-700">Menu</span>
            </div>
            <div className="max-h-96 overflow-y-auto">
              {menuLoading ? (
                <p className="text-surface-400 text-xs text-center py-6">Loading menu…</p>
              ) : menuCategories.length === 0 ? (
                <p className="text-surface-400 text-xs text-center py-6">Menu unavailable</p>
              ) : (
                <div className="divide-y divide-surface-100">
                  {menuCategories.map(cat => (
                    <div key={cat.name} className="px-4 py-3">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-surface-400 mb-2">{cat.name}</p>
                      <div className="space-y-2">
                        {cat.items.map(item => (
                          <div key={item.product_id} className="flex items-start justify-between gap-2">
                            <div className="flex items-start gap-1.5 min-w-0">
                              {item.is_veg
                                ? <Leaf size={10} className="text-emerald-500 mt-0.5 shrink-0" />
                                : <span className="w-2.5 h-2.5 rounded-sm border border-red-500 mt-0.5 shrink-0 flex items-center justify-center"><span className="w-1.5 h-1.5 rounded-full bg-red-500" /></span>}
                              <span className="text-xs text-surface-800 leading-tight">{item.name}</span>
                            </div>
                            <div className="text-right shrink-0">
                              {item.variants && item.variants.length > 1 ? (
                                <div className="space-y-0.5">
                                  {item.variants.slice(0, 2).map(v => (
                                    <p key={v.variant_id} className="text-[10px] text-surface-500">
                                      {v.variant_name} <span className="text-surface-700 font-medium">₹{v.price.toFixed(0)}</span>
                                    </p>
                                  ))}
                                </div>
                              ) : (
                                <span className="text-xs font-medium text-surface-700">₹{item.price.toFixed(0)}</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

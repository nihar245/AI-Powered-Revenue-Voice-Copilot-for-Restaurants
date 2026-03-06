import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Mic,
  MicOff,
  Sparkles,
  CheckCircle2,
  ShoppingCart,
  RotateCcw,
  Zap,
  Languages,
  Send,
  Keyboard,
  Volume2,
  AlertCircle,
} from 'lucide-react'
import { API_URL } from '../config'

export default function VoiceOrder() {
  /* ── state ─────────────────────────────────────────────── */
  const [mode, setMode] = useState('voice')                 // voice | text
  const [phase, setPhase] = useState('idle')                 // idle | recording | processing | ready
  const [sessionId] = useState(() => crypto.randomUUID())
  const [transcript, setTranscript] = useState('')
  const [aiResponse, setAiResponse] = useState('')
  const [cart, setCart] = useState([])
  const [cartTotal, setCartTotal] = useState('₹0')
  const [upsellChips, setUpsellChips] = useState([])
  const [activeCombos, setActiveCombos] = useState([])
  const [pendingClarification, setPendingClarification] = useState(null)
  const [language, setLanguage] = useState('—')
  const [latency, setLatency] = useState(null)
  const [confirmed, setConfirmed] = useState(false)
  const [orderId, setOrderId] = useState(null)
  const [error, setError] = useState(null)
  const [textInput, setTextInput] = useState('')
  const [aiHealthy, setAiHealthy] = useState(null)

  const mediaRecorder = useRef(null)
  const audioChunks = useRef([])
  const audioRef = useRef(null)

  /* ── health check on mount ─────────────────────────────── */
  useEffect(() => {
    fetch(`${API_URL}/voice/health`).then(r => r.json())
      .then(d => setAiHealthy(d.status === 'ok'))
      .catch(() => setAiHealthy(false))
  }, [])

  /* ── helpers ────────────────────────────────────────────── */
  const applyResponse = useCallback((data) => {
    if (data.transcript)     setTranscript(data.transcript)
    if (data.response_text)  setAiResponse(data.response_text)
    if (data.cart)           setCart(data.cart)
    if (data.cart_total)     setCartTotal(data.cart_total)
    if (data.language)       setLanguage(data.language)
    if (data.upsell_chips)   setUpsellChips(data.upsell_chips)
    if (data.active_combos)  setActiveCombos(data.active_combos)
    setPendingClarification(data.pending_clarification || null)
    if (data.latency_ms != null) setLatency(data.latency_ms)
    else if (data.live_ms != null) setLatency(data.live_ms)

    // Play back audio if present
    if (data.audio_b64 && audioRef.current) {
      audioRef.current.src = `data:audio/wav;base64,${data.audio_b64}`
      audioRef.current.play().catch(() => {})
    }
  }, [])

  /* ── audio recording ───────────────────────────────────── */
  const startRecording = async () => {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
      audioChunks.current = []
      recorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.current.push(e.data) }
      recorder.onstop = () => { stream.getTracks().forEach(t => t.stop()); sendAudio() }
      recorder.start()
      mediaRecorder.current = recorder
      setPhase('recording')
    } catch {
      setError('Microphone access denied. Use text mode instead.')
    }
  }

  const stopRecording = () => {
    if (mediaRecorder.current && mediaRecorder.current.state === 'recording') {
      mediaRecorder.current.stop()
    }
  }

  const sendAudio = async () => {
    setPhase('processing')
    const blob = new Blob(audioChunks.current, { type: 'audio/webm' })
    const form = new FormData()
    form.append('audio', blob, 'voice.webm')
    form.append('session_id', sessionId)

    try {
      const t0 = performance.now()
      const res = await fetch(`${API_URL}/voice/turn`, { method: 'POST', body: form })
      const elapsed = Math.round(performance.now() - t0)
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const data = await res.json()
      if (!data.latency_ms && !data.live_ms) data.latency_ms = elapsed
      applyResponse(data)
      setPhase('ready')
    } catch (err) {
      setError(err.message || 'Failed to process audio')
      setPhase('ready')
    }
  }

  /* ── text chat ─────────────────────────────────────────── */
  const sendText = async () => {
    if (!textInput.trim()) return
    setPhase('processing')
    setError(null)
    setTranscript(textInput)
    const body = { session_id: sessionId, user_text: textInput }
    setTextInput('')
    try {
      const t0 = performance.now()
      const res = await fetch(`${API_URL}/voice/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const elapsed = Math.round(performance.now() - t0)
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const data = await res.json()
      if (!data.latency_ms) data.latency_ms = elapsed
      applyResponse(data)
      setPhase('ready')
    } catch (err) {
      setError(err.message || 'Failed to process text')
      setPhase('ready')
    }
  }

  /* ── upsell chip click ─────────────────────────────────── */
  const handleUpsellClick = async (chip) => {
    try {
      const res = await fetch(`${API_URL}/voice/add-item`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          product_id: chip.product_id,
          item_name: chip.item_name,
          quantity: 1,
        }),
      })
      if (!res.ok) throw new Error(`Server error ${res.status}`)
      const data = await res.json()
      applyResponse(data)
      setUpsellChips(c => c.filter(x => x.product_id !== chip.product_id))
    } catch (err) {
      setError(err.message)
    }
  }

  /* ── confirm order ─────────────────────────────────────── */
  const confirmOrder = async () => {
    // Send a confirm intent through the chat endpoint
    const body = { session_id: sessionId, user_text: 'Confirm order' }
    try {
      const res = await fetch(`${API_URL}/voice/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      applyResponse(data)
      if (data.order_id) setOrderId(data.order_id)
      setConfirmed(true)
    } catch (err) {
      setError(err.message)
    }
  }

  /* ── reset ──────────────────────────────────────────────── */
  const reset = async () => {
    try {
      await fetch(`${API_URL}/voice/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      })
    } catch { /* ignore */ }
    setPhase('idle'); setTranscript(''); setAiResponse(''); setCart([])
    setCartTotal('₹0'); setUpsellChips([]); setActiveCombos([])
    setPendingClarification(null); setConfirmed(false); setOrderId(null)
    setError(null); setLanguage('—'); setLatency(null)
  }

  /* ── mic button handler ─────────────────────────────────── */
  const handleMicClick = () => {
    if (phase === 'recording') stopRecording()
    else if (phase === 'idle' || phase === 'ready') startRecording()
  }

  /* ── derived ────────────────────────────────────────────── */
  const cartSubtotal = cart.reduce((s, i) => s + (i.unit_price || 0) * (i.quantity || 1), 0)

  return (
    <div className="p-6 animate-fade-in">
      <audio ref={audioRef} className="hidden" />

      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900">Voice Ordering</h1>
          <p className="text-surface-400 text-sm mt-0.5">
            AI-powered Gemini voice assistant with upsell suggestions
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Mode toggle */}
          <button
            onClick={() => setMode(m => m === 'voice' ? 'text' : 'voice')}
            className="btn-secondary text-xs flex items-center gap-1.5 py-1.5 px-3"
          >
            {mode === 'voice' ? <Keyboard size={13} /> : <Volume2 size={13} />}
            {mode === 'voice' ? 'Text mode' : 'Voice mode'}
          </button>
          {/* AI health dot */}
          <span className={`w-2.5 h-2.5 rounded-full ${aiHealthy === true ? 'bg-emerald-500' : aiHealthy === false ? 'bg-red-500' : 'bg-surface-300'}`}
                title={aiHealthy === true ? 'AI service connected' : 'AI service offline'} />
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-4 flex items-center gap-2 text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-2.5 text-sm animate-fade-in">
          <AlertCircle size={15} /> {error}
          <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600">&times;</button>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">

        {/* ── Left column ── */}
        <div className="lg:col-span-2 space-y-5">

          {/* Language badge */}
          <div className="flex items-center gap-2 flex-wrap">
            {['Hindi', 'English', 'Tamil', 'Telugu', 'Marathi'].map(lang => (
              <span key={lang} className={`text-xs px-3 py-1 rounded-full border font-medium transition-all
                ${language.toLowerCase() === lang.toLowerCase()
                  ? 'bg-primary-50 text-primary-600 border-primary-200'
                  : 'text-surface-500 border-surface-200 bg-surface-50'}
              `}>
                <Languages size={11} className="inline mr-1" />{lang}
              </span>
            ))}
          </div>

          {/* Mic / Text input */}
          {mode === 'voice' ? (
            <div className="card p-8 flex flex-col items-center gap-6">
              <div className="relative">
                {phase === 'recording' && (
                  <>
                    <div className="absolute inset-[-16px] rounded-full bg-red-500/10 animate-ping" style={{ animationDuration: '1.5s' }} />
                    <div className="absolute inset-[-32px] rounded-full bg-red-500/5 animate-ping" style={{ animationDuration: '2s', animationDelay: '0.5s' }} />
                  </>
                )}
                <button
                  onClick={handleMicClick}
                  disabled={phase === 'processing' || confirmed}
                  className={`relative w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl
                    ${phase === 'recording'
                      ? 'bg-red-500 hover:bg-red-400 shadow-red-500/40 scale-110'
                      : phase === 'processing'
                        ? 'bg-amber-500 shadow-amber-500/30'
                        : 'bg-primary-600 hover:bg-primary-700 shadow-red-btn hover:scale-105'}
                  `}
                >
                  {phase === 'processing'
                    ? <span className="w-6 h-6 border-3 border-white/30 border-t-white rounded-full animate-spin" style={{ borderWidth: 3 }} />
                    : phase === 'recording'
                      ? <MicOff size={28} className="text-white" />
                      : <Mic size={28} className="text-white" />}
                </button>
              </div>
              <div className="text-center">
                <p className="text-surface-900 font-semibold text-sm">
                  {phase === 'idle' && 'Press to start voice ordering'}
                  {phase === 'recording' && 'Listening… click to stop'}
                  {phase === 'processing' && 'Processing with Gemini AI…'}
                  {phase === 'ready' && 'Tap mic to continue conversation'}
                </p>
                <p className="text-surface-400 text-xs mt-1">
                  {phase === 'idle' ? 'Supports Hindi, English, Tamil, Telugu & more' : 'Powered by Gemini Live API'}
                </p>
              </div>
            </div>
          ) : (
            <div className="card p-4 flex gap-3">
              <input
                type="text"
                value={textInput}
                onChange={(e) => setTextInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendText()}
                placeholder="Type your order… e.g. 'Ek paneer tikka aur coke dena'"
                className="flex-1 bg-surface-50 border border-surface-200 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-primary-400 transition-colors"
                disabled={phase === 'processing' || confirmed}
              />
              <button
                onClick={sendText}
                disabled={phase === 'processing' || confirmed || !textInput.trim()}
                className="btn-primary px-4 py-2.5 flex items-center gap-1.5 text-sm"
              >
                {phase === 'processing'
                  ? <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  : <Send size={15} />}
                Send
              </button>
            </div>
          )}

          {/* Transcript */}
          {(transcript || phase !== 'idle') && (
            <div className="card p-4 animate-fade-in">
              <p className="text-xs text-surface-400 uppercase tracking-wider font-semibold mb-2 flex items-center gap-1.5">
                <Zap size={11} className="text-primary-600" />You said
              </p>
              <div className="bg-surface-50 rounded-lg p-3 font-mono text-sm text-surface-700 min-h-[40px] border border-surface-200">
                {transcript || <span className="text-surface-400 italic">Waiting for speech…</span>}
                {phase === 'recording' && (
                  <span className="inline-block w-2 h-4 bg-primary-500 ml-0.5 animate-pulse align-[-2px]" />
                )}
              </div>
            </div>
          )}

          {/* AI response */}
          {aiResponse && (
            <div className="card p-4 border-l-4 border-l-primary-500 animate-fade-in">
              <p className="text-xs text-primary-600 uppercase tracking-wider font-semibold mb-2 flex items-center gap-1.5">
                <Sparkles size={11} />AI Response
              </p>
              <p className="text-surface-700 text-sm leading-relaxed">{aiResponse}</p>
            </div>
          )}

          {/* Pending clarification */}
          {pendingClarification && (
            <div className="card p-4 border-l-4 border-l-amber-500 bg-amber-50/50 animate-slide-up">
              <p className="text-amber-700 text-sm font-medium">{pendingClarification}</p>
            </div>
          )}

          {/* Upsell chips */}
          {upsellChips.length > 0 && !confirmed && (
            <div className="card p-4 border-l-4 border-l-violet-500 bg-violet-50/50 animate-slide-up">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles size={14} className="text-violet-600" />
                <p className="text-violet-600 text-sm font-semibold">AI Upsell Suggestions</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {upsellChips.map((chip, i) => (
                  <button
                    key={i}
                    onClick={() => handleUpsellClick(chip)}
                    className="px-3 py-1.5 rounded-full bg-violet-100 text-violet-700 text-xs font-medium
                               hover:bg-violet-200 transition-colors border border-violet-200"
                  >
                    + {chip.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Active combos */}
          {activeCombos.length > 0 && !confirmed && (
            <div className="card p-4 border-l-4 border-l-emerald-500 bg-emerald-50/50 animate-slide-up">
              <p className="text-xs text-emerald-600 uppercase tracking-wider font-semibold mb-2">
                Active Combo Deals
              </p>
              {activeCombos.map((combo, i) => (
                <div key={i} className="flex items-center justify-between text-sm py-1">
                  <span className="text-surface-700">{combo.combo_name || combo.name}</span>
                  {combo.saving > 0 && (
                    <span className="text-emerald-600 text-xs font-semibold">Save ₹{combo.saving}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Right column: cart + metrics ── */}
        <div className="space-y-4">
          <div className="card overflow-hidden">
            <div className="px-5 py-3.5 bg-surface-900 border-b border-surface-800 flex items-center gap-2">
              <ShoppingCart size={15} className="text-primary-400" />
              <span className="text-sm font-semibold text-white">Order Summary</span>
              {cart.length > 0 && (
                <span className="ml-auto text-xs text-surface-400">{cart.length} item{cart.length > 1 ? 's' : ''}</span>
              )}
            </div>

            <div className="p-5">
              {cart.length === 0 ? (
                <p className="text-surface-400 text-sm text-center py-6">
                  {phase === 'idle' ? 'Start voice ordering to see items here' : 'Cart is empty — keep ordering'}
                </p>
              ) : (
                <>
                  <div className="space-y-3 mb-4">
                    {cart.map((item, i) => (
                      <div key={i} className="flex items-center justify-between text-sm">
                        <div>
                          <p className="text-surface-900 font-medium">
                            {item.quantity > 1 && <span className="text-primary-600">{item.quantity}× </span>}
                            {item.name}
                          </p>
                          {item.variant_name && (
                            <p className="text-surface-400 text-xs">{item.variant_name}</p>
                          )}
                          {item.notes && (
                            <p className="text-surface-400 text-xs italic">{item.notes}</p>
                          )}
                        </div>
                        <span className="text-surface-500 font-medium">
                          ₹{((item.unit_price || 0) * (item.quantity || 1)).toFixed(0)}
                        </span>
                      </div>
                    ))}
                  </div>

                  <div className="border-t border-dashed border-surface-200 pt-3 mb-4">
                    <div className="flex items-center justify-between">
                      <span className="text-surface-400 text-sm">Total</span>
                      <span className="text-surface-900 font-bold text-lg">{cartTotal || `₹${cartSubtotal.toFixed(0)}`}</span>
                    </div>
                  </div>

                  {!confirmed ? (
                    <button onClick={confirmOrder} className="btn-primary w-full py-2.5 text-sm">
                      Confirm Order
                    </button>
                  ) : (
                    <div className="text-center">
                      <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-2">
                        <CheckCircle2 size={22} className="text-emerald-400" />
                      </div>
                      <p className="text-emerald-600 font-semibold text-sm">Order Confirmed!</p>
                      {orderId && <p className="text-surface-400 text-xs mt-0.5">Order #{orderId}</p>}
                      <p className="text-surface-400 text-xs mt-1">Sent to kitchen</p>
                      <button onClick={reset} className="mt-3 btn-ghost text-xs flex items-center gap-1.5 mx-auto">
                        <RotateCcw size={12} /> New Order
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          {/* AI Metrics */}
          {phase !== 'idle' && (
            <div className="card p-4 space-y-2 animate-fade-in">
              <p className="text-xs text-surface-400 uppercase tracking-wider font-semibold">AI Metrics</p>
              {[
                { label: 'Language', value: language },
                { label: 'Latency', value: latency != null ? `${latency}ms` : '—' },
                { label: 'Mode', value: mode === 'voice' ? 'Gemini Live Audio' : 'Text Pipeline' },
              ].map(({ label, value }) => (
                <div key={label} className="flex items-center justify-between">
                  <span className="text-surface-400 text-xs">{label}</span>
                  <span className="text-primary-600 text-xs font-semibold">{value}</span>
                </div>
              ))}
            </div>
          )}

          {/* Reset */}
          {phase !== 'idle' && !confirmed && (
            <button onClick={reset} className="btn-ghost text-xs flex items-center gap-1.5 mx-auto text-surface-400 hover:text-surface-600">
              <RotateCcw size={12} /> Reset session
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

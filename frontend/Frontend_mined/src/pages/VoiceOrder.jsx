import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Mic,
  MicOff,
  Sparkles,
  CheckCircle2,
  ShoppingCart,
  RotateCcw,
  Phone,
  PhoneOff,
  Send,
  Volume2,
  Loader2,
  AlertCircle,
  PhoneCall,
  MessageSquare,
  User,
  Bot,
} from 'lucide-react'
import { apiFetch, AI_SERVICE_WS, AI_SERVICE_ADMIN_WS } from '../config'

export default function VoiceOrder() {
  // ── Connection state ──
  const [connected, setConnected] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [error, setError] = useState(null)

  // ── Phone call state ──
  const [phoneCallActive, setPhoneCallActive] = useState(false)
  const [phoneCaller, setPhoneCaller] = useState(null)

  // ── Conversation state ──
  const [messages, setMessages] = useState([])
  const [recording, setRecording] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [textInput, setTextInput] = useState('')

  // ── Order state (from ai_service session) ──
  const [order, setOrder] = useState({ items: [], total: 0 })
  const [confirmed, setConfirmed] = useState(false)
  const [confirmResult, setConfirmResult] = useState(null)
  const [cartFlash, setCartFlash] = useState(false)

  // ── AI metrics ──
  const [metrics, setMetrics] = useState({})

  // ── Name-capture modal (triggered after phone order_confirmed) ──
  const [showNameModal, setShowNameModal] = useState(false)
  const [capturedName, setCapturedName]   = useState('')
  const [pendingConfirmData, setPendingConfirmData] = useState(null)
  const [confirmingOrder, setConfirmingOrder]       = useState(false)

  // ── Refs ──
  const wsRef = useRef(null)
  const adminWsRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const chatEndRef = useRef(null)
  const audioContextRef = useRef(null)

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, processing])

  // ── Cleanup on unmount ──
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        try { wsRef.current.close() } catch {}
      }
      if (adminWsRef.current) {
        try { adminWsRef.current.close() } catch {}
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        try { mediaRecorderRef.current.stop() } catch {}
      }
    }
  }, [])

  // ── Subscribe to phone-call broadcasts from /ws/admin ──
  // This is separate from the browser-demo WS (/ws/conversation).
  // All Twilio phone call events arrive here as { event, data, timestamp }.
  useEffect(() => {
    let ws
    let reconnectTimer

    const connect = () => {
      ws = new WebSocket(AI_SERVICE_ADMIN_WS)
      adminWsRef.current = ws

      ws.onmessage = (rawEvt) => {
        let msg
        try { msg = JSON.parse(rawEvt.data) } catch { return }

        const evType = msg.event
        const data   = msg.data || {}

        if (evType === 'call_started') {
          setPhoneCallActive(true)
          setPhoneCaller(data.caller || 'Unknown')
          // Show incoming call banner in chat
          setMessages(prev => [...prev, {
            role: 'system',
            text: `📞 Incoming call from ${data.caller || 'unknown number'}`,
            ts:   Date.now(),
          }])
          // Reset order/confirmed for the new call
          setOrder({ items: [], total: 0 })
          setConfirmed(false)
          setConfirmResult(null)
        }

        if (evType === 'transcript_received' && data.transcript) {
          setMessages(prev => [...prev, {
            role: 'user',
            text: data.transcript,
            ts:   Date.now(),
          }])
        }

        if (evType === 'response_generated') {
          if (data.transcript) {
            setMessages(prev => [...prev, {
              role: 'user',
              text: data.transcript,
              ts:   Date.now(),
            }])
          }
          if (data.response_text) {
            setMessages(prev => [...prev, {
              role:  'agent',
              text:  data.response_text,
              ts:    Date.now(),
            }])
          }
          // Live cart update as items accumulate during the call
          if (data.order && Array.isArray(data.order.items) && data.order.items.length > 0) {
            setOrder(data.order)
            setCartFlash(true)
            setTimeout(() => setCartFlash(false), 800)
          }
          // Propagate language metric if present
          if (data.language) {
            setMetrics(prev => ({ ...prev, language: data.language }))
          }
        }

        if (evType === 'order_confirmed') {
          // Final confirmed order — use items/total directly from broadcast
          const items = Array.isArray(data.items) ? data.items : (data.order?.items || [])
          const total = data.total ?? data.order?.total ?? 0
          setOrder({ items, total })
          setPhoneCallActive(false)
          setMessages(prev => [...prev, {
            role: 'system',
            text: `✅ Order confirmed — ₹${typeof total === 'number' ? total.toFixed(2) : total}`,
            ts:   Date.now(),
          }])
          // For phone calls: show name-capture modal before sending to DB
          // For browser demo: auto-confirm (the user can click Confirm Order button)
          if (data.channel === 'phone' || phoneCaller) {
            setPendingConfirmData({ items, total, customer_name: data.customer_name || '', phone: data.phone || phoneCaller || '' })
            setCapturedName(data.customer_name || '')
            setShowNameModal(true)
          } else {
            setConfirmed(true)
            setConfirmResult({ success: true, message: 'Order placed!' })
          }
        }

        if (evType === 'call_ended') {
          setPhoneCallActive(false)
          setMessages(prev => [...prev, {
            role: 'system',
            text: '📴 Call ended',
            ts:   Date.now(),
          }])
        }
      }

      ws.onerror = () => {}
      ws.onclose = () => {
        // Auto-reconnect after 3 s so a service restart doesn't drop updates
        reconnectTimer = setTimeout(connect, 3000)
      }
    }

    connect()
    return () => {
      clearTimeout(reconnectTimer)
      try { ws?.close() } catch {}
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Play audio from base64 (WAV or MP3) ──
  const playAudio = useCallback((base64Audio, audioFormat) => {
    if (!base64Audio) return
    try {
      const bytes = Uint8Array.from(atob(base64Audio), c => c.charCodeAt(0))
      const mime = audioFormat === 'mp3' ? 'audio/mpeg' : 'audio/wav'
      const blob = new Blob([bytes], { type: mime })
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audio.onended = () => URL.revokeObjectURL(url)
      audio.play().catch(() => {})
    } catch (e) {
      console.warn('Audio playback failed:', e)
    }
  }, [])

  // ── Start Call: connect WebSocket ──
  const startCall = useCallback(async () => {
    setError(null)
    setMessages([])
    setOrder({ items: [], total: 0 })
    setConfirmed(false)
    setConfirmResult(null)
    setMetrics({})

    try {
      const ws = new WebSocket(AI_SERVICE_WS)
      wsRef.current = ws

      ws.onopen = () => {
        ws.send(JSON.stringify({ type: 'start' }))
      }

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data)

        if (msg.type === 'session_started') {
          setSessionId(msg.session_id)
          setConnected(true)
          setMessages([{
            role: 'agent',
            text: msg.message || 'Call started. Speak or type your order!',
            ts: Date.now(),
          }])
        }

        if (msg.type === 'response') {
          setProcessing(false)

          // If there's a transcript (from audio), update the pending user message
          if (msg.transcript) {
            setMessages(prev => {
              const updated = [...prev]
              // Find the last pending user message and replace it
              for (let i = updated.length - 1; i >= 0; i--) {
                if (updated[i].role === 'user' && updated[i].pending) {
                  updated[i] = { ...updated[i], text: msg.transcript, pending: false }
                  break
                }
              }
              return updated
            })
          }

          // Add agent response to chat (text arrives instantly)
          setMessages(prev => [...prev, {
            role: 'agent',
            text: msg.agent_text,
            ts: Date.now(),
          }])

          // Update order from session
          if (msg.order && msg.order.items && msg.order.items.length > 0) {
            setOrder(msg.order)
          }

          // Update metrics
          setMetrics(prev => ({
            ...prev,
            language: msg.language || prev.language,
            turnNumber: msg.turn_number,
            lastDuration: msg.duration_ms,
          }))

          // Play audio if included (backward compat)
          if (msg.audio_base64) {
            playAudio(msg.audio_base64, msg.audio_format)
          }
        }

        // Audio arrives separately (after text for faster perceived response)
        if (msg.type === 'audio_ready') {
          if (msg.audio_base64) {
            playAudio(msg.audio_base64, msg.audio_format)
          }
        }

        if (msg.type === 'session_ended') {
          setConnected(false)
          setMessages(prev => [...prev, {
            role: 'system',
            text: 'Call ended.',
            ts: Date.now(),
          }])
        }

        if (msg.type === 'error') {
          setProcessing(false)
          setError(msg.message)
        }
      }

      ws.onerror = () => {
        setError('WebSocket connection failed. Is ai_service running on port 8001?')
        setConnected(false)
      }

      ws.onclose = () => {
        setConnected(false)
      }
    } catch (e) {
      setError('Could not connect: ' + e.message)
    }
  }, [playAudio])

  // ── End Call ──
  const endCall = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'end' }))
      wsRef.current.close()
    }
    setConnected(false)
    setRecording(false)
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
  }, [])

  // ── Toggle Mic: start/stop recording ──
  const toggleMic = useCallback(async () => {
    if (recording) {
      // Stop recording
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop()
      }
      setRecording(false)
      return
    }

    // Start recording
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : 'audio/webm',
      })
      mediaRecorderRef.current = recorder
      audioChunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data)
      }

      recorder.onstop = async () => {
        // Stop all tracks
        stream.getTracks().forEach(t => t.stop())

        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        if (blob.size < 100) return // Too small, ignore

        // Convert to base64
        const reader = new FileReader()
        reader.onload = () => {
          const base64 = reader.result.split(',')[1]
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            setProcessing(true)
            setMessages(prev => [...prev, {
              role: 'user',
              text: '🎤 (speaking...)',
              ts: Date.now(),
              pending: true,
            }])
            wsRef.current.send(JSON.stringify({
              type: 'audio',
              data: base64,
            }))
          }
        }
        reader.readAsDataURL(blob)
      }

      recorder.start()
      setRecording(true)
    } catch (e) {
      setError('Microphone access denied. Please allow microphone access.')
    }
  }, [recording])

  // ── Send text message ──
  const sendText = useCallback(() => {
    const text = textInput.trim()
    if (!text || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return

    setMessages(prev => [...prev, { role: 'user', text, ts: Date.now() }])
    setProcessing(true)
    setTextInput('')

    wsRef.current.send(JSON.stringify({ type: 'text', data: text }))
  }, [textInput])

  // ── Update user transcript when response arrives ──
  useEffect(() => {
    // When a response arrives, check if the last user message was a pending audio message
    // and update it with the actual transcript
    const lastAgent = [...messages].reverse().find(m => m.role === 'agent')
    if (!lastAgent) return
    // Messages are already handled by the response handler
  }, [messages])

  // ── Submit name + save order to DB (called from name-capture modal) ──
  const submitNameAndSave = useCallback(async (skipName = false) => {
    if (!pendingConfirmData) { setShowNameModal(false); return }
    setConfirmingOrder(true)
    try {
      const result = await apiFetch('/voice/confirm-order', {
        method: 'POST',
        body: JSON.stringify({
          items: pendingConfirmData.items.map(i => ({
            name: i.name,
            quantity: i.quantity,
            modifications: i.modifications || [],
          })),
          channel: 'phone',
          customer_name: skipName ? '' : capturedName.trim(),
          phone: pendingConfirmData.phone,
        }),
      })
      setConfirmResult(result)
      setConfirmed(true)
      setMessages(prev => [...prev, {
        role: 'system',
        text: `📋 Saved as Order #${result.order_id} for ${capturedName.trim() || 'Guest'}`,
        ts: Date.now(),
      }])
    } catch (e) {
      setError('Could not save order: ' + e.message)
    } finally {
      setConfirmingOrder(false)
      setShowNameModal(false)
      setPendingConfirmData(null)
    }
  }, [pendingConfirmData, capturedName])

  // ── Confirm Order via backend (browser demo button) ──
  const confirmOrder = useCallback(async () => {
    if (!order.items || order.items.length === 0) return

    try {
      const result = await apiFetch('/voice/confirm-order', {
        method: 'POST',
        body: JSON.stringify({
          items: order.items.map(i => ({
            name: i.name,
            quantity: i.quantity,
            modifications: i.modifications || [],
          })),
          channel: 'dine_in',
        }),
      })
      setConfirmResult(result)
      setConfirmed(true)
    } catch (e) {
      setError('Order confirmation failed: ' + e.message)
    }
  }, [order])

  // ── Reset everything ──
  const reset = useCallback(() => {
    endCall()
    setMessages([])
    setOrder({ items: [], total: 0 })
    setConfirmed(false)
    setConfirmResult(null)
    setMetrics({})
    setError(null)
    setSessionId(null)
    setPhoneCallActive(false)
    setPhoneCaller(null)
    setShowNameModal(false)
    setCapturedName('')
    setPendingConfirmData(null)
  }, [endCall])

  const total = order.total || order.items?.reduce((s, i) => s + (i.subtotal || i.price * i.quantity || 0), 0) || 0

  return (
    <div className="p-6 animate-fade-in">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900">Voice Ordering</h1>
          <p className="text-surface-400 text-sm mt-0.5">
            Gemini Live — Native Audio-in / Audio-out · Real-time DB menu
          </p>
        </div>
        <div className="flex items-center gap-3">
          {phoneCallActive && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 border border-emerald-200 rounded-full">
              <PhoneCall size={13} className="text-emerald-600 animate-pulse" />
              <span className="text-xs text-emerald-700 font-semibold">Active Call</span>
              {phoneCaller && <span className="text-xs text-emerald-500">{phoneCaller}</span>}
            </div>
          )}
          {connected && (
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs text-emerald-600 font-medium">Live</span>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 flex items-center gap-2 text-red-700 text-sm">
          <AlertCircle size={16} />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-700">×</button>
        </div>
      )}

      <div className="grid lg:grid-cols-3 gap-6">

        {/* ── Left column: Conversation ── */}
        <div className="lg:col-span-2 space-y-4">

          {/* Browser demo call: Start/End controls */}
          {!connected && (
            <div className="card p-5 flex items-center gap-4">
              <div className="w-14 h-14 rounded-full bg-primary-600 flex items-center justify-center shadow-xl hover:bg-primary-700 hover:scale-105 transition-all cursor-pointer flex-shrink-0"
                   onClick={startCall}>
                <Phone size={24} className="text-white" />
              </div>
              <div>
                <p className="text-surface-900 font-semibold text-sm">Browser Demo Call</p>
                <p className="text-surface-400 text-xs mt-0.5">
                  Click to start a web demo — or use a real phone call below
                </p>
              </div>
            </div>
          )}

          {/* Live conversation panel — shown for browser call OR phone call */}
          {(connected || phoneCallActive || messages.length > 0) && (
            <>
              {/* Chat messages */}
              <div className="card overflow-hidden">
                <div className="px-4 py-2.5 border-b border-surface-100 flex items-center gap-2">
                  <MessageSquare size={13} className="text-surface-400" />
                  <span className="text-xs font-semibold text-surface-500 uppercase tracking-wider">Conversation</span>
                  {phoneCallActive && (
                    <span className="ml-auto flex items-center gap-1 text-xs text-emerald-600">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse inline-block" />
                      Live
                    </span>
                  )}
                </div>
                <div className="p-4 max-h-[400px] overflow-y-auto space-y-3">
                  {messages.length === 0 && (
                    <p className="text-surface-400 text-sm text-center py-8">
                      {phoneCallActive ? 'Waiting for customer to speak…' : 'Start a call to see the conversation here'}
                    </p>
                  )}
                  {messages.map((msg, i) => (
                    <div key={i} className={`flex items-end gap-2 ${
                      msg.role === 'user' ? 'justify-end' : msg.role === 'system' ? 'justify-center' : 'justify-start'
                    }`}>
                      {msg.role === 'agent' && (
                        <div className="w-6 h-6 rounded-full bg-primary-100 flex items-center justify-center flex-shrink-0 mb-0.5">
                          <Bot size={12} className="text-primary-600" />
                        </div>
                      )}
                      <div className={`max-w-[78%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
                        msg.role === 'user'
                          ? 'bg-primary-600 text-white rounded-br-sm'
                          : msg.role === 'system'
                            ? 'bg-surface-100 text-surface-500 text-xs italic px-3 py-1.5 rounded-lg'
                            : 'bg-surface-100 text-surface-800 rounded-bl-sm'
                      }`}>
                        {msg.role === 'agent' && (
                          <span className="text-xs text-primary-500 font-semibold block mb-0.5 flex items-center gap-1">
                            <Volume2 size={10} className="inline" /> Aria
                          </span>
                        )}
                        {msg.role === 'user' && (
                          <span className="text-xs text-primary-200 font-medium block mb-0.5 flex items-center gap-1">
                            <User size={10} className="inline" /> Customer
                          </span>
                        )}
                        {msg.text}
                      </div>
                      {msg.role === 'user' && (
                        <div className="w-6 h-6 rounded-full bg-primary-600 flex items-center justify-center flex-shrink-0 mb-0.5">
                          <User size={12} className="text-white" />
                        </div>
                      )}
                    </div>
                  ))}
                  {processing && (
                    <div className="flex justify-start items-end gap-2">
                      <div className="w-6 h-6 rounded-full bg-primary-100 flex items-center justify-center">
                        <Bot size={12} className="text-primary-600" />
                      </div>
                      <div className="bg-surface-100 text-surface-500 px-4 py-2.5 rounded-2xl rounded-bl-sm text-sm flex items-center gap-2">
                        <Loader2 size={14} className="animate-spin" />
                        Thinking…
                      </div>
                    </div>
                  )}
                  <div ref={chatEndRef} />
                </div>
              </div>

              {/* Browser call controls — only when connected via web */}
              {connected && (
                <div className="card p-4">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={toggleMic}
                      disabled={processing}
                      className={`w-12 h-12 rounded-full flex items-center justify-center transition-all shadow-lg flex-shrink-0 ${
                        recording
                          ? 'bg-red-500 hover:bg-red-400 shadow-red-500/40 scale-110 animate-pulse'
                          : 'bg-primary-600 hover:bg-primary-700 shadow-primary-500/30'
                      } ${processing ? 'opacity-50 cursor-not-allowed' : ''}`}
                    >
                      {recording ? <MicOff size={20} className="text-white" /> : <Mic size={20} className="text-white" />}
                    </button>
                    <div className="flex-1 flex items-center gap-2">
                      <input
                        type="text"
                        value={textInput}
                        onChange={e => setTextInput(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && sendText()}
                        placeholder="Or type your order here..."
                        disabled={processing}
                        className="flex-1 bg-surface-50 border border-surface-200 rounded-lg px-3 py-2.5 text-sm outline-none focus:border-primary-400 transition-colors"
                      />
                      <button
                        onClick={sendText}
                        disabled={!textInput.trim() || processing}
                        className="w-10 h-10 rounded-lg bg-primary-600 text-white flex items-center justify-center hover:bg-primary-700 disabled:opacity-40 transition-all"
                      >
                        <Send size={16} />
                      </button>
                    </div>
                    <button
                      onClick={endCall}
                      className="w-12 h-12 rounded-full bg-red-500 hover:bg-red-400 flex items-center justify-center shadow-lg flex-shrink-0 transition-all"
                      title="End call"
                    >
                      <PhoneOff size={18} className="text-white" />
                    </button>
                  </div>
                  <div className="flex items-center justify-between mt-2 px-1">
                    <p className="text-xs text-surface-400">
                      {recording ? '🔴 Recording... click mic to stop' : 'Click mic to speak, or type below'}
                    </p>
                    {sessionId && <p className="text-xs text-surface-400">Session: {sessionId}</p>}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* ── Right column: Order summary + Metrics ── */}
        <div className="space-y-4">
          <div className={`card overflow-hidden transition-all duration-300 ${
            cartFlash ? 'ring-2 ring-emerald-400 ring-offset-1' : ''
          }`}>
            <div className="px-5 py-3.5 bg-surface-900 border-b border-surface-800 flex items-center gap-2">
              <ShoppingCart size={15} className="text-primary-400" />
              <span className="text-sm font-semibold text-white">Order Summary</span>
              {cartFlash && (
                <span className="ml-auto text-xs text-emerald-400 animate-pulse font-medium">Updated ✓</span>
              )}
            </div>

            <div className="p-5">
              {(!order.items || order.items.length === 0) ? (
                <p className="text-surface-400 text-sm text-center py-6">
                  {connected || phoneCallActive ? 'Speak your order to add items' : 'Start a call to begin ordering'}
                </p>
              ) : (
                <>
                  <div className="space-y-3 mb-4">
                    {order.items.map((item, i) => (
                      <div key={i} className="flex items-start justify-between text-sm py-1 border-b border-surface-50 last:border-0">
                        <div className="flex items-start gap-2">
                          <span className="w-5 h-5 rounded-full bg-primary-100 text-primary-700 text-xs font-bold flex items-center justify-center flex-shrink-0 mt-0.5">
                            {item.quantity}
                          </span>
                          <div>
                            <p className="text-surface-900 font-medium">{item.name}</p>
                            {item.modifications?.length > 0 && (
                              <p className="text-surface-400 text-xs">{item.modifications.join(', ')}</p>
                            )}
                          </div>
                        </div>
                        <span className="text-surface-600 font-semibold flex-shrink-0 ml-2">
                          ₹{item.subtotal || (item.price * item.quantity) || 0}
                        </span>
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
                      onClick={confirmOrder}
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
                      {confirmResult && (
                        <p className="text-surface-400 text-xs mt-1">
                          Order #{confirmResult.order_id} — ₹{confirmResult.total} — Sent to kitchen
                        </p>
                      )}
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

          {/* Gemini panel */}
          {(connected || phoneCallActive) && (
            <div className="card p-4 space-y-2 animate-fade-in">
              <p className="text-xs text-surface-400 uppercase tracking-wider font-semibold flex items-center gap-1">
                <Sparkles size={11} /> Gemini
              </p>
              {[
                { label: 'Language', value: metrics.language || 'en' },
                { label: 'Conversation Turn', value: metrics.turnNumber || 0 },
                { label: 'Last Response', value: metrics.lastDuration ? `${(metrics.lastDuration / 1000).toFixed(1)}s` : '—' },
                { label: 'Pipeline', value: 'Gemini Live' },
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

      {/* ── Name-capture modal ── */}
      {showNameModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl p-7 w-full max-w-sm mx-4 animate-fade-in">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center">
                <User size={18} className="text-primary-600" />
              </div>
              <div>
                <h3 className="font-bold text-surface-900 text-base">Save Customer Details</h3>
                <p className="text-surface-400 text-xs">Optional — for future reference</p>
              </div>
            </div>

            {pendingConfirmData?.phone && (
              <div className="mb-3 px-3 py-2 bg-surface-50 rounded-lg flex items-center gap-2">
                <Phone size={13} className="text-surface-400" />
                <span className="text-sm text-surface-700 font-medium">{pendingConfirmData.phone}</span>
              </div>
            )}

            <label className="block text-xs font-semibold text-surface-500 mb-1">Customer Name</label>
            <input
              type="text"
              value={capturedName}
              onChange={e => setCapturedName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && submitNameAndSave()}
              placeholder="e.g. Rahul Sharma"
              autoFocus
              className="w-full border border-surface-200 rounded-lg px-3 py-2.5 text-sm outline-none focus:border-primary-400 transition-colors mb-4"
            />

            <div className="flex gap-2">
              <button
                onClick={() => submitNameAndSave(true)}
                disabled={confirmingOrder}
                className="flex-1 py-2 border border-surface-200 rounded-lg text-sm text-surface-500 hover:bg-surface-50 transition-colors"
              >
                Skip
              </button>
              <button
                onClick={() => submitNameAndSave(false)}
                disabled={confirmingOrder}
                className="flex-1 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg text-sm font-semibold flex items-center justify-center gap-1.5 transition-colors"
              >
                {confirmingOrder
                  ? <Loader2 size={14} className="animate-spin" />
                  : <CheckCircle2 size={14} />}
                Save &amp; Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

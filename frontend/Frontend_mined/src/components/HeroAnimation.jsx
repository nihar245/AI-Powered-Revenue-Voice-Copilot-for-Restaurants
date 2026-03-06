import { useEffect, useRef, useState } from 'react'

const TOTAL_FRAMES = 105

export default function HeroAnimation() {
  const canvasRef = useRef(null)
  const imagesRef = useRef([])
  const frameRef = useRef(0)
  const [loaded, setLoaded] = useState(false)
  const [loadProgress, setLoadProgress] = useState(0)
  const [hasFrames, setHasFrames] = useState(true)

  // Try loading first frame to check if frames exist
  useEffect(() => {
    const testImg = new Image()
    testImg.onload = () => setHasFrames(true)
    testImg.onerror = () => setHasFrames(false)
    testImg.src = '/assets/frames/frame_001.png'
  }, [])

  useEffect(() => {
    if (!hasFrames) return

    let loadedCount = 0
    const images = []

    for (let i = 1; i <= TOTAL_FRAMES; i++) {
      const img = new Image()
      const num = String(i).padStart(3, '0')
      img.src = `/assets/frames/frame_${num}.png`
      img.onload = () => {
        loadedCount++
        setLoadProgress(Math.round((loadedCount / TOTAL_FRAMES) * 100))
        if (loadedCount === TOTAL_FRAMES) setLoaded(true)
      }
      img.onerror = () => {
        loadedCount++
        if (loadedCount === TOTAL_FRAMES) setLoaded(true)
      }
      images.push(img)
    }
    imagesRef.current = images
  }, [hasFrames])

  useEffect(() => {
    if (!loaded || !hasFrames) return

    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    const drawFrame = (idx) => {
      const img = imagesRef.current[idx]
      if (!img) return
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    }

    const handleScroll = () => {
      const scrollY = window.scrollY
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight
      const progress = Math.min(scrollY / (maxScroll * 0.4), 1)
      const frameIndex = Math.min(
        Math.floor(progress * (TOTAL_FRAMES - 1)),
        TOTAL_FRAMES - 1
      )
      frameRef.current = frameIndex
      drawFrame(frameIndex)
    }

    drawFrame(0)
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [loaded, hasFrames])

  // Fallback animation when no frames exist
  if (!hasFrames) {
    return (
      <div className="relative w-full h-full flex items-center justify-center">
        {/* Animated bowl placeholder */}
        <div className="relative">
          {/* Glow rings */}
          <div className="absolute inset-0 rounded-full bg-sky-500/20 animate-ping" style={{ animationDuration: '3s' }} />
          <div className="absolute inset-[-20px] rounded-full border border-sky-500/20 animate-pulse" />
          <div className="absolute inset-[-40px] rounded-full border border-sky-500/10 animate-pulse" style={{ animationDelay: '1s' }} />

          {/* Bowl SVG illustration */}
          <div className="w-52 h-52 relative animate-float">
            <svg viewBox="0 0 200 200" className="w-full h-full drop-shadow-2xl">
              <defs>
                <radialGradient id="bowlGrad" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#1e3a5f" />
                  <stop offset="100%" stopColor="#0f172a" />
                </radialGradient>
                <linearGradient id="noodleGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#f59e0b" />
                  <stop offset="100%" stopColor="#ef4444" />
                </linearGradient>
                <linearGradient id="rimGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#334155" />
                  <stop offset="100%" stopColor="#1e293b" />
                </linearGradient>
              </defs>
              {/* Bowl body */}
              <ellipse cx="100" cy="130" rx="75" ry="50" fill="url(#bowlGrad)" />
              <ellipse cx="100" cy="100" rx="75" ry="30" fill="url(#rimGrad)" />
              <ellipse cx="100" cy="100" rx="75" ry="30" fill="none" stroke="#475569" strokeWidth="2" />
              {/* Noodles */}
              <path d="M 60 110 Q 80 95 100 110 Q 120 125 140 110" stroke="url(#noodleGrad)" strokeWidth="4" fill="none" strokeLinecap="round" />
              <path d="M 65 120 Q 85 105 100 118 Q 118 132 135 120" stroke="url(#noodleGrad)" strokeWidth="3.5" fill="none" strokeLinecap="round" opacity="0.8" />
              <path d="M 70 115 Q 90 100 110 115 Q 125 127 145 115" stroke="#f59e0b" strokeWidth="3" fill="none" strokeLinecap="round" opacity="0.6" />
              {/* Steam */}
              <path d="M 80 85 Q 75 72 80 60" stroke="#94a3b8" strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.4" />
              <path d="M 100 80 Q 95 65 100 52" stroke="#94a3b8" strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.5" />
              <path d="M 120 85 Q 115 70 120 57" stroke="#94a3b8" strokeWidth="2" fill="none" strokeLinecap="round" opacity="0.4" />
            </svg>
          </div>

          {/* Falling particles */}
          {[...Array(6)].map((_, i) => (
            <div
              key={i}
              className="absolute w-1.5 h-1.5 rounded-full bg-sky-400/60"
              style={{
                top: `${10 + i * 8}%`,
                left: `${30 + i * 10}%`,
                animation: `float ${2 + i * 0.4}s ease-in-out infinite`,
                animationDelay: `${i * 0.3}s`,
              }}
            />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="relative w-full h-full flex items-center justify-center">
      {!loaded && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 z-10">
          <div className="w-48 h-1 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full bg-sky-400 rounded-full transition-all duration-300"
              style={{ width: `${loadProgress}%` }}
            />
          </div>
          <span className="text-slate-500 text-xs">Loading animation… {loadProgress}%</span>
        </div>
      )}
      <canvas
        ref={canvasRef}
        width={520}
        height={520}
        className={`rounded-2xl transition-opacity duration-700 ${loaded ? 'opacity-100' : 'opacity-0'}`}
        style={{ imageRendering: 'crisp-edges' }}
      />
    </div>
  )
}

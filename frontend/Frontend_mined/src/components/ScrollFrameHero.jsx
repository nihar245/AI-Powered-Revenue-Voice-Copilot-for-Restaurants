import { useEffect, useRef, useState } from 'react'

// ─── Frame paths ──────────────────────────────────────────────────────────────
const TOTAL_FRAMES = 105

const frames = Array.from(
  { length: TOTAL_FRAMES },
  (_, i) => new URL(
    `../assets/frames/ezgif-frame-${String(i + 1).padStart(3, '0')}.jpg`,
    import.meta.url
  ).href
)

// ─── Component ────────────────────────────────────────────────────────────────
/**
 * ScrollFrameHero
 * ─────────────────────────────────────────────────────────────────────────────
 * Apple-style scroll animation: a 300vh section with a sticky full-screen
 * container whose background image advances through 105 frames in sync with
 * scroll position.
 *
 * Layout
 *   <section class="relative h-[300vh] bg-black">
 *     <div class="sticky top-0 h-screen …">
 *       ← background-image div (single element, no <img> per frame)
 *       ← gradient overlay
 *       ← hero text
 *     </div>
 *   </section>
 *
 * Props
 *   showOverlay  – render hero text overlay (default true)
 *   onComplete   – optional callback fired once when all frames have played
 */
export default function ScrollFrameHero({ showOverlay = true, onComplete }) {
  const sectionRef     = useRef(null)
  const rafIdRef       = useRef(null)
  const lastIndexRef   = useRef(-1)
  const completeFired  = useRef(false)

  const [currentFrame, setCurrentFrame] = useState(frames[0])

  // ── 1. Preload all frames on mount ─────────────────────────────────────────
  useEffect(() => {
    frames.forEach((src) => {
      const img = new Image()
      img.src = src
    })
    // Display frame 1 immediately (already the default state, but be explicit)
    setCurrentFrame(frames[0])
    lastIndexRef.current = 0
  }, [])

  // ── 2. Scroll → frame mapping ───────────────────────────────────────────────
  useEffect(() => {
    const onScroll = () => {
      // One rAF queued at a time — no redundant work between paint calls
      if (rafIdRef.current !== null) return

      rafIdRef.current = requestAnimationFrame(() => {
        rafIdRef.current = null

        const section = sectionRef.current
        if (!section) return

        // scrollProgress relative to the section, not the whole document
        const { top, height } = section.getBoundingClientRect()
        const viewH = window.innerHeight

        // px scrolled past the top of the section
        const scrolled  = Math.max(-top, 0)
        // total scrollable distance inside the section
        const maxScroll = Math.max(height - viewH, 1)
        // clamp [0, 1]
        const progress  = Math.min(scrolled / maxScroll, 1)

        const frameIndex = Math.min(
          Math.floor(progress * (TOTAL_FRAMES - 1)),
          TOTAL_FRAMES - 1
        )

        // Only call setState when the index actually changes
        if (frameIndex !== lastIndexRef.current) {
          lastIndexRef.current = frameIndex
          setCurrentFrame(frames[frameIndex])
        }

        // Fire onComplete once when the last frame is reached
        if (progress >= 1 && !completeFired.current) {
          completeFired.current = true
          onComplete?.()
        } else if (progress < 1) {
          completeFired.current = false
        }
      })
    }

    window.addEventListener('scroll', onScroll, { passive: true })
    onScroll() // compute correct frame if page loads mid-scroll

    return () => {
      window.removeEventListener('scroll', onScroll)
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current)
    }
  }, [onComplete])

  // ── 3. Render ───────────────────────────────────────────────────────────────
  return (
    <section
      ref={sectionRef}
      className="relative h-[300vh] bg-black"
    >
      {/* Sticky viewport — pinned while the tall section scrolls past */}
      <div className="sticky top-0 h-screen w-full overflow-hidden flex items-center justify-center">

        {/* ── Frame background — single div, background-image is swapped ── */}
        <div
          className="absolute inset-0 bg-center bg-contain bg-no-repeat"
          style={{ backgroundImage: `url(${currentFrame})` }}
        />

        {/* ── Gradient vignette for text legibility ── */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              'linear-gradient(to bottom, rgba(0,0,0,0.5) 0%, rgba(0,0,0,0.1) 45%, rgba(0,0,0,0.6) 100%)',
          }}
        />

        {/* ── Hero text overlay ── */}
        {showOverlay && (
          <div className="relative z-10 flex flex-col items-center justify-center px-6 text-center select-none pointer-events-none">
            {/* Pill badge */}
            <span className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-sm border border-white/20 text-white/90 text-xs font-semibold px-3 py-1.5 rounded-full mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
              AI-Powered Restaurant OS
            </span>

            {/* Headline */}
            <h1 className="text-4xl sm:text-5xl lg:text-[4rem] font-extrabold text-white leading-tight tracking-tight mb-5 drop-shadow-xl max-w-3xl">
              AI Revenue &amp; Voice{' '}
              <span className="text-red-400">Copilot</span>{' '}
              for Restaurants
            </h1>

            {/* Subtitle */}
            <p className="text-white/70 text-lg sm:text-xl leading-relaxed max-w-xl drop-shadow-md">
              Turn POS data into revenue insights and automate phone ordering
              with&nbsp;AI.
            </p>
          </div>
        )}
      </div>
    </section>
  )
}

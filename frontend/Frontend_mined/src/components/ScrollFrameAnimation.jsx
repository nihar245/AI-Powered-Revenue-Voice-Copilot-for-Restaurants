import { useEffect, useRef } from 'react'

// ─── Configuration ────────────────────────────────────────────────────────────
const TOTAL_FRAMES = 105

/**
 * Returns the public path for a given 1-based frame index.
 * e.g. framePath(1) → '/assets/frames/frame_001.png'
 */
function framePath(index) {
  return new URL(
    `../assets/frames/ezgif-frame-${String(index).padStart(3, '0')}.jpg`,
    import.meta.url
  ).href
}

// Preload all frame paths into an array once (module-level, not per-mount)
const FRAME_PATHS = Array.from({ length: TOTAL_FRAMES }, (_, i) => framePath(i + 1))

// ─── Component ────────────────────────────────────────────────────────────────
/**
 * ScrollFrameAnimation
 * ─────────────────────────────────────────────────────────────────────────────
 * A full-screen hero section that plays a 105-frame sequence as the user
 * scrolls.  The animation container is `sticky` so it stays pinned to the
 * viewport while the tall outer section drives scroll progress.
 *
 * Layout:
 *   <section>  height = 300vh  ← scroll container
 *     <div>    sticky h-screen  ← pinned viewport
 *       <img>                   ← single element, src is swapped per rAF tick
 *       <div>  overlay          ← hero text rendered on top
 *     </div>
 *   </section>
 *
 * Props
 *  scrollHeight  – total height of the scroll container (default "300vh")
 *  showOverlay   – whether to render the hero text overlay (default true)
 *  onScrollEnd   – optional callback fired once when progress reaches 1
 */
export default function ScrollFrameAnimation({
  scrollHeight = '300vh',
  showOverlay  = true,
  onScrollEnd,
}) {
  const sectionRef   = useRef(null)
  const imgRef       = useRef(null)
  const rafIdRef     = useRef(null)   // pending rAF id
  const lastIndexRef = useRef(-1)     // last rendered frame index (0-based)
  const endFiredRef  = useRef(false)  // guard for onScrollEnd

  // ── 1. Preload all frames on mount ─────────────────────────────────────────
  useEffect(() => {
    // Kick off parallel downloads; browser caches them for <img> src swaps
    FRAME_PATHS.forEach((src) => {
      const img = new Image()
      img.src = src
    })

    // Show frame 1 immediately before any scroll happens
    if (imgRef.current) {
      imgRef.current.src = FRAME_PATHS[0]
      lastIndexRef.current = 0
    }

    return () => {
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current)
    }
  }, [])

  // ── 2. Scroll → frame logic ─────────────────────────────────────────────────
  useEffect(() => {
    const onScroll = () => {
      // Throttle: skip if a rAF is already queued
      if (rafIdRef.current !== null) return

      rafIdRef.current = requestAnimationFrame(() => {
        rafIdRef.current = null

        const section = sectionRef.current
        const img     = imgRef.current
        if (!section || !img) return

        const { top, height } = section.getBoundingClientRect()
        const viewH = window.innerHeight

        // px the section top has moved above the viewport top
        const scrolled  = Math.max(-top, 0)
        // full scrollable range so the last frame shows before the section exits
        const maxScroll = height - viewH
        // clamp progress to [0, 1]
        const progress   = maxScroll > 0 ? Math.min(scrolled / maxScroll, 1) : 0
        const frameIndex = Math.min(
          Math.floor(progress * (TOTAL_FRAMES - 1)),
          TOTAL_FRAMES - 1
        )

        // Only touch the DOM when the frame actually changes
        if (frameIndex !== lastIndexRef.current) {
          img.src = FRAME_PATHS[frameIndex]
          lastIndexRef.current = frameIndex
        }

        // Fire onScrollEnd once when the animation completes
        if (progress >= 1 && !endFiredRef.current) {
          endFiredRef.current = true
          onScrollEnd?.()
        } else if (progress < 1) {
          endFiredRef.current = false
        }
      })
    }

    window.addEventListener('scroll', onScroll, { passive: true })
    // Run once so the correct frame shows if the page loads mid-scroll
    onScroll()

    return () => {
      window.removeEventListener('scroll', onScroll)
      if (rafIdRef.current) cancelAnimationFrame(rafIdRef.current)
    }
  }, [onScrollEnd])

  // ── 3. Render ───────────────────────────────────────────────────────────────
  return (
    <section
      ref={sectionRef}
      className="relative bg-black"
      style={{ height: scrollHeight }}
    >
      {/* Sticky viewport — stays pinned while the outer section scrolls */}
      <div className="sticky top-0 w-full h-screen overflow-hidden flex items-center justify-center">

        {/* Single frame image — full-cover, never more than one in the DOM */}
        <img
          ref={imgRef}
          alt=""
          aria-hidden="true"
          draggable={false}
          className="w-full h-full object-cover select-none pointer-events-none"
        />

        {/* Darkening gradient so overlay text stays legible on any frame */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              'linear-gradient(to bottom, rgba(0,0,0,0.45) 0%, rgba(0,0,0,0.15) 50%, rgba(0,0,0,0.55) 100%)',
          }}
        />

        {/* Hero text overlay */}
        {showOverlay && (
          <div className="absolute inset-0 flex flex-col items-center justify-center px-6 text-center pointer-events-none select-none">
            {/* Pill badge */}
            <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur-sm border border-white/20 text-white/90 text-xs font-semibold px-3 py-1.5 rounded-full mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
              AI-Powered Restaurant OS
            </div>

            {/* Headline */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white leading-tight mb-5 drop-shadow-lg max-w-3xl">
              AI Revenue &amp; Voice{' '}
              <span className="text-red-400">Copilot</span>{' '}
              for Restaurants
            </h1>

            {/* Subtitle */}
            <p className="text-white/75 text-lg sm:text-xl leading-relaxed max-w-xl drop-shadow">
              Turn POS data into revenue insights and automate phone ordering
              with&nbsp;AI. Serve&nbsp;more, earn&nbsp;more, stress&nbsp;less.
            </p>
          </div>
        )}
      </div>
    </section>
  )
}

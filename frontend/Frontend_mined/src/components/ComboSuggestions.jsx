import { useState, useEffect, useCallback } from 'react'
import { ShoppingBag, ChevronLeft, ChevronRight, Flame } from 'lucide-react'
import { apiFetch } from '../config'

const LIMIT = 5

// Skeleton card shown while loading
function SkeletonCard() {
  return (
    <div className="w-44 shrink-0 rounded-xl border border-orange-100 bg-orange-50 p-3 animate-pulse">
      <div className="h-3 w-3/4 bg-orange-200 rounded mb-2" />
      <div className="h-2 w-1/2 bg-orange-100 rounded mb-3" />
      <div className="h-6 w-full bg-orange-200 rounded" />
    </div>
  )
}

export default function ComboSuggestions({ onAddCombo }) {
  const [combos, setCombos]   = useState([])
  const [page, setPage]       = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [loading, setLoading] = useState(true)

  const fetchPage = useCallback((p) => {
    setLoading(true)
    apiFetch(`/combos/suggestions?page=${p}&limit=${LIMIT}`)
      .then(data => {
        setCombos(data.combos || [])
        setTotalPages(data.total_pages || 1)
        setPage(data.page || p)
      })
      .catch(() => setCombos([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { fetchPage(1) }, [fetchPage])

  // Don't render the strip at all when there's nothing to show (after loading)
  if (!loading && combos.length === 0) return null

  return (
    <div className="mb-3 shrink-0">
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <Flame size={14} className="text-orange-500" />
          <span className="text-xs font-semibold text-orange-700 uppercase tracking-wide">
            Suggested Combos
          </span>
          <span className="text-[10px] text-orange-400 font-medium">· frequently ordered together</span>
        </div>
        {totalPages > 1 && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => fetchPage(page - 1)}
              disabled={page <= 1 || loading}
              className="p-0.5 rounded text-orange-400 hover:text-orange-600 disabled:opacity-30 transition-colors"
            >
              <ChevronLeft size={14} />
            </button>
            <span className="text-[10px] text-orange-400 font-medium">{page}/{totalPages}</span>
            <button
              onClick={() => fetchPage(page + 1)}
              disabled={page >= totalPages || loading}
              className="p-0.5 rounded text-orange-400 hover:text-orange-600 disabled:opacity-30 transition-colors"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>

      {/* Card strip */}
      <div className="flex gap-2 overflow-x-auto pb-1 custom-scrollbar">
        {loading
          ? Array.from({ length: LIMIT }).map((_, i) => <SkeletonCard key={i} />)
          : combos.map(combo => (
              <div
                key={combo.combo_id}
                className="w-44 shrink-0 rounded-xl border border-orange-200 bg-gradient-to-b from-orange-50 to-white p-3 flex flex-col gap-1.5"
              >
                {/* Header: label + size/lift badges */}
                <div className="flex items-start justify-between gap-1">
                  <p className="text-xs font-semibold text-surface-800 leading-tight line-clamp-2 flex-1">
                    {combo.combo_label || combo.combo_name}
                  </p>
                  <div className="flex flex-col items-end gap-0.5 shrink-0">
                    <span className="text-[9px] font-bold bg-orange-100 text-orange-700 px-1 py-0.5 rounded">
                      {combo.combo_size === 2 ? 'Pair' : `${combo.combo_size}-item`}
                    </span>
                    {combo.lift > 2 && (
                      <span className="text-[9px] font-bold bg-emerald-100 text-emerald-600 px-1 py-0.5 rounded">
                        {combo.lift.toFixed(1)}×
                      </span>
                    )}
                  </div>
                </div>

                {/* Item pills */}
                <div className="flex flex-wrap gap-1">
                  {(combo.items || []).map(item => (
                    <span
                      key={item.item_id}
                      className="text-[9px] bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded-full font-medium"
                    >
                      {item.qty > 1 ? `${item.qty}× ` : ''}{item.name}
                    </span>
                  ))}
                </div>

                {/* Price row */}
                <div className="flex items-baseline gap-1.5 mt-auto">
                  <span className="text-sm font-bold text-orange-600">₹{combo.combo_price}</span>
                  {combo.saving > 0 && (
                    <span className="text-[9px] text-emerald-600 font-semibold bg-emerald-50 px-1 py-0.5 rounded">
                      save {combo.saving_pct}%
                    </span>
                  )}
                </div>

                {/* Add button */}
                <button
                  onClick={() => onAddCombo && onAddCombo(combo)}
                  className="mt-1 w-full flex items-center justify-center gap-1 text-[10px] font-semibold text-white bg-orange-500 hover:bg-orange-600 active:scale-95 rounded-lg py-1.5 transition-all"
                >
                  <ShoppingBag size={10} />
                  Add Combo
                </button>
              </div>
            ))
        }
      </div>
    </div>
  )
}

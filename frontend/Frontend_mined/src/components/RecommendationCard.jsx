import { Sparkles, Plus, TrendingUp } from 'lucide-react'

export default function RecommendationCard({ item }) {
  const rec = item

  if (!rec) {
    return (
      <div className="card p-5 border-l-4 border-l-primary-500">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-6 h-6 rounded-md bg-primary-50 flex items-center justify-center">
            <Sparkles size={13} className="text-primary-600" />
          </div>
          <h3 className="text-sm font-semibold text-surface-900">AI Upsell Recommendation</h3>
        </div>
        <p className="text-surface-400 text-xs">Select an order to see AI-powered upsell suggestions.</p>
      </div>
    )
  }

  return (
    <div className="card p-5 border-l-4 border-l-primary-500 animate-slide-in-right">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <div className="w-7 h-7 rounded-lg bg-primary-50 flex items-center justify-center">
          <Sparkles size={14} className="text-primary-600" />
        </div>
        <h3 className="text-sm font-semibold text-surface-900">AI Upsell Recommendation</h3>
      </div>

      {/* Algorithm badge */}
      <div className="text-xs text-surface-400 italic mb-3">
        Generated using Apriori association analysis
      </div>

      <p className="text-surface-600 text-xs mb-4 leading-relaxed">
        Customers who order{' '}
        <span className="text-primary-600 font-semibold">{rec.baseItem}</span>{' '}
        often add{' '}
        <span className="text-primary-600 font-semibold">{rec.combo}</span>.
      </p>

      {/* Combo box */}
      <div className="bg-surface-50 border border-surface-200 rounded-lg p-3 mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-surface-400 uppercase tracking-wider font-medium">Suggested Combo</span>
          <div className="flex items-center gap-1 text-emerald-600 text-xs font-semibold">
            <TrendingUp size={11} />
            +₹{rec.revenue}
          </div>
        </div>
        <p className="text-surface-900 font-semibold text-sm">
          {rec.baseItem} + {rec.combo}
        </p>
      </div>

      {/* Confidence */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-xs mb-1.5">
          <span className="text-surface-400">Confidence</span>
          <span className="text-primary-600 font-bold">{rec.confidence}%</span>
        </div>
        <div className="h-1.5 bg-surface-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-primary-600 to-primary-400 rounded-full transition-all duration-700"
            style={{ width: `${rec.confidence}%` }}
          />
        </div>
      </div>

      <button className="w-full btn-primary py-2 text-sm flex items-center justify-center gap-2">
        <Plus size={14} />
        Add To Order
      </button>
    </div>
  )
}


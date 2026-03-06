import { useState, useEffect, useMemo } from 'react'
import { apiFetch } from '../config'
import { Plus, Pencil, Trash2, X, ChevronDown, ChevronUp, Package, Leaf, Search } from 'lucide-react'

const badgeColor = {
  veg: 'text-emerald-700 bg-emerald-50 border-emerald-200',
  nonveg: 'text-red-700 bg-red-50 border-red-200',
  jain: 'text-amber-700 bg-amber-50 border-amber-200',
}

const quadrantConfig = {
  Star:        { label: 'Star',       cls: 'text-emerald-700 bg-emerald-50 border-emerald-200', icon: '★' },
  'Plow Horse':{ label: 'Plow Horse', cls: 'text-rose-700 bg-rose-50 border-rose-200',           icon: '⚡' },
  Puzzle:      { label: 'Puzzle',     cls: 'text-violet-700 bg-violet-50 border-violet-200',     icon: '?' },
  Dog:         { label: 'Dog',        cls: 'text-orange-700 bg-orange-50 border-orange-200',     icon: '·' },
}

function getQuadrant(rankPct, avgMargin) {
  const highPop    = rankPct >= 50
  const highMargin = avgMargin >= 40
  if (highPop && highMargin)   return 'Star'
  if (highPop && !highMargin)  return 'Plow Horse'
  if (!highPop && highMargin)  return 'Puzzle'
  return 'Dog'
}

export default function Products() {
  const [products, setProducts] = useState([])
  const [categories, setCategories] = useState([])
  const [ingredients, setIngredients] = useState([])
  const [analyticsMap, setAnalyticsMap] = useState({})
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [catFilter, setCatFilter] = useState('')
  const [expanded, setExpanded] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState(null)
  const [saving, setSaving] = useState(false)

  const emptyForm = {
    name: '', description: '', category_id: '', is_veg: true, is_jain: false,
    tags: '', image_url: '',
    variants: [{ variant_name: 'Regular', selling_price: '', gst_pct: 5, recipe: [] }],
  }
  const [form, setForm] = useState(emptyForm)

  const reload = () => {
    setLoading(true)
    Promise.all([
      apiFetch('/products').catch(() => []),
      apiFetch('/products/categories').catch(() => []),
      apiFetch('/products/ingredients').catch(() => []),
      apiFetch('/analytics/popularity-scoring').catch(() => []),
    ]).then(([p, c, i, ps]) => {
      setProducts(Array.isArray(p) ? p : [])
      setCategories(Array.isArray(c) ? c : [])
      setIngredients(Array.isArray(i) ? i : [])
      const map = {}
      if (Array.isArray(ps)) ps.forEach(s => { map[s.item_id] = s })
      setAnalyticsMap(map)
      setLoading(false)
    })
  }

  useEffect(() => { reload() }, [])

  const filtered = useMemo(() => {
    return products.filter(p => {
      if (search && !p.name.toLowerCase().includes(search.toLowerCase())) return false
      if (catFilter && String(p.category_id) !== catFilter) return false
      return true
    })
  }, [products, search, catFilter])

  const openEdit = async (id) => {
    try {
      const data = await apiFetch(`/products/${id}`)
      setForm({
        name: data.name,
        description: data.description || '',
        category_id: String(data.category_id),
        is_veg: data.is_veg,
        is_jain: data.is_jain,
        tags: data.tags || '',
        image_url: data.image_url || '',
        variants: data.variants.map(v => ({
          variant_name: v.variant_name,
          selling_price: String(v.selling_price),
          gst_pct: v.gst_pct,
          recipe: (v.recipe || []).map(r => ({ ing_id: String(r.ing_id), qty_required: String(r.qty_required) })),
        })),
      })
      setEditId(id)
      setShowForm(true)
    } catch (e) { console.error(e) }
  }

  const handleSave = async () => {
    if (!form.name || !form.category_id || form.variants.length === 0) return
    setSaving(true)
    try {
      const body = {
        ...form,
        category_id: parseInt(form.category_id),
        tags: form.tags || null,
        image_url: form.image_url || null,
        variants: form.variants.map(v => ({
          variant_name: v.variant_name,
          selling_price: parseFloat(v.selling_price) || 0,
          gst_pct: parseFloat(v.gst_pct) || 5,
          recipe: v.recipe.filter(r => r.ing_id && r.qty_required).map(r => ({
            ing_id: parseInt(r.ing_id),
            qty_required: parseFloat(r.qty_required),
          })),
        })),
      }
      if (editId) {
        await apiFetch(`/products/${editId}`, { method: 'PUT', body: JSON.stringify(body) })
      } else {
        await apiFetch('/products', { method: 'POST', body: JSON.stringify(body) })
      }
      setShowForm(false)
      setEditId(null)
      setForm(emptyForm)
      reload()
    } catch (e) { console.error(e) }
    setSaving(false)
  }

  const handleDelete = async (id) => {
    if (!confirm('Disable this product?')) return
    try {
      await apiFetch(`/products/${id}`, { method: 'DELETE' })
      reload()
    } catch (e) { console.error(e) }
  }

  const addVariant = () => setForm(f => ({ ...f, variants: [...f.variants, { variant_name: '', selling_price: '', gst_pct: 5, recipe: [] }] }))
  const removeVariant = (vi) => setForm(f => ({ ...f, variants: f.variants.filter((_, i) => i !== vi) }))
  const updateVariant = (vi, field, val) => setForm(f => ({ ...f, variants: f.variants.map((v, i) => i === vi ? { ...v, [field]: val } : v) }))

  const addRecipeLine = (vi) => setForm(f => ({
    ...f, variants: f.variants.map((v, i) => i === vi ? { ...v, recipe: [...v.recipe, { ing_id: '', qty_required: '' }] } : v)
  }))
  const removeRecipeLine = (vi, ri) => setForm(f => ({
    ...f, variants: f.variants.map((v, i) => i === vi ? { ...v, recipe: v.recipe.filter((_, j) => j !== ri) } : v)
  }))
  const updateRecipeLine = (vi, ri, field, val) => setForm(f => ({
    ...f, variants: f.variants.map((v, i) => i === vi ? { ...v, recipe: v.recipe.map((r, j) => j === ri ? { ...r, [field]: val } : r) } : v)
  }))

  const computeFoodCost = (recipe) => {
    const ingMap = Object.fromEntries(ingredients.map(i => [i.ing_id, i.cost_per_unit]))
    return recipe.reduce((sum, r) => sum + (ingMap[r.ing_id] || 0) * (parseFloat(r.qty_required) || 0), 0)
  }

  const totalProducts = products.length
  const activeProducts = products.filter(p => p.is_available).length

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full" />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-surface-900">Products</h1>
          <p className="text-surface-400 text-sm mt-0.5">Manage menu items, variants, recipes &amp; pricing</p>
        </div>
        <button onClick={() => { setForm(emptyForm); setEditId(null); setShowForm(true) }}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors">
          <Plus size={16} /> New Product
        </button>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Total Products', value: totalProducts, color: 'text-primary-600' },
          { label: 'Active', value: activeProducts, color: 'text-emerald-600' },
          { label: 'Disabled', value: totalProducts - activeProducts, color: 'text-red-500' },
          { label: 'Categories', value: categories.length, color: 'text-violet-600' },
        ].map(k => (
          <div key={k.label} className="card p-4">
            <p className="text-xs text-surface-400 font-medium mb-1">{k.label}</p>
            <p className={`text-2xl font-bold ${k.color}`}>{k.value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-surface-400" />
          <input type="text" value={search} onChange={e => setSearch(e.target.value)}
            className="pl-9 pr-3 py-2 border border-surface-200 rounded-lg text-sm w-64 focus:outline-none focus:ring-2 focus:ring-primary-300"
            placeholder="Search products..." />
        </div>
        <select value={catFilter} onChange={e => setCatFilter(e.target.value)}
          className="border border-surface-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300">
          <option value="">All Categories</option>
          {categories.map(c => <option key={c.category_id} value={c.category_id}>{c.name}</option>)}
        </select>
      </div>

      {/* Product list */}
      <div className="space-y-3">
        {filtered.length === 0 ? (
          <div className="card p-12 text-center">
            <Package size={40} className="mx-auto text-surface-300 mb-3" />
            <p className="text-surface-500 font-semibold">No products found</p>
            <p className="text-surface-400 text-sm mt-1">Create your first product to get started</p>
          </div>
        ) : filtered.map(p => {
          const isExpanded = expanded === p.item_id
          const variants = Array.isArray(p.variants) ? p.variants : []
          const priceRange = variants.length > 0
            ? `₹${Math.min(...variants.map(v => v.selling_price))} – ₹${Math.max(...variants.map(v => v.selling_price))}`
            : '—'
          const avgMargin = variants.length > 0
            ? Math.round(variants.reduce((s, v) => s + ((v.selling_price - v.food_cost) / (v.selling_price || 1)) * 100, 0) / variants.length)
            : 0
          const aData    = analyticsMap[p.item_id]
          const quadrant = aData ? getQuadrant(aData.rank_pct, avgMargin) : null
          const qConf    = quadrant ? quadrantConfig[quadrant] : null

          return (
            <div key={p.item_id} className={`card overflow-hidden transition-all ${!p.is_available ? 'opacity-60' : ''}`}>
              <div className="flex items-center gap-4 p-4 cursor-pointer hover:bg-surface-50 transition-colors"
                onClick={() => setExpanded(isExpanded ? null : p.item_id)}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-semibold text-surface-900 text-sm">{p.name}</h3>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-semibold ${p.is_veg ? badgeColor.veg : badgeColor.nonveg}`}>
                      {p.is_veg ? 'Veg' : 'Non-veg'}
                    </span>
                    {p.is_jain && <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-semibold ${badgeColor.jain}`}>Jain</span>}
                    {!p.is_available && <span className="text-[10px] px-1.5 py-0.5 rounded-full border font-semibold text-red-600 bg-red-50 border-red-200">Disabled</span>}
                    {qConf && (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full border font-semibold ${qConf.cls}`}>
                        {qConf.icon} {qConf.label}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-surface-400 mt-0.5">{p.category} · {variants.length} variant{variants.length !== 1 ? 's' : ''}</p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-sm font-bold text-surface-900">{priceRange}</p>
                  <p className={`text-xs font-semibold ${avgMargin >= 50 ? 'text-emerald-600' : avgMargin >= 30 ? 'text-amber-600' : 'text-red-600'}`}>
                    {avgMargin}% margin
                  </p>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <button onClick={e => { e.stopPropagation(); openEdit(p.item_id) }}
                    className="p-1.5 rounded-md hover:bg-surface-100 text-surface-400 hover:text-primary-600 transition-colors">
                    <Pencil size={14} />
                  </button>
                  <button onClick={e => { e.stopPropagation(); handleDelete(p.item_id) }}
                    className="p-1.5 rounded-md hover:bg-red-50 text-surface-400 hover:text-red-600 transition-colors">
                    <Trash2 size={14} />
                  </button>
                  {isExpanded ? <ChevronUp size={16} className="text-surface-400" /> : <ChevronDown size={16} className="text-surface-400" />}
                </div>
              </div>

              {isExpanded && (
                <div className="border-t border-surface-100 bg-surface-50/50 p-4">
                  {p.description && <p className="text-xs text-surface-500 mb-3">{p.description}</p>}
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-surface-200">
                        {['Variant', 'Selling Price', 'Food Cost', 'GST %', 'Margin', 'Profit/Unit'].map(h => (
                          <th key={h} className="text-left text-xs text-surface-400 font-semibold uppercase tracking-wider pb-2 pr-3">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-100">
                      {variants.map(v => {
                        const margin = v.selling_price > 0 ? Math.round(((v.selling_price - v.food_cost) / v.selling_price) * 100) : 0
                        const profit = (v.selling_price - v.food_cost).toFixed(2)
                        return (
                          <tr key={v.variant_id} className="hover:bg-white transition-colors">
                            <td className="py-2 pr-3 text-surface-900 font-medium text-xs">{v.variant_name}</td>
                            <td className="py-2 pr-3 text-surface-700 text-xs font-semibold">₹{v.selling_price}</td>
                            <td className="py-2 pr-3 text-surface-500 text-xs">₹{v.food_cost}</td>
                            <td className="py-2 pr-3 text-surface-500 text-xs">{v.gst_pct}%</td>
                            <td className="py-2 pr-3">
                              <span className={`text-xs font-bold ${margin >= 50 ? 'text-emerald-600' : margin >= 30 ? 'text-amber-600' : 'text-red-600'}`}>
                                {margin}%
                              </span>
                            </td>
                            <td className={`py-2 text-xs font-bold ${parseFloat(profit) >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>₹{profit}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* ── Create/Edit Modal ── */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 overflow-y-auto py-8">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-3xl p-6 relative animate-fade-in">
            <button onClick={() => { setShowForm(false); setEditId(null); setForm(emptyForm) }}
              className="absolute top-4 right-4 text-surface-400 hover:text-surface-600"><X size={18} /></button>
            <h3 className="text-lg font-bold text-surface-900 mb-5">{editId ? 'Edit Product' : 'New Product'}</h3>

            {/* Basic info */}
            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="col-span-2">
                <label className="text-sm font-medium text-surface-700 block mb-1">Product Name *</label>
                <input type="text" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                  className="w-full border border-surface-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300" placeholder="e.g. Butter Chicken" />
              </div>
              <div>
                <label className="text-sm font-medium text-surface-700 block mb-1">Category *</label>
                <select value={form.category_id} onChange={e => setForm({ ...form, category_id: e.target.value })}
                  className="w-full border border-surface-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300">
                  <option value="">Select category</option>
                  {categories.map(c => <option key={c.category_id} value={c.category_id}>{c.name}</option>)}
                </select>
              </div>
              <div className="flex items-end gap-4">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={form.is_veg} onChange={e => setForm({ ...form, is_veg: e.target.checked })} className="accent-emerald-600" />
                  <Leaf size={14} className="text-emerald-600" /> Veg
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={form.is_jain} onChange={e => setForm({ ...form, is_jain: e.target.checked })} className="accent-amber-600" />
                  Jain
                </label>
              </div>
              <div className="col-span-2">
                <label className="text-sm font-medium text-surface-700 block mb-1">Description</label>
                <input type="text" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
                  className="w-full border border-surface-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300" placeholder="Short description..." />
              </div>
            </div>

            {/* Variants */}
            <div className="mb-4 flex items-center justify-between">
              <h4 className="font-semibold text-surface-900 text-sm">Variants &amp; Recipes</h4>
              <button onClick={addVariant} className="flex items-center gap-1 text-xs text-primary-600 hover:text-primary-700 font-medium">
                <Plus size={14} /> Add Variant
              </button>
            </div>

            <div className="space-y-5">
              {form.variants.map((v, vi) => {
                const foodCost = computeFoodCost(v.recipe)
                const sellingPrice = parseFloat(v.selling_price) || 0
                const margin = sellingPrice > 0 ? Math.round(((sellingPrice - foodCost) / sellingPrice) * 100) : 0
                const profit = (sellingPrice - foodCost).toFixed(2)

                return (
                  <div key={vi} className="border border-surface-200 rounded-lg p-4 bg-surface-50/50">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-semibold text-surface-500 uppercase">Variant {vi + 1}</span>
                      {form.variants.length > 1 && (
                        <button onClick={() => removeVariant(vi)} className="text-red-400 hover:text-red-600"><X size={14} /></button>
                      )}
                    </div>

                    <div className="grid grid-cols-3 gap-3 mb-3">
                      <div>
                        <label className="text-xs font-medium text-surface-600 block mb-1">Variant Name *</label>
                        <input type="text" value={v.variant_name} onChange={e => updateVariant(vi, 'variant_name', e.target.value)}
                          className="w-full border border-surface-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300" placeholder="e.g. Half" />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-surface-600 block mb-1">Selling Price (₹) *</label>
                        <input type="number" min="0" step="any" value={v.selling_price} onChange={e => updateVariant(vi, 'selling_price', e.target.value)}
                          className="w-full border border-surface-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300" placeholder="0" />
                      </div>
                      <div>
                        <label className="text-xs font-medium text-surface-600 block mb-1">GST %</label>
                        <input type="number" min="0" max="100" value={v.gst_pct} onChange={e => updateVariant(vi, 'gst_pct', e.target.value)}
                          className="w-full border border-surface-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300" />
                      </div>
                    </div>

                    {/* Cost summary */}
                    <div className="flex gap-4 mb-3 text-xs">
                      <div className="px-3 py-1.5 rounded-md bg-white border border-surface-200">
                        <span className="text-surface-400">Food Cost:</span>{' '}
                        <span className="font-bold text-surface-700">₹{foodCost.toFixed(2)}</span>
                      </div>
                      <div className="px-3 py-1.5 rounded-md bg-white border border-surface-200">
                        <span className="text-surface-400">Margin:</span>{' '}
                        <span className={`font-bold ${margin >= 50 ? 'text-emerald-600' : margin >= 30 ? 'text-amber-600' : 'text-red-600'}`}>{margin}%</span>
                      </div>
                      <div className="px-3 py-1.5 rounded-md bg-white border border-surface-200">
                        <span className="text-surface-400">Profit:</span>{' '}
                        <span className={`font-bold ${parseFloat(profit) >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>₹{profit}</span>
                      </div>
                    </div>

                    {/* Recipe builder */}
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-semibold text-surface-500">Recipe Ingredients</span>
                        <button onClick={() => addRecipeLine(vi)} className="flex items-center gap-1 text-[11px] text-primary-600 hover:text-primary-700 font-medium">
                          <Plus size={12} /> Add Ingredient
                        </button>
                      </div>
                      {v.recipe.length === 0 ? (
                        <p className="text-xs text-surface-400 italic">No ingredients added. Food cost will be ₹0.</p>
                      ) : (
                        <div className="space-y-2">
                          {v.recipe.map((r, ri) => {
                            const ing = ingredients.find(i => i.ing_id === parseInt(r.ing_id))
                            const lineCost = ing ? (ing.cost_per_unit * (parseFloat(r.qty_required) || 0)).toFixed(2) : '0.00'
                            return (
                              <div key={ri} className="flex items-center gap-2">
                                <select value={r.ing_id} onChange={e => updateRecipeLine(vi, ri, 'ing_id', e.target.value)}
                                  className="flex-1 border border-surface-200 rounded-md px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-primary-300">
                                  <option value="">Select ingredient</option>
                                  {ingredients.map(i => <option key={i.ing_id} value={i.ing_id}>{i.name} (₹{i.cost_per_unit}/{i.unit})</option>)}
                                </select>
                                <input type="number" min="0.001" step="any" value={r.qty_required} onChange={e => updateRecipeLine(vi, ri, 'qty_required', e.target.value)}
                                  className="w-24 border border-surface-200 rounded-md px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-primary-300"
                                  placeholder={ing ? ing.unit : 'qty'} />
                                <span className="text-xs text-surface-500 w-16 text-right">₹{lineCost}</span>
                                <button onClick={() => removeRecipeLine(vi, ri)} className="text-red-400 hover:text-red-600"><X size={12} /></button>
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>

            <button onClick={handleSave} disabled={saving || !form.name || !form.category_id || form.variants.length === 0}
              className="w-full mt-6 py-2.5 bg-primary-600 text-white rounded-lg text-sm font-semibold hover:bg-primary-700 disabled:opacity-50 transition-colors">
              {saving ? 'Saving...' : editId ? 'Update Product' : 'Create Product'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

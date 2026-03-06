// ─── Orders ──────────────────────────────────────────────────────────────────
export const mockOrders = [
  {
    id: '#101',
    items: ['Paneer Pizza (L)', 'Coke'],
    price: 480,
    status: 'Served',
    source: 'Voice',
    details: [
      { name: 'Paneer Pizza (Large)', mods: ['Extra Cheese'], price: 420 },
      { name: 'Coke', mods: [], price: 60 },
    ],
  },
  {
    id: '#102',
    items: ['Burger', 'Fries', 'Lemonade'],
    price: 340,
    status: 'Ready',
    source: 'Manual',
    details: [
      { name: 'Classic Burger', mods: ['No Onion'], price: 220 },
      { name: 'French Fries', mods: [], price: 80 },
      { name: 'Lemonade', mods: [], price: 40 },
    ],
  },
  {
    id: '#103',
    items: ['Veg Thali'],
    price: 220,
    status: 'Preparing',
    source: 'Manual',
    details: [
      { name: 'Veg Thali', mods: ['Extra Roti'], price: 220 },
    ],
  },
  {
    id: '#104',
    items: ['Paneer Pizza (L)', 'Garlic Bread', 'Pepsi'],
    price: 580,
    status: 'Preparing',
    source: 'Voice',
    details: [
      { name: 'Paneer Pizza (Large)', mods: [], price: 420 },
      { name: 'Garlic Bread', mods: [], price: 100 },
      { name: 'Pepsi', mods: [], price: 60 },
    ],
  },
  {
    id: '#105',
    items: ['Pasta Arrabiata', 'Garlic Bread'],
    price: 360,
    status: 'Received',
    source: 'Manual',
    details: [
      { name: 'Pasta Arrabiata', mods: [], price: 260 },
      { name: 'Garlic Bread', mods: [], price: 100 },
    ],
  },
  {
    id: '#106',
    items: ['Margherita Pizza (M)', 'Sprite'],
    price: 390,
    status: 'Received',
    source: 'Voice',
    details: [
      { name: 'Margherita Pizza (Medium)', mods: [], price: 330 },
      { name: 'Sprite', mods: [], price: 60 },
    ],
  },
  {
    id: '#107',
    items: ['Chicken Tikka', 'Naan x2', 'Lassi'],
    price: 560,
    status: 'Served',
    source: 'Manual',
    details: [
      { name: 'Chicken Tikka', mods: ['Extra Spicy'], price: 380 },
      { name: 'Garlic Naan x2', mods: [], price: 120 },
      { name: 'Sweet Lassi', mods: [], price: 60 },
    ],
  },
  {
    id: '#108',
    items: ['Dal Makhani', 'Rice', 'Papad'],
    price: 280,
    status: 'Ready',
    source: 'Manual',
    details: [
      { name: 'Dal Makhani', mods: [], price: 200 },
      { name: 'Steamed Rice', mods: [], price: 60 },
      { name: 'Papad', mods: [], price: 20 },
    ],
  },
]

// ─── Dashboard KPIs ───────────────────────────────────────────────────────────
export const dashboardKPIs = {
  totalOrders: 147,
  totalRevenue: 58420,
  avgOrderValue: 397,
  topSellingItem: 'Paneer Pizza',
}

// ─── Hourly Orders Chart ──────────────────────────────────────────────────────
export const hourlyOrders = [
  { time: '9AM',  orders: 6,  revenue: 2100 },
  { time: '10AM', orders: 10, revenue: 3800 },
  { time: '11AM', orders: 14, revenue: 5200 },
  { time: '12PM', orders: 28, revenue: 10800 },
  { time: '1PM',  orders: 32, revenue: 12400 },
  { time: '2PM',  orders: 24, revenue: 9200 },
  { time: '3PM',  orders: 12, revenue: 4600 },
  { time: '4PM',  orders: 8,  revenue: 3100 },
  { time: '5PM',  orders: 10, revenue: 3900 },
  { time: '6PM',  orders: 22, revenue: 8700 },
  { time: '7PM',  orders: 36, revenue: 13800 },
  { time: '8PM',  orders: 42, revenue: 16200 },
  { time: '9PM',  orders: 30, revenue: 11600 },
]

// ─── Top Selling Items ────────────────────────────────────────────────────────
export const topItems = [
  { name: 'Paneer Pizza', orders: 48, revenue: 20160 },
  { name: 'Burger',       orders: 35, revenue: 7700  },
  { name: 'Garlic Bread', orders: 30, revenue: 3000  },
  { name: 'Coke',         orders: 28, revenue: 1680  },
  { name: 'Pasta',        orders: 22, revenue: 5720  },
  { name: 'Veg Thali',    orders: 18, revenue: 3960  },
]

// ─── Analytics – Menu Profitability ──────────────────────────────────────────
export const menuProfitability = [
  { name: 'Paneer Pizza',    popularity: 92, margin: 68, revenue: 20160 },
  { name: 'Burger',          popularity: 78, margin: 55, revenue: 7700  },
  { name: 'Garlic Bread',    popularity: 74, margin: 80, revenue: 3000  },
  { name: 'Pasta Arrabiata', popularity: 42, margin: 72, revenue: 5720  },
  { name: 'Veg Thali',       popularity: 38, margin: 45, revenue: 3960  },
  { name: 'Coke',            popularity: 70, margin: 60, revenue: 1680  },
  { name: 'Chicken Tikka',   popularity: 55, margin: 50, revenue: 9500  },
  { name: 'Dal Makhani',     popularity: 35, margin: 65, revenue: 4200  },
  { name: 'Lassi',           popularity: 28, margin: 75, revenue: 1680  },
  { name: 'Paneer Pasta',    popularity: 20, margin: 70, revenue: 2400  },
  { name: 'Naan',            popularity: 60, margin: 82, revenue: 2400  },
  { name: 'Margherita',      popularity: 50, margin: 62, revenue: 6600  },
]

// ─── Analytics – Combo Recommendations ───────────────────────────────────────
export const comboRecommendations = [
  { itemA: 'Paneer Pizza', itemB: 'Garlic Bread', confidence: 78, lift: 2.4 },
  { itemA: 'Burger',       itemB: 'Fries',        confidence: 85, lift: 3.1 },
  { itemA: 'Pasta',        itemB: 'Garlic Bread', confidence: 72, lift: 2.2 },
  { itemA: 'Chicken Tikka',itemB: 'Naan',         confidence: 88, lift: 3.4 },
  { itemA: 'Veg Thali',    itemB: 'Lassi',        confidence: 65, lift: 1.9 },
  { itemA: 'Margherita',   itemB: 'Coke',         confidence: 61, lift: 1.7 },
]

// ─── Analytics – Underperforming Items ────────────────────────────────────────
export const underperformingItems = [
  { name: 'Paneer Pasta',    sales: 'Low',    margin: 'High',   recommendation: 'Promote item' },
  { name: 'Dal Makhani',     sales: 'Low',    margin: 'Medium', recommendation: 'Bundle with Naan' },
  { name: 'Lassi',           sales: 'Medium', margin: 'High',   recommendation: 'Add to combos' },
  { name: 'Veg Thali',       sales: 'Low',    margin: 'Low',    recommendation: 'Review pricing' },
]

// ─── Upsell Recommendations ───────────────────────────────────────────────────
export const upsellRecommendations = {
  'Paneer Pizza': { combo: 'Garlic Bread', confidence: 78 },
  'Burger':       { combo: 'Fries',        confidence: 85 },
  'Pasta':        { combo: 'Garlic Bread', confidence: 72 },
  'Chicken Tikka':{ combo: 'Garlic Naan',  confidence: 88 },
}

// ─── Weekly Revenue (for one more chart) ──────────────────────────────────────
export const weeklyRevenue = [
  { day: 'Mon', revenue: 32000 },
  { day: 'Tue', revenue: 28500 },
  { day: 'Wed', revenue: 35200 },
  { day: 'Thu', revenue: 30800 },
  { day: 'Fri', revenue: 48600 },
  { day: 'Sat', revenue: 62400 },
  { day: 'Sun', revenue: 58420 },
]

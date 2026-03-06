import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiFetch, DATA_DATE } from '../config';

const POSContext = createContext();

export const usePOS = () => useContext(POSContext);

export const POSProvider = ({ children }) => {
    const [orders, setOrders] = useState([]);
    const [dashboardKPIs, setDashboardKPIs] = useState({
        totalOrdersToday: 0,
        totalRevenue: 0,
        avgOrderValue: 0,
        topSellingItem: '-',
        changes: { orders: null, revenue: null, aov: null },
    });
    const [loading, setLoading] = useState(true);

    // Transform backend order to frontend shape
    const mapOrder = (o) => ({
        id: `#${o.order_id}`,
        order_id: o.order_id,
        items: (o.items || []).filter(i => i.item_name).map(i => i.qty > 1 ? `${i.item_name} x${i.qty}` : i.item_name),
        price: parseFloat(o.total),
        status: o.status === 'placed' ? 'Received' : o.status === 'preparing' ? 'Preparing' : o.status === 'ready' ? 'Ready' : o.status === 'delivered' ? 'Served' : o.status,
        source: o.channel === 'voice' ? 'Voice' : 'Manual',
        type: o.channel === 'dine_in' ? 'Dine-in' : o.channel === 'delivery' ? 'Delivery' : 'Takeaway',
        createdAt: o.placed_at ? new Date(o.placed_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true }) : '',
        details: (o.items || []).filter(i => i.item_name).map(i => ({
            line_id: i.line_id,
            name: i.variant_name ? `${i.item_name} (${i.variant_name})` : i.item_name,
            mods: i.special_instructions ? [i.special_instructions] : [],
            price: parseFloat(i.revenue || i.unit_price * i.qty),
            qty: i.qty,
        })),
    });

    const fetchOrders = useCallback(async () => {
        try {
            const dateParam = DATA_DATE ? `?date=${DATA_DATE}&limit=50` : '?limit=50';
            const data = await apiFetch(`/orders${dateParam}`);
            setOrders(data.map(mapOrder));
        } catch {
            // keep current state on error
        }
    }, []);

    const fetchKPIs = useCallback(async () => {
        try {
            const dateParam = DATA_DATE ? `?date=${DATA_DATE}` : '';
            const data = await apiFetch(`/dashboard/kpis${dateParam}`);
            setDashboardKPIs({
                totalOrdersToday: Number(data.totalOrdersToday) || 0,
                totalRevenue: Number(data.totalRevenue) || 0,
                avgOrderValue: Number(data.avgOrderValue) || 0,
                topSellingItem: data.topSellingItem || '-',
                changes: data.changes || { orders: null, revenue: null, aov: null },
            });
        } catch {
            // keep defaults
        }
    }, []);

    useEffect(() => {
        Promise.all([fetchOrders(), fetchKPIs()]).finally(() => setLoading(false));

        // Auto-poll every 20s so Orders page stays in sync with Kitchen status changes
        const poll = setInterval(() => {
            fetchOrders();
            fetchKPIs();
        }, 20000);
        return () => clearInterval(poll);
    }, [fetchOrders, fetchKPIs]);

    const addOrder = async (orderPayload) => {
        try {
            const result = await apiFetch('/orders', {
                method: 'POST',
                body: JSON.stringify({
                    ...orderPayload,
                    // Pass order_date when using a pinned demo date so new orders
                    // appear in the same date bucket as the seed data.
                    ...(DATA_DATE ? { order_date: DATA_DATE } : {}),
                }),
            });
            // Refresh orders and KPIs after creating
            await Promise.all([fetchOrders(), fetchKPIs()]);
            return result;
        } catch (err) {
            throw err;
        }
    };

    const statusMap = { Received: 'placed', Preparing: 'preparing', Ready: 'ready', Served: 'delivered' };
    const updateOrderStatus = async (displayId, newStatus) => {
        const order = orders.find(o => o.id === displayId);
        if (!order) return;
        const backendStatus = statusMap[newStatus] || newStatus.toLowerCase();
        // Optimistic update immediately for snappy UI
        setOrders(prev => prev.map(o => o.id === displayId ? { ...o, status: newStatus } : o));
        try {
            await apiFetch(`/orders/${order.order_id}/status`, {
                method: 'PUT',
                body: JSON.stringify({ status: backendStatus }),
            });
            // Re-fetch from DB to stay in sync with Kitchen status changes
            await Promise.all([fetchOrders(), fetchKPIs()]);
        } catch {
            // Revert optimistic update on failure
            setOrders(prev => prev.map(o => o.id === displayId ? { ...o, status: order.status } : o));
        }
    };

    return (
        <POSContext.Provider value={{
            orders,
            addOrder,
            updateOrderStatus,
            dashboardKPIs,
            loading,
            refreshOrders: fetchOrders,
            refreshKPIs: fetchKPIs,
        }}>
            {children}
        </POSContext.Provider>
    );
};

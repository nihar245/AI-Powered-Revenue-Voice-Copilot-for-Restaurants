import { test, expect } from '@playwright/test'

const BASE = 'http://localhost:5173'

test.describe('AI Restaurant Copilot', () => {

  test('1 - Landing page loads with hero content', async ({ page }) => {
    await page.goto(BASE)
    await expect(page).toHaveTitle(/AI Restaurant Copilot/)
    await expect(page.locator('h1')).toContainText('AI Revenue')
    await expect(page.getByText('Turn POS data into revenue insights')).toBeVisible()
    await expect(page.getByRole('button', { name: /Login/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /Sign Up/i }).first()).toBeVisible()
  })

  test('2 - Login redirects to dashboard', async ({ page }) => {
    await page.goto(`${BASE}/login`)
    await expect(page.locator('h1')).toContainText('Welcome back')
    await page.fill('input[type="email"]', 'test@restaurant.com')
    await page.fill('input[type="password"]', 'password123')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(`${BASE}/dashboard`, { timeout: 5000 })
  })

  test('3 - Signup redirects to dashboard', async ({ page }) => {
    await page.goto(`${BASE}/signup`)
    await expect(page.locator('h1')).toContainText('Create your account')
    await page.fill('input[type="text"]', 'Spice Garden')
    await page.fill('input[type="email"]', 'chef@spicegarden.com')
    await page.fill('input[type="password"]', 'securepass')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL(`${BASE}/dashboard`, { timeout: 5000 })
  })

  test('4 - Dashboard page renders KPI cards and charts', async ({ page }) => {
    await page.goto(`${BASE}/dashboard`)
    await expect(page.getByText('Total Orders Today')).toBeVisible()
    await expect(page.getByText('Total Revenue')).toBeVisible()
    await expect(page.getByText('Avg Order Value')).toBeVisible()
    await expect(page.getByText('Top Selling Item')).toBeVisible()
    await expect(page.getByText('Orders Over Time')).toBeVisible()
    await expect(page.getByText('Top Selling Items')).toBeVisible()
  })

  test('5 - Orders page renders table', async ({ page }) => {
    await page.goto(`${BASE}/dashboard/orders`)
    await expect(page.getByText('Orders', { exact: true }).first()).toBeVisible()
    await expect(page.getByText('Order ID')).toBeVisible()
    await expect(page.getByText('#101')).toBeVisible()
    await expect(page.getByText('#104')).toBeVisible()
  })

  test('6 - Orders page: clicking order opens kitchen ticket', async ({ page }) => {
    await page.goto(`${BASE}/dashboard/orders`)
    await page.locator('tr').filter({ hasText: '#101' }).click()
    await expect(page.getByText('Kitchen Order Ticket')).toBeVisible()
    await expect(page.getByText('AI Upsell Recommendation')).toBeVisible()
  })

  test('7 - Voice ordering UI renders', async ({ page }) => {
    await page.goto(`${BASE}/dashboard/voice`)
    await expect(page.getByText('Voice Ordering')).toBeVisible()
    await expect(page.getByText('Press to start voice ordering')).toBeVisible()
    await expect(page.getByText('Order Summary')).toBeVisible()
  })

  test('8 - Analytics charts render', async ({ page }) => {
    await page.goto(`${BASE}/dashboard/analytics`)
    await expect(page.getByText('Analytics')).toBeVisible()
    await expect(page.getByText('Menu Profitability Matrix')).toBeVisible()
    await expect(page.getByText('Combo Recommendations')).toBeVisible()
    await expect(page.getByText('Underperforming Items')).toBeVisible()
    // Check combo data
    await expect(page.getByText('Paneer Pizza')).toBeVisible()
    await expect(page.getByText('Garlic Bread')).toBeVisible()
  })

  test('9 - Navbar navigates between pages', async ({ page }) => {
    await page.goto(`${BASE}/dashboard`)
    await page.getByRole('link', { name: /Orders/i }).first().click()
    await expect(page).toHaveURL(`${BASE}/dashboard/orders`)
    await page.getByRole('link', { name: /Voice/i }).first().click()
    await expect(page).toHaveURL(`${BASE}/dashboard/voice`)
    await page.getByRole('link', { name: /Analytics/i }).first().click()
    await expect(page).toHaveURL(`${BASE}/dashboard/analytics`)
  })
})

/**
 * Smoke-тесты FireWatch — проверяют что страницы рендерятся без ошибок.
 *
 * Требования перед запуском:
 *   1. cd backend && source .venv/bin/activate && uvicorn main:app --reload
 *   2. npm test  (фронтенд поднимается автоматически через webServer)
 */
import { test, expect } from '@playwright/test'
import { login, waitForLoad } from './helpers'

// ─── Авторизация ──────────────────────────────────────────────────────────────

test('страница логина отображается', async ({ page }) => {
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: /firewatch/i })).toBeVisible()
  await expect(page.getByPlaceholder(/email/i)).toBeVisible()
  await expect(page.getByPlaceholder(/пароль/i)).toBeVisible()
})

test('неверный пароль — показывает ошибку', async ({ page }) => {
  await page.goto('/login')
  await page.getByPlaceholder(/email/i).fill('admin@firewatch.kz')
  await page.getByPlaceholder(/пароль/i).fill('wrongpassword')
  await page.getByRole('button', { name: /войти/i }).click()
  await expect(page.getByText(/неверный|ошибка|invalid/i)).toBeVisible({ timeout: 5_000 })
})

test('успешный логин → редирект на дашборд', async ({ page }) => {
  await login(page)
  await expect(page).toHaveURL(/dashboard/)
})

// ─── Основной дашборд ─────────────────────────────────────────────────────────

test('дашборд — KPI карточки загружаются', async ({ page }) => {
  await login(page)
  await waitForLoad(page)
  // Ожидаем хотя бы один статистический блок (тенге или число инцидентов)
  await expect(page.getByText(/пожар|инцидент|YTD|ущерб/i).first()).toBeVisible({ timeout: 10_000 })
})

test('дашборд — сайдбар содержит новые пункты', async ({ page }) => {
  await login(page)
  await expect(page.getByRole('link', { name: /здания/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /гидранты/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /маршрутизация/i })).toBeVisible()
})

// ─── Здания и оперативные планы ───────────────────────────────────────────────

test('страница зданий — заголовок и список', async ({ page }) => {
  await login(page)
  await page.goto('/dashboard/buildings')
  await expect(page.getByRole('heading', { name: /оперативные планы/i })).toBeVisible()
  await waitForLoad(page)
  // Ждём либо карточку здания, либо сообщение «не найдены»
  const card = page.locator('[class*="rounded-xl"]').first()
  await expect(card).toBeVisible({ timeout: 10_000 })
})

test('здания — карточка раскрывается', async ({ page }) => {
  await login(page)
  await page.goto('/dashboard/buildings')
  await waitForLoad(page)
  // Кликаем на первую карточку
  await page.locator('button').filter({ hasText: /хайвилл|аланда|евразия/i }).first().click()
  // Должна появиться кнопка QR
  await expect(page.getByRole('button', { name: /qr/i })).toBeVisible({ timeout: 3_000 })
})

test('здания — QR-модалка открывается', async ({ page }) => {
  await login(page)
  await page.goto('/dashboard/buildings')
  await waitForLoad(page)
  await page.locator('button').filter({ hasText: /хайвилл|аланда|евразия/i }).first().click()
  await page.getByRole('button', { name: /qr/i }).click()
  await expect(page.locator('canvas')).toBeVisible({ timeout: 3_000 })
})

// ─── Публичный просмотрщик плана (без авторизации) ───────────────────────────

test('план здания по ID — доступен без логина', async ({ page }) => {
  // Публичная страница должна открываться без редиректа на /login
  await page.goto('/plan/building-highvill')
  await expect(page).not.toHaveURL(/login/)
  await expect(page.getByText(/firewatch/i)).toBeVisible()
})

test('план здания — показывает название и данные', async ({ page }) => {
  await page.goto('/plan/building-highvill')
  await waitForLoad(page)
  await expect(page.getByText(/хайвилл/i)).toBeVisible({ timeout: 8_000 })
})

test('план здания — несуществующий ID показывает ошибку', async ({ page }) => {
  await page.goto('/plan/non-existent-id')
  await waitForLoad(page)
  await expect(page.getByText(/не найден|обратитесь/i)).toBeVisible({ timeout: 8_000 })
})

// ─── Мобильный вид плана ──────────────────────────────────────────────────────
// Запускается в проекте "mobile" (iPhone 13) из playwright.config.ts

test('план здания — мобильный вид, хедер sticky', async ({ page }) => {
  await page.goto('/plan/building-highvill')
  await waitForLoad(page)
  const header = page.locator('div').filter({ hasText: /firewatch/ }).first()
  await expect(header).toBeVisible()
})

// ─── Гидранты ─────────────────────────────────────────────────────────────────

test('страница гидрантов — заголовок и сводка', async ({ page }) => {
  await login(page)
  await page.goto('/dashboard/hydrants')
  await expect(page.getByRole('heading', { name: /гидранты/i })).toBeVisible()
  await waitForLoad(page)
  // Ожидаем цифры сводки
  await expect(page.getByText(/рабочих/i)).toBeVisible({ timeout: 8_000 })
})

test('гидранты — фильтр по статусу работает', async ({ page }) => {
  await login(page)
  await page.goto('/dashboard/hydrants')
  await waitForLoad(page)
  // Кликаем на «Не работают»
  await page.getByRole('button', { name: /не работают/i }).click()
  // Должны остаться только карточки с красным статусом
  await expect(page.getByText(/не работает/i).first()).toBeVisible({ timeout: 3_000 })
})

test('гидранты — форма редактирования открывается', async ({ page }) => {
  await login(page)
  await page.goto('/dashboard/hydrants')
  await waitForLoad(page)
  // Кнопка карандаша (Edit2)
  await page.locator('button').filter({ has: page.locator('svg') }).first().click()
  // Должен появиться select статуса
  await expect(page.getByText(/рабочий/i).first()).toBeVisible({ timeout: 3_000 })
})

// ─── Экстренная маршрутизация ─────────────────────────────────────────────────

test('страница маршрутизации — заголовок', async ({ page }) => {
  await login(page)
  await page.goto('/dashboard/routing')
  await expect(page.getByRole('heading', { name: /маршрутизация/i })).toBeVisible()
  await expect(page.getByRole('button', { name: /рассчитать/i })).toBeVisible()
})

test('маршрутизация — расчёт маршрута показывает результат', async ({ page }) => {
  await login(page)
  await page.goto('/dashboard/routing')
  await waitForLoad(page)
  await page.getByRole('button', { name: /рассчитать/i }).click()
  // Ждём результат — обычное и экстренное время
  await expect(page.getByText(/экстренный режим/i)).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText(/экономия/i)).toBeVisible({ timeout: 15_000 })
})

test('маршрутизация — карта появляется после расчёта', async ({ page }) => {
  await login(page)
  await page.goto('/dashboard/routing')
  await waitForLoad(page)
  await page.getByRole('button', { name: /рассчитать/i }).click()
  // Leaflet создаёт div.leaflet-container
  await expect(page.locator('.leaflet-container')).toBeVisible({ timeout: 15_000 })
})

// ─── Инспектор (регрессия) ────────────────────────────────────────────────────

test('инспектор — загружается и показывает районы', async ({ page }) => {
  await login(page)
  await page.goto('/dashboard/inspector')
  await waitForLoad(page)
  await expect(page.getByText(/байқоңыр|есіл|алматы|сарыарқа|нұра/i).first()).toBeVisible({ timeout: 10_000 })
})

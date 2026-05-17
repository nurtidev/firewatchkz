import type { Page } from '@playwright/test'

export const TEST_USER = { email: 'admin@firewatch.kz', password: 'admin123' }

export async function login(page: Page) {
  await page.goto('/login')
  // Поля логина не имеют label/placeholder со словами "email"/"пароль" —
  // плейсхолдер email = "admin@firewatch.kz", у пароля — "••••••••".
  // Ищем по типу input.
  await page.locator('input[type="email"]').fill(TEST_USER.email)
  await page.locator('input[type="password"]').fill(TEST_USER.password)
  await page.getByRole('button', { name: /^войти/i }).click()
  await page.waitForURL('**/dashboard**', { timeout: 10_000 })
}

/** Ждёт пока спиннер/скелетон исчезнет */
export async function waitForLoad(page: Page) {
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
}

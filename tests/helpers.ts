import type { Page } from '@playwright/test'

export const TEST_USER = { email: 'admin@firewatch.kz', password: 'admin123' }

export async function login(page: Page) {
  await page.goto('/login')
  await page.getByPlaceholder(/email/i).fill(TEST_USER.email)
  await page.getByPlaceholder(/пароль/i).fill(TEST_USER.password)
  await page.getByRole('button', { name: /войти/i }).click()
  await page.waitForURL('**/dashboard**', { timeout: 10_000 })
}

/** Ждёт пока спиннер/скелетон исчезнет */
export async function waitForLoad(page: Page) {
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {})
}

import { test, expect } from '@playwright/test';

const apiBase = process.env.PLAYWRIGHT_API_BASE_URL || 'http://127.0.0.1:8000';
const studyGuideId = process.env.PLAYWRIGHT_STUDY_GUIDE_ID || '3';

async function apiHealthy() {
  try {
    const res = await fetch(`${apiBase}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

test('login and dashboard', async ({ page }) => {
  if (!await apiHealthy()) {
    test.skip(true, 'API not reachable on http://127.0.0.1:8000');
  }

  await page.goto('/login');
  await page.fill('input[type="email"]', 'parent@classbridge.local');
  await page.fill('input[type="password"]', 'password123!');
  await page.getByRole('button', { name: /sign in|login/i }).click();

  await expect(page).toHaveURL(/dashboard/);
  await expect(page.getByText(/welcome back/i)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Messages', exact: true })).toBeVisible();
});

test('messages and notifications smoke', async ({ page }) => {
  if (!await apiHealthy()) {
    test.skip(true, 'API not reachable on http://127.0.0.1:8000');
  }

  await page.goto('/login');
  await page.fill('input[type="email"]', 'parent@classbridge.local');
  await page.fill('input[type="password"]', 'password123!');
  await page.getByRole('button', { name: /sign in|login/i }).click();

  await page.getByRole('button', { name: 'Messages', exact: true }).click();
  await expect(page).toHaveURL(/messages/);
  await expect(page.getByText(/conversations/i)).toBeVisible();

  await page.getByRole('button', { name: /notifications/i }).click();
  await expect(page.getByText(/notifications/i)).toBeVisible();
});

test('study guide markdown renders without raw syntax artifacts', async ({ page }) => {
  if (!await apiHealthy()) {
    test.skip(true, 'API not reachable on http://127.0.0.1:8000');
  }

  await page.goto('/login');
  await page.fill('input[type="email"]', 'parent@classbridge.local');
  await page.fill('input[type="password"]', 'password123!');
  await page.getByRole('button', { name: /sign in|login/i }).click();
  await expect(page).toHaveURL(/dashboard/);

  await page.goto(`/study/guide/${studyGuideId}`);
  await expect(page.locator('.guide-body')).toBeVisible();

  const structuredContent = page.locator('.guide-body h1, .guide-body h2, .guide-body h3, .guide-body ul, .guide-body ol, .guide-body table');
  await expect(structuredContent.first()).toBeVisible();

  const guideText = await page.locator('.guide-body').innerText();
  expect(guideText).not.toContain('| ---');
  expect(guideText).not.toContain('**');
  expect(guideText).not.toMatch(/(^|\n)\s{0,3}#{1,6}\s+/);
});

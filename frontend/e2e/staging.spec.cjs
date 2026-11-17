const { test, expect } = require('@playwright/test');
const password = 'Kanasu-CI-Only-Synthetic-2026';
const api = 'http://127.0.0.1:8000/api';
const ui = 'http://127.0.0.1:4173';

async function login(page) {
  await page.goto(ui);
  await expect(page.getByRole('heading', { name: 'Kanasu staging login' })).toBeVisible();
  await page.getByLabel('Staging password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByText('Quant Research & Trading Workspace')).toBeVisible();
}

test('protects API, CORS, and login', async ({ page, request }) => {
  expect((await request.get(`${api}/backtest/config`)).status()).toBe(401);
  const preflight = await request.fetch(`${api}/backtest/config`, { method: 'OPTIONS', headers: { Origin: 'http://127.0.0.1:4173', 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'authorization' } });
  expect(preflight.headers()['access-control-allow-origin']).toBe('http://127.0.0.1:4173');
  const denied = await request.fetch(`${api}/backtest/config`, { method: 'OPTIONS', headers: { Origin: 'https://untrusted.example', 'Access-Control-Request-Method': 'GET' } });
  expect(denied.headers()['access-control-allow-origin']).toBeUndefined();
  await page.goto(ui);
  await page.getByLabel('Staging password').fill('incorrect-synthetic-password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('alert')).toContainText('Incorrect password');
});

test('runs protected synthetic Backtest', async ({ page }) => {
  await login(page);
  await page.getByText('Run and analyze strategy backtests').click();
  await page.getByLabel('Backtest start').fill('2026-11-10T09:15');
  await page.getByLabel('Backtest end').fill('2026-11-10T10:15');
  await page.getByRole('button', { name: 'Run Backtest' }).click();
  await expect(page.getByText('e2e-backtest-run')).toBeVisible();
});

test('runs Paper lifecycle and reports backend replacement', async ({ page, request }) => {
  await login(page);
  await page.getByText('Monitor paper trading runtime').click();
  await page.getByRole('button', { name: 'Start Paper Trading' }).click();
  await expect(page.getByText('RUNNING', { exact: true })).toBeVisible();
  expect((await request.post('http://127.0.0.1:8000/__test__/simulate-restart')).status()).toBe(200);
  await page.reload();
  await page.getByLabel('Staging password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByText('Paper Trading Runtime')).toBeVisible();
  await expect(page.getByRole('status')).toContainText('restarted or was replaced');
  await expect(page.getByText('NO SESSION', { exact: true })).toBeVisible();
});

test('server and UI logout revoke the session', async ({ page, request }) => {
  const signed = await request.post(`${api}/auth/login`, { data: { password } });
  const { access_token } = await signed.json();
  const headers = { Authorization: `Bearer ${access_token}` };
  expect((await request.get(`${api}/backtest/config`, { headers })).status()).toBe(200);
  expect((await request.post(`${api}/auth/logout`, { headers })).status()).toBe(200);
  expect((await request.get(`${api}/backtest/config`, { headers })).status()).toBe(401);
  await login(page);
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page.getByRole('heading', { name: 'Kanasu staging login' })).toBeVisible();
});

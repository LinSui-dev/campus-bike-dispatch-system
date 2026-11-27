/**
 * E real-browser evidence for C01 reset branches, C02 refresh/recovery and C03 station drag.
 * Runs against the real campus backend (8010) with Mock disabled (Vite 15175).
 *
 *   node scripts/e2e_campus_acceptance.mjs
 */
import { createRequire } from 'node:module'
import { mkdirSync, writeFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
import { join } from 'node:path'

const require = createRequire(pathToFileURL(join(process.cwd(), 'frontend', 'package.json')))
const { chromium } = require('playwright-core')

const BASE = process.env.UI_BASE || 'http://127.0.0.1:15175'
const API = process.env.API_BASE || 'http://127.0.0.1:8010'
const OUT = join(process.cwd(), 'docs', 'integration', 'results', 'evidence', 'ui')
mkdirSync(OUT, { recursive: true })

const record = { base: BASE, api: API, started_at: new Date().toISOString(), steps: [], requests: [], errors: [], warnings: [] }

async function api(path, options = {}) {
  const response = await fetch(API + path, { headers: { 'Content-Type': 'application/json' }, ...options })
  return { status: response.status, body: await response.json().catch(() => null) }
}

async function ensureIdle() {
  const runtime = (await api('/api/v1/runtime')).body
  if (runtime?.mode === 'interactive' && runtime.run_id) {
    await api(`/api/v1/runs/${runtime.run_id}/control`, { method: 'POST', body: JSON.stringify({ action: 'reset', save: false }) })
  }
}

async function shot(page, name) {
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }))
  await page.screenshot({ path: join(OUT, name + '.png'), fullPage: true, animations: 'disabled' })
  record.steps.push({ step: name, file: `docs/integration/results/evidence/ui/${name}.png` })
  console.log('screenshot', name)
}

async function go(page, label) {
  await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: label, exact: true }).click()
  await page.getByRole('heading', { level: 1, name: label, exact: true }).waitFor({ state: 'visible' })
  await page.waitForTimeout(700)
}

const status = page => page.getByTestId('runtime-status')
const actions = page => page.locator('.run-actions')

async function startPaused(page) {
  await actions(page).getByRole('button', { name: '开始仿真', exact: true }).click()
  await status(page).filter({ hasText: '运行中' }).waitFor({ timeout: 15000 })
  await actions(page).getByRole('button', { name: '暂停', exact: true }).click()
  await status(page).filter({ hasText: '已暂停' }).waitFor({ timeout: 15000 })
}

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1040 } })
const page = await context.newPage()
page.on('pageerror', err => record.errors.push('pageerror: ' + err.message))
page.on('response', res => {
  if (res.url().endsWith('/favicon.ico')) return
  if (res.status() >= 400 && !res.url().includes('/runs/')) record.errors.push(`http ${res.status()}: ${res.url()}`)
})
page.on('request', req => {
  if (!['POST', 'PATCH'].includes(req.method()) || !req.url().includes('/api/v1/')) return
  let body = null
  try { body = req.postDataJSON() } catch { /* ignore */ }
  record.requests.push({ method: req.method(), path: new URL(req.url()).pathname, body })
})

try {
  await ensureIdle()
  await page.goto(BASE + '/#/overview')
  await page.getByRole('heading', { level: 1, name: '运营总览', exact: true }).waitFor()
  await page.waitForTimeout(1200)

  // ---------- C01: reset three options ----------
  await go(page, '仿真控制')
  await startPaused(page)
  const controlCount = () => record.requests.filter(r => r.path.endsWith('/control')).length
  const before = controlCount()
  await actions(page).getByRole('button', { name: '重置', exact: true }).click()
  await shot(page, 'c01-reset-modal')
  await page.getByRole('dialog').getByRole('button', { name: '取消' }).click()
  if (controlCount() !== before) throw new Error('取消重置不应发送 control 请求')
  await actions(page).getByRole('button', { name: '重置', exact: true }).click()
  await page.getByRole('button', { name: '保存并重置' }).click()
  await status(page).filter({ hasText: '空闲' }).waitFor({ timeout: 15000 })
  await shot(page, 'c01-reset-saved')

  await startPaused(page)
  await actions(page).getByRole('button', { name: '重置', exact: true }).click()
  await page.getByRole('button', { name: '舍弃并重置' }).click()
  await status(page).filter({ hasText: '空闲' }).waitFor({ timeout: 15000 })
  await shot(page, 'c01-reset-discarded')
  const resets = record.requests.filter(r => r.path.endsWith('/control') && r.body?.action === 'reset')
  record.steps.push({ step: 'c01-reset-bodies', bodies: resets.map(r => r.body) })

  // ---------- C02: refresh recovery + external reset 404 ----------
  await page.getByLabel('随机种子').fill('47')
  await page.getByRole('combobox', { name: '运行场景', exact: true }).selectOption('lunch')
  await startPaused(page)
  await actions(page).getByLabel('运行倍速').fill('27.5')
  await actions(page).getByRole('button', { name: '设倍速' }).click()
  await page.getByTestId('current-speed').filter({ hasText: '27.5×' }).waitFor({ timeout: 15000 })
  await shot(page, 'c02-recovery-before-refresh')

  await page.reload()
  await status(page).filter({ hasText: '已暂停' }).waitFor({ timeout: 20000 })
  await page.getByTestId('current-speed').filter({ hasText: '27.5×' }).waitFor({ timeout: 15000 })
  if (await page.getByLabel('随机种子').inputValue() !== '47') throw new Error('刷新后种子未恢复')
  if (await page.getByRole('combobox', { name: '运行场景', exact: true }).inputValue() !== 'lunch') throw new Error('刷新后场景未恢复')
  await shot(page, 'c02-recovery-after-refresh')

  for (const label of ['运营总览', '停车点管理', '智能调度', '实验分析', '仿真控制']) {
    await go(page, label)
    await status(page).filter({ hasText: '已暂停' }).waitFor({ timeout: 10000 })
  }
  const runtime = (await api('/api/v1/runtime')).body
  await api(`/api/v1/runs/${runtime.run_id}/control`, { method: 'POST', body: JSON.stringify({ action: 'reset', save: false }) })
  await status(page).filter({ hasText: '空闲' }).waitFor({ timeout: 20000 })
  await shot(page, 'c02-recovery-reset-404')

  // ---------- C03: real map and station drag ----------
  await go(page, '停车点管理')
  await page.getByLabel('显示道路').check()
  await page.waitForTimeout(800)
  await shot(page, 'c03-campus-roads')

  const marker = page.locator('[data-station="M10"]').first()
  await marker.waitFor({ state: 'visible', timeout: 15000 })
  const bounds = await marker.boundingBox()
  if (!bounds) throw new Error('找不到 M10 站点标记')
  const patchBefore = record.requests.length
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2)
  await page.mouse.down()
  // 校园底图 4500px 缩放到约 680px，4 显示像素约 26 图像像素，落在 40px 吸附容差内。
  await page.mouse.move(bounds.x + bounds.width / 2 + 4, bounds.y + bounds.height / 2 + 2, { steps: 6 })
  await page.mouse.up()
  await page.waitForTimeout(1500)
  const patches = record.requests.slice(patchBefore).filter(r => r.method === 'PATCH' && r.path.includes('/stations/'))
  if (!patches.length) throw new Error('拖动后没有发送站点 PATCH')
  const keys = Object.keys(patches[0].body || {}).sort()
  if (JSON.stringify(keys) !== JSON.stringify(['x', 'y'])) throw new Error('PATCH 应只含 x/y，实际 ' + keys.join(','))
  record.steps.push({ step: 'c03-station-patch', body: patches[0].body, path: patches[0].path })
  await shot(page, 'c03-station-drag')
} catch (error) {
  record.errors.push('fatal: ' + (error?.stack || String(error)))
  try { await shot(page, 'c99-failure') } catch { /* ignore */ }
  process.exitCode = 1
} finally {
  try { await ensureIdle() } catch { /* ignore */ }
  record.finished_at = new Date().toISOString()
  writeFileSync(join(OUT, 'c-real-acceptance.json'), JSON.stringify(record, null, 2), 'utf8')
  await context.close()
  await browser.close()
}

console.log(JSON.stringify({ steps: record.steps.length, requests: record.requests.length, errors: record.errors }, null, 2))
if (record.errors.length) process.exitCode = 1

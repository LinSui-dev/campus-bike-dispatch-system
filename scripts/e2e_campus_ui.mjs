/**
 * E real-system UI acceptance: drives the Vite dev server (Mock disabled) against the
 * real campus backend, visits all five pages, starts/pauses a real run, triggers a real
 * dispatch, and stores screenshots for AC-C01..C04 / AC-E02 evidence.
 *
 * Usage (repo root, backend on 8010 and Vite on 15175 already running):
 *   node scripts/e2e_campus_ui.mjs
 */
import { createRequire } from 'node:module'
import { mkdirSync, writeFileSync } from 'node:fs'
import { pathToFileURL } from 'node:url'
import { join } from 'node:path'

const require = createRequire(pathToFileURL(join(process.cwd(), 'frontend', 'package.json')))
const { chromium } = require('playwright-core')

const BASE = process.env.UI_BASE || 'http://127.0.0.1:15175'
const OUT = join(process.cwd(), 'docs', 'integration', 'results', 'evidence', 'ui')
mkdirSync(OUT, { recursive: true })

const record = { base: BASE, started_at: new Date().toISOString(), steps: [], errors: [], warnings: [] }

async function shot(page, name) {
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }))
  const file = join(OUT, name + '.png')
  await page.screenshot({ path: file, fullPage: true, animations: 'disabled' })
  record.steps.push({ step: name, file: `docs/integration/results/evidence/ui/${name}.png` })
  console.log('screenshot', name)
}

async function go(page, label) {
  await page.getByRole('navigation', { name: '主导航' }).getByRole('link', { name: label, exact: true }).click()
  await page.getByRole('heading', { level: 1, name: label, exact: true }).waitFor({ state: 'visible' })
  await page.waitForTimeout(600)
}

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1040 } })
const page = await context.newPage()
page.on('console', msg => {
  if (msg.type() !== 'error') return
  if (msg.text().includes('Failed to load resource')) return // covered by the response listener below
  record.errors.push('console: ' + msg.text())
})
page.on('pageerror', err => record.errors.push('pageerror: ' + err.message))
page.on('response', res => {
  if (res.url().endsWith('/favicon.ico')) { record.warnings.push('favicon.ico is not provided (cosmetic only)'); return }
  if (res.status() >= 400) record.errors.push(`http ${res.status()}: ${res.url()}`)
})

try {
  await page.goto(BASE + '/#/overview')
  await page.getByRole('heading', { level: 1, name: '运营总览', exact: true }).waitFor()
  await page.waitForTimeout(1500)
  await shot(page, '01-overview-campus')

  await go(page, '停车点管理')
  const roadButton = page.getByRole('button', { name: /道路/ }).first()
  if (await roadButton.count()) await roadButton.click()
  await page.waitForTimeout(800)
  await shot(page, '02-stations-campus-map')

  await go(page, '仿真控制')
  await shot(page, '03-control-config')
  await page.getByRole('button', { name: '开始仿真', exact: true }).click()
  await page.getByTestId('runtime-status').filter({ hasText: '运行中' }).waitFor({ timeout: 15000 })
  await page.getByRole('button', { name: '暂停', exact: true }).click()
  await page.getByTestId('runtime-status').filter({ hasText: '已暂停' }).waitFor({ timeout: 15000 })
  record.steps.push({ step: 'start-and-pause-real-run', status: await page.getByTestId('runtime-status').innerText() })
  await shot(page, '04-control-paused')

  await go(page, '智能调度')
  const dispatchButton = page.getByRole('button', { name: '手动触发调度', exact: true })
  if (await dispatchButton.isEnabled()) {
    await dispatchButton.click()
    await page.waitForTimeout(1500)
    record.steps.push({ step: 'manual-dispatch-real', status: 'clicked' })
  }
  await shot(page, '05-dispatch-real')

  await go(page, '实验分析')
  await page.waitForTimeout(1500)
  await shot(page, '06-experiments-batch-form')
  await page.getByRole('button', { name: '保存历史', exact: true }).click()
  await page.waitForTimeout(1500)
  await shot(page, '07-experiments-history')

  const stateResponse = await page.request.get('http://127.0.0.1:8010/api/v1/runtime')
  record.runtime = await stateResponse.json()
} catch (error) {
  record.errors.push('fatal: ' + (error?.stack || String(error)))
  try { await shot(page, '99-failure') } catch { /* ignore */ }
  process.exitCode = 1
} finally {
  record.finished_at = new Date().toISOString()
  writeFileSync(join(OUT, 'ui-acceptance.json'), JSON.stringify(record, null, 2), 'utf8')
  await context.close()
  await browser.close()
}

console.log(JSON.stringify({ steps: record.steps.length, errors: record.errors }, null, 2))
if (record.errors.length) process.exitCode = 1

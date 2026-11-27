import { defineConfig } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const artifacts = new URL('../artifacts/', import.meta.url)
mkdirSync(artifacts, { recursive: true })
const testDatabase = fileURLToPath(new URL('c-browser-' + process.pid + '.db', artifacts)).replaceAll('\\', '/')

export default defineConfig({
  testDir: './tests',
  outputDir: '../artifacts/c-browser',
  workers: 1,
  timeout: 35_000,
  use: {
    viewport: { width: 1440, height: 1040 },
    channel: process.env.C_TEST_CHROME_CHANNEL,
    baseURL: 'http://127.0.0.1:15173',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'npm run dev -- --port 15173',
      url: 'http://127.0.0.1:15173',
      env: { VITE_USE_MOCK: 'true' },
    },
    {
      command: 'npm run dev -- --port 15174',
      url: 'http://127.0.0.1:15174',
      env: { VITE_USE_MOCK: 'false', BACKEND_URL: 'http://127.0.0.1:18015' },
    },
    {
      command: 'python -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 18015',
      url: 'http://127.0.0.1:18015/api/v1/health',
      env: { DATA_PROFILE: 'fixture', DATABASE_URL: 'sqlite:///' + testDatabase },
    },
  ],
})

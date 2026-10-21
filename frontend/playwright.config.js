import { defineConfig, devices } from '@playwright/test'
const existingUrl = process.env.BRAINFUSION_WEB_URL
const browserChannel = process.env.BRAINFUSION_BROWSER_CHANNEL
export default defineConfig({
  testDir: './e2e', timeout: 30000, workers: 1, reporter: 'list',
  use: { baseURL: existingUrl || 'http://127.0.0.1:5185', headless: true, trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], ...(browserChannel ? { channel: browserChannel } : {}) } }],
  webServer: existingUrl ? undefined : { command: 'npm run dev -- --host 127.0.0.1 --port 5185 --strictPort', url: 'http://127.0.0.1:5185', reuseExistingServer: false },
})

import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const cwd = process.cwd()
const frontendRoot = existsSync(path.join(cwd, 'package.json')) && existsSync(path.join(cwd, 'src'))
  ? cwd
  : path.join(cwd, 'frontend')
const projectRoot = path.resolve(frontendRoot, '..')
const outputRoot = path.resolve(projectRoot, 'outputs', 'vella-system-smoke-2026-05-09')
const baseUrl = process.env.VELLA_BASE_URL || 'http://127.0.0.1:4176'
const shouldStartPreview = !process.env.VELLA_BASE_URL

async function waitForServer(url, timeoutMs = 30_000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {
      // retry
    }
    await new Promise((resolve) => setTimeout(resolve, 300))
  }
  throw new Error(`Timed out waiting for ${url}`)
}

async function main() {
  let server
  if (shouldStartPreview) {
    if (!existsSync(path.join(frontendRoot, 'dist'))) {
      throw new Error('frontend/dist is missing. Run npm --prefix frontend run build first.')
    }
    server = spawn('npx', ['vite', 'preview', '--host', '127.0.0.1', '--port', '4176', '--strictPort'], {
      cwd: frontendRoot,
      stdio: 'pipe',
    })
    await waitForServer(baseUrl)
  }

  await mkdir(outputRoot, { recursive: true })
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })
  const results = []

  async function step(name, fn) {
    try {
      await fn()
      results.push({ name, ok: true })
    } catch (error) {
      results.push({ name, ok: false, error: error instanceof Error ? error.message : String(error) })
    }
  }

  await page.goto(`${baseUrl}/internal/vella-system`, { waitUntil: 'networkidle' })
  await page.screenshot({ path: path.join(outputRoot, '01-default.png'), fullPage: true })

  await step('no iframe', async () => {
    const iframeCount = await page.locator('iframe').count()
    if (iframeCount !== 0) throw new Error(`Expected 0 iframes, got ${iframeCount}`)
  })

  await step('computed contract', async () => {
    const contract = await page.locator('.vella-system').evaluate((element) => {
      const style = window.getComputedStyle(element)
      const shell = document.querySelector('.vs-shell')
      const topbar = document.querySelector('.vs-topbar')
      const row = document.querySelector('.vs-table tbody tr')
      return {
        fontFamily: style.fontFamily,
        sidebarWidth: shell ? window.getComputedStyle(shell).gridTemplateColumns.split(' ')[0] : null,
        topbarHeight: topbar ? window.getComputedStyle(topbar).height : null,
        rowHeight: row ? window.getComputedStyle(row).height : null,
      }
    })
    if (!contract.fontFamily.includes('Inter')) throw new Error(`Expected Inter font, got ${contract.fontFamily}`)
    if (contract.sidebarWidth !== '232px') throw new Error(`Expected sidebar 232px, got ${contract.sidebarWidth}`)
    if (contract.topbarHeight !== '50px') throw new Error(`Expected topbar 50px, got ${contract.topbarHeight}`)
  })

  await step('filter table', async () => {
    await page.getByPlaceholder('SKU или рекламная кампания').fill('HCBT')
    await page.waitForTimeout(100)
    const rows = await page.locator('.vs-table tbody tr').count()
    if (rows !== 1) throw new Error(`Expected 1 filtered row, got ${rows}`)
    await page.getByPlaceholder('SKU или рекламная кампания').fill('')
  })

  await step('columns dropdown toggles column', async () => {
    await page.getByRole('button', { name: /Колонки/ }).last().click()
    await page.getByText('margin').click()
    await page.keyboard.press('Escape')
    const hasMargin = await page.locator('.vs-table th').filter({ hasText: 'Маржа' }).count()
    if (hasMargin !== 0) throw new Error('Expected Маржа column to be hidden')
  })

  await step('custom select uses Vella dropdown', async () => {
    await page.getByRole('button', { name: 'Все менеджеры' }).click()
    await page.locator('.vs-select-option').filter({ hasText: 'Мария Д.' }).click()
    const rows = await page.locator('.vs-table tbody tr').count()
    if (rows !== 1) throw new Error(`Expected manager filter to leave 1 row, got ${rows}`)
  })

  await step('modal opens and closes by outside click', async () => {
    await page.getByRole('button', { name: /Применить цены/ }).click()
    await page.locator('.vs-modal-content').waitFor()
    await page.mouse.click(20, 20)
    await page.locator('.vs-modal-content').waitFor({ state: 'hidden' })
  })

  await step('drawer tabs and escape close', async () => {
    await page.locator('.vs-sku').first().click()
    await page.locator('.vs-drawer-content').waitFor()
    await page.getByRole('button', { name: 'Правила' }).click()
    await page.getByText('Автоматика, P_min').waitFor()
    await page.keyboard.press('Escape')
    await page.locator('.vs-drawer-content').waitFor({ state: 'hidden' })
  })

  await step('calendar popover closes by escape', async () => {
    await page.getByRole('button', { name: /25.04/ }).click()
    await page.locator('.vs-calendar').waitFor()
    await page.keyboard.press('Escape')
    await page.locator('.vs-calendar').waitFor({ state: 'hidden' })
  })

  await page.screenshot({ path: path.join(outputRoot, '02-after-interactions.png'), fullPage: true })
  await browser.close()
  server?.kill('SIGTERM')

  const failed = results.filter((result) => !result.ok)
  await writeFile(path.join(outputRoot, 'smoke.json'), JSON.stringify({ baseUrl, results }, null, 2))
  if (failed.length) {
    console.error(JSON.stringify(failed, null, 2))
    process.exit(1)
  }
  console.log(`Vella system smoke passed: ${outputRoot}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})

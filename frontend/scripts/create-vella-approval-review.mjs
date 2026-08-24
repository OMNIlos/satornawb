import { copyFile, cp, mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'

const cwd = process.cwd()
const frontendRoot = existsSync(path.join(cwd, 'package.json')) && existsSync(path.join(cwd, 'src'))
  ? cwd
  : path.join(cwd, 'frontend')
const projectRoot = path.resolve(frontendRoot, '..')
const outputsRoot = path.join(projectRoot, 'outputs')
const stamp = new Date().toISOString().replace(/[:.]/g, '-')
const reviewRoot = path.join(outputsRoot, `vella-approval-wb-reports-digest-${stamp}`)
const latestReviewRoot = path.join(outputsRoot, 'vella-approval-wb-reports-digest-latest')

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, 'utf8'))
}

async function listOutputDirs(prefix) {
  const entries = await readdir(outputsRoot, { withFileTypes: true })
  return entries
    .filter((entry) => entry.isDirectory() && entry.name.startsWith(prefix))
    .map((entry) => path.join(outputsRoot, entry.name))
    .sort()
    .reverse()
}

async function findLatestParity(screenName, strict) {
  const dirs = await listOutputDirs(`vella-page-parity-${screenName}-`)
  for (const dir of dirs) {
    const reportPath = path.join(dir, 'parity-report.json')
    if (!existsSync(reportPath)) continue
    const report = await readJson(reportPath)
    if (report.screenName === screenName && Boolean(report.strict) === strict) {
      return { dir, report, reportPath }
    }
  }
  throw new Error(`No parity report found for ${screenName}, strict=${strict}`)
}

async function findLatestInteraction() {
  const dirs = await listOutputDirs('vella-interaction-parity-')
  for (const dir of dirs) {
    const reportPath = path.join(dir, 'interaction-report.json')
    if (!existsSync(reportPath)) continue
    const report = await readJson(reportPath)
    return { dir, report, reportPath }
  }
  throw new Error('No interaction parity report found')
}

async function findLatestContract() {
  const dirs = await listOutputDirs('vella-page-contract-wb-reports-digest-')
  for (const dir of dirs) {
    const reportPath = path.join(dir, 'page-contract.json')
    if (!existsSync(reportPath)) continue
    const report = await readJson(reportPath)
    if (report.screen === 'wb-reports-digest' && report.gate) {
      return { dir, report, reportPath }
    }
  }
  throw new Error('No machine page contract report found')
}

function relativeFromProject(filePath) {
  return path.relative(projectRoot, filePath)
}

async function copyStateAssets(stateName, sourceDir) {
  const assetDir = path.join(reviewRoot, 'assets', stateName)
  await mkdir(assetDir, { recursive: true })
  const assets = {}
  for (const name of ['reference.png', 'candidate.png', 'diff.png']) {
    const source = path.join(sourceDir, name)
    const target = path.join(assetDir, name)
    await copyFile(source, target)
    assets[name] = path.relative(reviewRoot, target)
  }
  return assets
}

function statusClass(status) {
  return status === 'pass' ? 'pass' : 'fail'
}

function gateRow(label, status, detail, pathValue) {
  return `
    <tr>
      <td>${escapeHtml(label)}</td>
      <td><span class="pill ${statusClass(status)}">${escapeHtml(status)}</span></td>
      <td>${escapeHtml(detail)}</td>
      <td><code>${escapeHtml(pathValue)}</code></td>
    </tr>`
}

function stateSection(title, report, assets) {
  const mismatch = `${(report.image.mismatchRatio * 100).toFixed(2)}%`
  const selectorFailures = report.selectorChecks.filter((check) => !check.pass).length
  const styleFailures = report.styleChecks.filter((check) => !check.pass).length
  return `
    <section>
      <div class="section-head">
        <div>
          <h2>${escapeHtml(title)}</h2>
          <p>Mismatch ${escapeHtml(mismatch)} · selectors failed ${selectorFailures} · styles failed ${styleFailures}</p>
        </div>
        <span class="pill ${statusClass(report.status)}">${escapeHtml(report.status)}</span>
      </div>
      <div class="shots">
        <figure>
          <figcaption>HTML baseline</figcaption>
          <img src="${escapeHtml(assets['reference.png'])}" alt="${escapeHtml(title)} HTML baseline">
        </figure>
        <figure>
          <figcaption>React candidate</figcaption>
          <img src="${escapeHtml(assets['candidate.png'])}" alt="${escapeHtml(title)} React candidate">
        </figure>
        <figure>
          <figcaption>Diff</figcaption>
          <img src="${escapeHtml(assets['diff.png'])}" alt="${escapeHtml(title)} visual diff">
        </figure>
      </div>
    </section>`
}

function interactionList(report) {
  return report.results.map((result) => `
    <div class="interaction-group">
      <h3>${escapeHtml(result.target)}</h3>
      <ul>
        ${result.steps.map((step) => `<li><span class="pill ${statusClass(step.pass ? 'pass' : 'fail')}">${step.pass ? 'pass' : 'fail'}</span>${escapeHtml(step.description)}</li>`).join('')}
      </ul>
    </div>
  `).join('')
}

function machineContractSection(contract) {
  const rows = contract.report.gate.states.map((state) => `
    <tr>
      <td>${escapeHtml(state.name)}</td>
      <td>${state.commonSelectorFailures.reference} / ${state.commonSelectorFailures.candidate}</td>
      <td>${state.candidateOnlySelectorFailures}</td>
      <td>${state.digestHandlerReferenceCount} / ${state.digestHandlerCandidateCount}</td>
      <td>${state.digestReactConvertedHandlerCount}</td>
      <td>${state.runtimeFunctionFailures.reference} / ${state.runtimeFunctionFailures.candidate}</td>
    </tr>
  `).join('')
  return `
    <section>
      <div class="section-head">
        <div>
          <h2>Machine Contract</h2>
          <p>DOM/state/dependency extraction for baseline and React candidate.</p>
        </div>
        <span class="pill ${statusClass(contract.report.gate.status)}">${escapeHtml(contract.report.gate.status)}</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>State</th>
            <th>Common selector failures ref/cand</th>
            <th>Candidate island failures</th>
            <th>Digest handlers ref/cand</th>
            <th>React-converted handlers</th>
            <th>Runtime failures ref/cand</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
      <p>Report: <code>${escapeHtml(relativeFromProject(contract.reportPath))}</code></p>
    </section>`
}

function renderHtml({ now, period, strictNow, interaction, contract, nowAssets, periodAssets }) {
  const nowMismatch = `${(now.report.image.mismatchRatio * 100).toFixed(2)}%`
  const periodMismatch = `${(period.report.image.mismatchRatio * 100).toFixed(2)}%`
  const strictMismatch = `${(strictNow.report.image.mismatchRatio * 100).toFixed(2)}%`
  return `<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>WB Reports Digest Approval Review</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f8fb;
      --panel: #ffffff;
      --border: #dfe4ec;
      --text: #111827;
      --muted: #667085;
      --pass: #057a55;
      --pass-bg: #dcfce7;
      --fail: #b42318;
      --fail-bg: #fee4e2;
      --brand: #2563eb;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main { max-width: 1480px; margin: 0 auto; padding: 24px; }
    header, section {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 16px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, .04);
    }
    h1, h2, h3, p { margin-top: 0; }
    h1 { font-size: 24px; margin-bottom: 8px; }
    h2 { font-size: 18px; margin-bottom: 4px; }
    h3 { font-size: 15px; margin-bottom: 10px; }
    p, li { color: var(--muted); }
    code {
      display: inline-block;
      max-width: 560px;
      overflow-wrap: anywhere;
      border: 1px solid var(--border);
      background: #f8fafc;
      border-radius: 6px;
      padding: 2px 6px;
      color: #344054;
    }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-top: 1px solid var(--border); padding: 10px 8px; text-align: left; vertical-align: top; }
    th { color: #344054; font-size: 12px; text-transform: uppercase; letter-spacing: .02em; }
    .summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
    .metric { border: 1px solid var(--border); border-radius: 8px; padding: 12px; background: #fbfdff; }
    .metric strong { display: block; font-size: 20px; margin-top: 4px; }
    .pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 54px;
      height: 24px;
      border-radius: 999px;
      padding: 0 8px;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }
    .pill.pass { color: var(--pass); background: var(--pass-bg); }
    .pill.fail { color: var(--fail); background: var(--fail-bg); }
    .section-head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
    .shots { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
    figure { margin: 0; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: #fff; }
    figcaption { padding: 8px 10px; color: #344054; border-bottom: 1px solid var(--border); font-weight: 700; }
    img { display: block; width: 100%; height: auto; }
    ul { padding-left: 0; list-style: none; margin-bottom: 0; }
    li { display: flex; align-items: center; gap: 8px; padding: 5px 0; }
    .interaction-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
    .decision { border-left: 4px solid var(--brand); }
    @media (max-width: 1100px) {
      .summary, .shots, .interaction-grid { grid-template-columns: 1fr; }
      main { padding: 14px; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>WB Reports Digest Approval Review</h1>
      <p>React candidate must inherit the HTML baseline. Production <code>/wb/reports</code> remains on <code>VellaStaticPage</code> until manual approval.</p>
      <div class="summary">
        <div class="metric">Visual now<strong>${escapeHtml(nowMismatch)}</strong></div>
        <div class="metric">Visual period<strong>${escapeHtml(periodMismatch)}</strong></div>
        <div class="metric">Contract<strong>${escapeHtml(contract.report.gate.status)}</strong></div>
        <div class="metric">Interaction<strong>${escapeHtml(interaction.report.status)}</strong></div>
        <div class="metric">Strict target<strong>${escapeHtml(strictMismatch)} / 1%</strong></div>
      </div>
    </header>

    <section>
      <h2>Gate Evidence</h2>
      <table>
        <thead><tr><th>Gate</th><th>Status</th><th>Detail</th><th>Report</th></tr></thead>
        <tbody>
          ${gateRow('Visual parity now', now.report.status, `mismatch ${nowMismatch}`, relativeFromProject(now.reportPath))}
          ${gateRow('Visual parity period', period.report.status, `mismatch ${periodMismatch}`, relativeFromProject(period.reportPath))}
          ${gateRow('Machine contract', contract.report.gate.status, `${contract.report.gate.failures.length} failures`, relativeFromProject(contract.reportPath))}
          ${gateRow('Interaction parity', interaction.report.status, `${interaction.report.failedSteps.length} failed steps`, relativeFromProject(interaction.reportPath))}
          ${gateRow('Strict 1% target', strictNow.report.status, `mismatch ${strictMismatch}`, relativeFromProject(strictNow.reportPath))}
        </tbody>
      </table>
    </section>

    ${stateSection('Digest now', now.report, nowAssets)}
    ${stateSection('Digest period', period.report, periodAssets)}
    ${machineContractSection(contract)}

    <section>
      <div class="section-head">
        <div>
          <h2>Interaction Smoke</h2>
          <p>The same actions are executed against HTML baseline and React candidate.</p>
        </div>
        <span class="pill ${statusClass(interaction.report.status)}">${escapeHtml(interaction.report.status)}</span>
      </div>
      <div class="interaction-grid">
        ${interactionList(interaction.report)}
      </div>
    </section>

    <section class="decision">
      <h2>Manual Decision</h2>
      <p>Status: pending manual approval.</p>
      <p>Approve this page only if the visible forms, colors, states, dependencies and interactions match the HTML baseline closely enough to start JSX island replacement under the strict gate.</p>
    </section>
  </main>
</body>
</html>`
}

async function main() {
  const now = await findLatestParity('wb-reports-digest', false)
  const period = await findLatestParity('wb-reports-digest-period', false)
  const strictNow = await findLatestParity('wb-reports-digest', true)
  const contract = await findLatestContract()
  const interaction = await findLatestInteraction()

  await mkdir(reviewRoot, { recursive: true })
  const nowAssets = await copyStateAssets('now', now.dir)
  const periodAssets = await copyStateAssets('period', period.dir)
  const html = renderHtml({ now, period, strictNow, interaction, contract, nowAssets, periodAssets })
  const indexPath = path.join(reviewRoot, 'index.html')
  await writeFile(indexPath, html)

  const summary = {
    generatedAt: new Date().toISOString(),
    reviewPath: indexPath,
    nowReport: relativeFromProject(now.reportPath),
    periodReport: relativeFromProject(period.reportPath),
    strictNowReport: relativeFromProject(strictNow.reportPath),
    contractReport: relativeFromProject(contract.reportPath),
    interactionReport: relativeFromProject(interaction.reportPath),
    status: now.report.status === 'pass' && period.report.status === 'pass' && contract.report.gate.status === 'pass' && interaction.report.status === 'pass'
      ? 'pending_manual_approval'
      : 'needs_fix',
  }
  await writeFile(path.join(reviewRoot, 'review-summary.json'), `${JSON.stringify(summary, null, 2)}\n`)
  await rm(latestReviewRoot, { recursive: true, force: true })
  await cp(reviewRoot, latestReviewRoot, { recursive: true })
  console.log(`Vella approval review: ${summary.status}`)
  console.log(`Review: ${indexPath}`)
  console.log(`Latest: ${path.join(latestReviewRoot, 'index.html')}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})

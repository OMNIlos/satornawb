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
const screenName = 'wb-reports-abc'
const reviewRoot = path.join(outputsRoot, `vella-approval-${screenName}-${stamp}`)
const latestReviewRoot = path.join(outputsRoot, `vella-approval-${screenName}-latest`)
const promotionReadinessLatestPath = path.join(latestReviewRoot, 'promotion-readiness-report.json')
const manifestPath = process.env.VELLA_ABC_APPROVAL_MANIFEST_PATH
  ? path.resolve(projectRoot, process.env.VELLA_ABC_APPROVAL_MANIFEST_PATH)
  : path.join(projectRoot, 'docs', 'react-migration', 'wb-reports-abc-approval.manifest.json')
const approvalPackPath = process.env.VELLA_ABC_APPROVAL_PACK_PATH
  ? path.resolve(projectRoot, process.env.VELLA_ABC_APPROVAL_PACK_PATH)
  : path.join(projectRoot, 'docs', 'react-migration', 'reviews', 'wb-reports-abc-2026-05-31-approval.md')

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

async function readJsonIfExists(filePath) {
  if (!existsSync(filePath)) return null
  return readJson(filePath)
}

async function listOutputDirs(prefix) {
  const entries = await readdir(outputsRoot, { withFileTypes: true })
  return entries
    .filter((entry) => entry.isDirectory() && entry.name.startsWith(prefix))
    .map((entry) => path.join(outputsRoot, entry.name))
    .sort()
    .reverse()
}

async function findLatestParity() {
  const dirs = await listOutputDirs(`vella-page-parity-${screenName}-`)
  for (const dir of dirs) {
    const reportPath = path.join(dir, 'parity-report.json')
    if (!existsSync(reportPath)) continue
    const report = await readJson(reportPath)
    if (report.screenName === screenName && !report.strict) {
      return { dir, report, reportPath }
    }
  }
  throw new Error(`No parity report found for ${screenName}`)
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
  const dirs = await listOutputDirs(`vella-page-contract-${screenName}-`)
  for (const dir of dirs) {
    const reportPath = path.join(dir, 'page-contract.json')
    if (!existsSync(reportPath)) continue
    const report = await readJson(reportPath)
    if (report.screen === screenName && report.gate) {
      return { dir, report, reportPath }
    }
  }
  throw new Error(`No machine page contract report found for ${screenName}`)
}

function relativeFromProject(filePath) {
  return path.relative(projectRoot, filePath)
}

async function copyShotAssets(sourceDir) {
  const assetDir = path.join(reviewRoot, 'assets', 'abc')
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
  const state = contract.report.gate.states.find((item) => item.name === 'default') || contract.report.gate.states[0]
  const rows = [
    ['Common selectors ref/candidate', `${state.commonSelectorFailures.reference} / ${state.commonSelectorFailures.candidate}`],
    ['Candidate island selector failures', state.candidateOnlySelectorFailures],
    ['Runtime function failures ref/candidate', `${state.runtimeFunctionFailures.reference} / ${state.runtimeFunctionFailures.candidate}`],
    ['Screen handlers ref/candidate', `${state.screenHandlerReferenceCount} / ${state.screenHandlerCandidateCount}`],
    ['React-converted screen handlers', state.screenReactConvertedHandlerCount],
    ['Screen controls ref/candidate', `${state.screenControlCount.reference} / ${state.screenControlCount.candidate}`],
  ]
  return `
    <section>
      <div class="section-head">
        <div>
          <h2>Machine Contract Details</h2>
          <p>DOM/state/dependency extraction for ABC baseline and React candidate.</p>
        </div>
        <span class="pill ${statusClass(contract.report.gate.status)}">${escapeHtml(contract.report.gate.status)}</span>
      </div>
      <table>
        <thead><tr><th>Check</th><th>Value</th></tr></thead>
        <tbody>
          ${rows.map(([label, value]) => `
            <tr>
              <td>${escapeHtml(label)}</td>
              <td>${escapeHtml(value)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      <p>Report: <code>${escapeHtml(relativeFromProject(contract.reportPath))}</code></p>
    </section>`
}

function manualChecklistSection() {
  const approveItems = [
    'Sidebar, topbar and report subtabs look like the HTML baseline.',
    'ABC KPI cards, source cards, toolbar, search, chips and filtered summary preserve forms, colors, spacing and text hierarchy.',
    'Table columns, row density, row colors, badges, tooltips and row actions match baseline.',
    'Search, chips and `Заказы` sorting behave correctly.',
    '`Колонки`, `Экспорт XLSX` and `Как читать?` behave like baseline.',
    'SKU drawer opens from a visible row and preserves header, tabs, overview, algo, comments and misc states.',
    'Drawer calculator, margin analysis, promo boost, comments and misc `Заказы/Логи` controls behave like baseline.',
    'Row comment drawer opens and closes like baseline.',
    'The current visual diff is acceptable and does not show a real layout/content reinterpretation.',
  ]
  const rejectItems = [
    'New visual pattern appears that is not in HTML.',
    'Form, color, spacing, state, text, or dependency was simplified or reinterpreted.',
    'Any control behaves differently from the HTML baseline.',
    'Diff highlights a real layout/content shift rather than rendering noise.',
  ]
  const listItems = (items) => items.map((item) => `<li><span class="box"></span><span>${escapeHtml(item)}</span></li>`).join('')
  return `
    <section>
      <div class="section-head">
        <div>
          <h2>Manual Review Checklist</h2>
          <p>Use this checklist while comparing the live candidate and screenshots before giving approval.</p>
        </div>
        <span class="pill fail">pending</span>
      </div>
      <div class="checklist-grid">
        <div>
          <h3>Approve only if</h3>
          <ul class="checklist">${listItems(approveItems)}</ul>
        </div>
        <div>
          <h3>Send back if</h3>
          <ul class="checklist">${listItems(rejectItems)}</ul>
        </div>
      </div>
    </section>`
}

function promotionReadinessSection(report) {
  if (!report) {
    return `
    <section>
      <div class="section-head">
        <div>
          <h2>Promotion Readiness</h2>
          <p>Run the promotion readiness command after manual approval and the final refresh.</p>
        </div>
        <span class="pill fail">not run</span>
      </div>
      <p>Command: <code>npm --prefix frontend run review:vella-abc-promotion:check</code></p>
    </section>`
  }

  return `
    <section>
      <div class="section-head">
        <div>
          <h2>Promotion Readiness</h2>
          <p>Final guard before a separate production route patch.</p>
        </div>
        <span class="pill ${statusClass(report.promotionAllowed ? 'pass' : 'fail')}">${escapeHtml(report.status)}</span>
      </div>
      <p>${escapeHtml(report.requiredNextAction)}</p>
      <p>Report: <code>outputs/vella-approval-wb-reports-abc-latest/promotion-readiness-report.json</code></p>
      <table>
        <thead><tr><th>Precondition</th><th>Status</th><th>Detail</th></tr></thead>
        <tbody>
          ${(report.preconditions || []).map((item) => `
            <tr>
              <td>${escapeHtml(item.name)}</td>
              <td><span class="pill ${statusClass(item.pass ? 'pass' : 'fail')}">${item.pass ? 'pass' : 'fail'}</span></td>
              <td>${escapeHtml(item.detail)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </section>`
}

function renderHtml({ parity, contract, interaction, assets, promotionReadiness }) {
  const mismatch = `${(parity.report.image.mismatchRatio * 100).toFixed(2)}%`
  const selectorFailures = parity.report.selectorChecks.filter((check) => !check.pass).length
  const styleFailures = parity.report.styleChecks.filter((check) => !check.pass).length
  const baselineHash = contract.report.source.staticRuntimeHints.htmlHash
  return `<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>WB Reports ABC Approval Review</title>
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
    .checklist-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
    .checklist li { align-items: flex-start; }
    .box {
      flex: 0 0 auto;
      width: 14px;
      height: 14px;
      border: 1px solid #98a2b3;
      border-radius: 3px;
      margin-top: 3px;
      background: #fff;
    }
    .decision { border-left: 4px solid var(--brand); }
    @media (max-width: 1100px) {
      .summary, .shots, .interaction-grid, .checklist-grid { grid-template-columns: 1fr; }
      main { padding: 14px; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>WB Reports ABC Approval Review</h1>
      <p>React candidate must inherit the HTML baseline. Production <code>/wb/reports/abc</code> remains on <code>VellaStaticPage</code> until manual approval.</p>
      <div class="summary">
        <div class="metric">Visual parity<strong>${escapeHtml(mismatch)}</strong></div>
        <div class="metric">Selectors failed<strong>${selectorFailures}</strong></div>
        <div class="metric">Styles failed<strong>${styleFailures}</strong></div>
        <div class="metric">Contract<strong>${escapeHtml(contract.report.gate.status)}</strong></div>
        <div class="metric">Interaction<strong>${escapeHtml(interaction.report.status)}</strong></div>
        <div class="metric">Baseline hash<strong>${escapeHtml(baselineHash.slice(0, 12))}</strong></div>
      </div>
      <p>Baseline file: <code>frontend/public/vella-production.html</code> · SHA-256: <code>${escapeHtml(baselineHash)}</code></p>
    </header>

    <section>
      <h2>Gate Evidence</h2>
      <table>
        <thead><tr><th>Gate</th><th>Status</th><th>Detail</th><th>Report</th></tr></thead>
        <tbody>
          ${gateRow('Visual parity ABC', parity.report.status, `mismatch ${mismatch}`, relativeFromProject(parity.reportPath))}
          ${gateRow('Required selectors', selectorFailures === 0 ? 'pass' : 'fail', `${selectorFailures} failed`, relativeFromProject(parity.reportPath))}
          ${gateRow('Style probes', styleFailures === 0 ? 'pass' : 'fail', `${styleFailures} failed`, relativeFromProject(parity.reportPath))}
          ${gateRow('Machine contract', contract.report.gate.status, `${contract.report.gate.failures.length} failures`, relativeFromProject(contract.reportPath))}
          ${gateRow('Interaction parity', interaction.report.status, `${interaction.report.failedSteps.length} failed steps`, relativeFromProject(interaction.reportPath))}
        </tbody>
      </table>
    </section>

    ${machineContractSection(contract)}

    <section>
      <div class="section-head">
        <div>
          <h2>ABC Visual Diff</h2>
          <p>HTML baseline, React candidate, and pixel diff from the latest passing ABC gate.</p>
        </div>
        <span class="pill ${statusClass(parity.report.status)}">${escapeHtml(parity.report.status)}</span>
      </div>
      <div class="shots">
        <figure>
          <figcaption>HTML baseline</figcaption>
          <img src="${escapeHtml(assets['reference.png'])}" alt="ABC HTML baseline">
        </figure>
        <figure>
          <figcaption>React candidate</figcaption>
          <img src="${escapeHtml(assets['candidate.png'])}" alt="ABC React candidate">
        </figure>
        <figure>
          <figcaption>Diff</figcaption>
          <img src="${escapeHtml(assets['diff.png'])}" alt="ABC visual diff">
        </figure>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>Interaction Smoke</h2>
          <p>The same ABC actions are executed against HTML baseline and React candidate.</p>
        </div>
        <span class="pill ${statusClass(interaction.report.status)}">${escapeHtml(interaction.report.status)}</span>
      </div>
      <div class="interaction-grid">
        ${interactionList(interaction.report)}
      </div>
    </section>

    ${manualChecklistSection()}

    ${promotionReadinessSection(promotionReadiness)}

    <section class="decision">
      <h2>Manual Decision</h2>
      <p>Status: pending manual approval.</p>
      <p>Approve only if the visible table, filters, forms, drawer tabs, colors, states, and dependencies match the HTML baseline closely enough to promote this screen later.</p>
      <p>Dry run: <code>VELLA_APPROVAL_SIGNAL="&lt;test approval text&gt;" VELLA_APPROVAL_DRY_RUN=1 npm --prefix frontend run review:vella-abc-approval:record</code></p>
      <p>Record approval: <code>VELLA_APPROVAL_SIGNAL="&lt;exact user approval text&gt;" npm --prefix frontend run review:vella-abc-approval:record</code></p>
    </section>
  </main>
</body>
</html>`
}

async function writeApprovalManifest({ parity, contract, interaction, summary }) {
  const existing = await readJsonIfExists(manifestPath)
  const visualFailures = {
    selectors: parity.report.selectorChecks.filter((check) => !check.pass).length,
    styles: parity.report.styleChecks.filter((check) => !check.pass).length,
  }
  const existingApproved =
    existing?.status === 'approved_for_promotion_review' &&
    Boolean(existing?.manualReview?.approvalSignal) &&
    Boolean(existing?.manualReview?.approvedAt)
  const manifestStatus = summary.status === 'pending_manual_approval' && existingApproved
    ? 'approved_for_promotion_review'
    : summary.status
  const approvedManualReviewFields = existingApproved
    ? {
        approvalSignal: existing.manualReview.approvalSignal,
        approvedAt: existing.manualReview.approvedAt,
        approvedBy: existing.manualReview.approvedBy || 'user',
      }
    : {
        approvalSignal: null,
      }
  const manifest = {
    screen: 'WB Reports ABC',
    status: manifestStatus,
    productionSwitchAllowed: false,
    productionRoute: '/wb/reports/abc',
    productionOwner: 'VellaStaticPage',
    htmlBaseline: {
      default: '/vella-production.html?tab=abc',
      file: 'frontend/public/vella-production.html',
      htmlHash: contract.report.source.staticRuntimeHints.htmlHash,
    },
    reactCandidate: {
      default: '/internal/vella-parity/reports?tab=abc',
    },
    manualReview: {
      stableLatest: 'outputs/vella-approval-wb-reports-abc-latest/index.html',
      localhostUrl: 'http://127.0.0.1:4193/',
      approvalPack: 'docs/react-migration/reviews/wb-reports-abc-2026-05-31-approval.md',
      refreshCommand: 'npm --prefix frontend run review:vella-abc-approval:refresh',
      verificationCommand: 'npm --prefix frontend run review:vella-abc-approval:verify',
      recordCommand: 'VELLA_APPROVAL_SIGNAL="<exact user approval text>" npm --prefix frontend run review:vella-abc-approval:record',
      dryRunCommand: 'VELLA_APPROVAL_SIGNAL="<test approval text>" VELLA_APPROVAL_DRY_RUN=1 npm --prefix frontend run review:vella-abc-approval:record',
      ...approvedManualReviewFields,
    },
    gates: {
      defaultVisual: {
        status: parity.report.status,
        states: {
          default: {
            mismatchRatio: parity.report.image.mismatchRatio,
            requiredSelectorFailures: visualFailures.selectors,
            styleProbeFailures: visualFailures.styles,
            report: relativeFromProject(parity.reportPath),
          },
        },
      },
      machineContract: {
        status: contract.report.gate.status,
        report: relativeFromProject(contract.reportPath),
      },
      allVisual: existing?.gates?.allVisual || {
        status: 'not_refreshed_by_abc_workflow',
        abcReport: relativeFromProject(parity.reportPath),
      },
      interaction: {
        status: interaction.report.status,
        failedSteps: interaction.report.failedSteps.length,
        report: relativeFromProject(interaction.reportPath),
      },
      approvalReview: {
        status: summary.status,
        report: 'outputs/vella-approval-wb-reports-abc-latest/review-summary.json',
      },
      approvalVerification: {
        status: 'pending_refresh_verification',
        report: 'outputs/vella-approval-wb-reports-abc-latest/verification-report.json',
      },
    },
    activeIslandBoundary: {
      name: 'wb-reports-abc',
      status: 'react_element_tree_plus_explicit_jsx_islands',
      explicitJsxIslands: existing?.activeIslandBoundary?.explicitJsxIslands || [],
      verifiedBy: relativeFromProject(contract.reportPath),
    },
    blockedActionsUntilManualApproval: existingApproved ? [] : existing?.blockedActionsUntilManualApproval || [
      'Switch /wb/reports/abc from VellaStaticPage to React candidate',
      'Treat the page as approved without manual review',
      'Use ABC approval as approval for other report screens',
    ],
    ...(existingApproved
      ? {
          blockedActionsUntilExplicitPromotionPatch: existing?.blockedActionsUntilExplicitPromotionPatch || [
            'Switch /wb/reports/abc from VellaStaticPage to React candidate without a separate promotion patch',
            'Use ABC approval as approval for other report screens',
            'Promote if review:vella-abc-approval:refresh no longer passes',
          ],
        }
      : {}),
  }
  await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`)
}

async function writeApprovalPackEvidence({ parity, contract, interaction, summary }) {
  if (!existsSync(approvalPackPath)) return
  const visualReport = relativeFromProject(parity.reportPath)
  const contractReport = relativeFromProject(contract.reportPath)
  const interactionReport = relativeFromProject(interaction.reportPath)
  const visualDir = path.dirname(visualReport)
  let markdown = await readFile(approvalPackPath, 'utf8')

  markdown = markdown
    .replace(
      /- timestamped copy: `outputs\/vella-approval-wb-reports-abc-[^`]+\/index\.html`/,
      `- timestamped copy: \`${relativeFromProject(summary.reviewPath)}\``,
    )
    .replace(
      /\| Visual parity `abc` \| pass \| `outputs\/vella-page-parity-wb-reports-abc-[^`]+\/parity-report\.json` \|/,
      `| Visual parity \`abc\` | pass | \`${visualReport}\` |`,
    )
    .replace(
      /\| Machine contract `abc` \| pass \| `outputs\/vella-page-contract-wb-reports-abc-[^`]+\/page-contract\.json` \|/,
      `| Machine contract \`abc\` | pass | \`${contractReport}\` |`,
    )
    .replace(
      /\| Interaction parity \| pass \| `outputs\/vella-interaction-parity-[^`]+\/interaction-report\.json` \|/,
      `| Interaction parity | pass | \`${interactionReport}\` |`,
    )
    .replace(
      /- Reference: `outputs\/vella-page-parity-wb-reports-abc-[^`]+\/reference\.png`/,
      `- Reference: \`${visualDir}/reference.png\``,
    )
    .replace(
      /- Candidate: `outputs\/vella-page-parity-wb-reports-abc-[^`]+\/candidate\.png`/,
      `- Candidate: \`${visualDir}/candidate.png\``,
    )
    .replace(
      /- Diff: `outputs\/vella-page-parity-wb-reports-abc-[^`]+\/diff\.png`/,
      `- Diff: \`${visualDir}/diff.png\``,
    )

  await writeFile(approvalPackPath, markdown)
}

async function main() {
  const parity = await findLatestParity()
  const contract = await findLatestContract()
  const interaction = await findLatestInteraction()
  const promotionReadiness = await readJsonIfExists(promotionReadinessLatestPath)

  await mkdir(reviewRoot, { recursive: true })
  const assets = await copyShotAssets(parity.dir)
  if (promotionReadiness) {
    await writeFile(
      path.join(reviewRoot, 'promotion-readiness-report.json'),
      `${JSON.stringify(promotionReadiness, null, 2)}\n`,
    )
  }
  const html = renderHtml({ parity, contract, interaction, assets, promotionReadiness })
  const indexPath = path.join(reviewRoot, 'index.html')
  await writeFile(indexPath, html)

  const summary = {
    generatedAt: new Date().toISOString(),
    screenName,
    reviewPath: indexPath,
    parityReport: relativeFromProject(parity.reportPath),
    contractReport: relativeFromProject(contract.reportPath),
    interactionReport: relativeFromProject(interaction.reportPath),
    status: parity.report.status === 'pass' && contract.report.gate.status === 'pass' && interaction.report.status === 'pass'
      ? 'pending_manual_approval'
      : 'needs_fix',
  }
  await writeFile(path.join(reviewRoot, 'review-summary.json'), `${JSON.stringify(summary, null, 2)}\n`)
  await rm(latestReviewRoot, { recursive: true, force: true })
  await cp(reviewRoot, latestReviewRoot, { recursive: true })
  await writeApprovalManifest({ parity, contract, interaction, summary })
  await writeApprovalPackEvidence({ parity, contract, interaction, summary })
  console.log(`Vella ABC approval review: ${summary.status}`)
  console.log(`Review: ${indexPath}`)
  console.log(`Latest: ${path.join(latestReviewRoot, 'index.html')}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})

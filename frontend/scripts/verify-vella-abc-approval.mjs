import { existsSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'

const cwd = process.cwd()
const frontendRoot = existsSync(path.join(cwd, 'package.json')) && existsSync(path.join(cwd, 'src'))
  ? cwd
  : path.join(cwd, 'frontend')
const projectRoot = path.resolve(frontendRoot, '..')
const latestReviewRoot = path.join(projectRoot, 'outputs', 'vella-approval-wb-reports-abc-latest')
const verificationReportPath = path.join(latestReviewRoot, 'verification-report.json')

function projectPath(relativePath) {
  return path.join(projectRoot, relativePath)
}

function relativeFromProject(filePath) {
  return path.relative(projectRoot, filePath)
}

async function readJson(relativePath) {
  return JSON.parse(await readFile(projectPath(relativePath), 'utf8'))
}

async function readText(relativePath) {
  return readFile(projectPath(relativePath), 'utf8')
}

async function sha256File(relativePath) {
  const contents = await readFile(projectPath(relativePath))
  return createHash('sha256').update(contents).digest('hex')
}

function assert(condition, message, details = {}) {
  if (!condition) {
    const error = new Error(message)
    error.details = details
    throw error
  }
}

function assertExists(relativePath) {
  assert(existsSync(projectPath(relativePath)), `Missing file: ${relativePath}`)
}

function isApprovedForPromotionReview(manifest) {
  return manifest.status === 'approved_for_promotion_review'
}

async function main() {
  const checks = []
  const check = async (name, fn) => {
    try {
      const details = await fn()
      checks.push({ name, status: 'pass', ...(details ? { details } : {}) })
    } catch (error) {
      checks.push({
        name,
        status: 'fail',
        error: error instanceof Error ? error.message : String(error),
        ...(error?.details ? { details: error.details } : {}),
      })
    }
  }

  const manifestPath = 'docs/react-migration/wb-reports-abc-approval.manifest.json'
  const appPath = 'frontend/src/App.tsx'
  const approvalPackPath = 'docs/react-migration/reviews/wb-reports-abc-2026-05-31-approval.md'

  let manifest
  let reviewSummary
  let parityReport
  let contractReport
  let interactionReport

  await check('manifest loads and blocks production promotion', async () => {
    manifest = await readJson(manifestPath)
    const allowedStatuses = ['pending_manual_approval', 'approved_for_promotion_review']
    assert(manifest.screen === 'WB Reports ABC', 'Unexpected screen in manifest', { screen: manifest.screen })
    assert(allowedStatuses.includes(manifest.status), 'Unexpected manifest approval status', { status: manifest.status })
    assert(manifest.productionSwitchAllowed === false, 'Production switch must be blocked')
    assert(manifest.productionRoute === '/wb/reports/abc', 'Unexpected production route', { route: manifest.productionRoute })
    assert(manifest.productionOwner === 'VellaStaticPage', 'Production owner must remain VellaStaticPage', {
      owner: manifest.productionOwner,
    })
    if (isApprovedForPromotionReview(manifest)) {
      assert(Boolean(manifest.manualReview?.approvalSignal), 'Approved manifest must include approval signal')
      assert(Boolean(manifest.manualReview?.approvedAt), 'Approved manifest must include approvedAt')
    } else {
      assert(manifest.manualReview?.approvalSignal === null, 'Approval signal must stay null until user approval')
    }
    assert(
      manifest.manualReview?.recordCommand?.includes('VELLA_APPROVAL_SIGNAL='),
      'Manifest must document the manual approval record command',
    )
    assert(
      manifest.manualReview?.dryRunCommand?.includes('VELLA_APPROVAL_DRY_RUN=1'),
      'Manifest must document the manual approval dry-run command',
    )
    return { manifestPath, status: manifest.status }
  })

  await check('production route is still static in App.tsx', async () => {
    const app = await readText(appPath)
    assert(
      app.includes('<Route path="/wb/reports/abc" element={<VellaStaticPage />} />'),
      '/wb/reports/abc is not mapped to VellaStaticPage',
    )
    assert(
      app.includes('<Route path="/internal/vella-parity/reports" element={<VellaHtmlParityPage />} />'),
      'Internal parity route is missing',
    )
    return { appPath }
  })

  await check('latest approval review summary matches manifest reports', async () => {
    const reviewSummaryPath = manifest.gates.approvalReview.report
    assertExists(reviewSummaryPath)
    reviewSummary = await readJson(reviewSummaryPath)
    const visualReportPath = manifest.gates.defaultVisual.states.default.report
    const contractReportPath = manifest.gates.machineContract.report
    const interactionReportPath = manifest.gates.interaction.report
    assert(reviewSummary.screenName === 'wb-reports-abc', 'Unexpected review screen', {
      screenName: reviewSummary.screenName,
    })
    assert(reviewSummary.status === 'pending_manual_approval', 'Review summary must remain the pre-approval review artifact', {
      status: reviewSummary.status,
    })
    assert(reviewSummary.parityReport === visualReportPath, 'Review parity report is stale or mismatched', {
      expected: visualReportPath,
      actual: reviewSummary.parityReport,
    })
    assert(reviewSummary.contractReport === contractReportPath, 'Review contract report is stale or mismatched', {
      expected: contractReportPath,
      actual: reviewSummary.contractReport,
    })
    assert(reviewSummary.interactionReport === interactionReportPath, 'Review interaction report is stale or mismatched', {
      expected: interactionReportPath,
      actual: reviewSummary.interactionReport,
    })
    assertExists(manifest.manualReview.stableLatest)
    assertExists(relativeFromProject(reviewSummary.reviewPath))
    const latestReviewHtml = await readText(manifest.manualReview.stableLatest)
    assert(latestReviewHtml.includes('Promotion Readiness'), 'Latest approval HTML must show promotion readiness')
    assert(
      latestReviewHtml.includes('review:vella-abc-promotion:check') ||
        latestReviewHtml.includes('promotion-readiness-report.json'),
      'Latest approval HTML must document the promotion readiness gate',
    )
    return { reviewSummaryPath, visualReportPath, contractReportPath, interactionReportPath }
  })

  await check('visual parity report is passing and complete', async () => {
    const visualReportPath = manifest.gates.defaultVisual.states.default.report
    assertExists(visualReportPath)
    parityReport = await readJson(visualReportPath)
    const selectorFailures = parityReport.selectorChecks.filter((item) => !item.pass).length
    const styleFailures = parityReport.styleChecks.filter((item) => !item.pass).length
    assert(parityReport.screenName === 'wb-reports-abc', 'Unexpected visual report screen', {
      screenName: parityReport.screenName,
    })
    assert(parityReport.strict === false, 'Approval visual report must be non-strict')
    assert(parityReport.status === 'pass', 'Visual parity is not passing', { status: parityReport.status })
    assert(selectorFailures === 0, 'Visual parity has required selector failures', { selectorFailures })
    assert(styleFailures === 0, 'Visual parity has style probe failures', { styleFailures })
    assert(parityReport.image.mismatchRatio === manifest.gates.defaultVisual.states.default.mismatchRatio, 'Manifest mismatch ratio is stale', {
      manifestMismatch: manifest.gates.defaultVisual.states.default.mismatchRatio,
      reportMismatch: parityReport.image.mismatchRatio,
    })

    const visualDir = path.dirname(visualReportPath)
    for (const name of ['reference.png', 'candidate.png', 'diff.png']) {
      assertExists(path.join(visualDir, name))
    }
    return { visualReportPath, mismatchRatio: parityReport.image.mismatchRatio, selectorFailures, styleFailures }
  })

  await check('interaction smoke report is passing', async () => {
    const interactionReportPath = manifest.gates.interaction.report
    assertExists(interactionReportPath)
    interactionReport = await readJson(interactionReportPath)
    assert(interactionReport.status === 'pass', 'Interaction smoke is not passing', {
      status: interactionReport.status,
    })
    assert(interactionReport.failedSteps.length === 0, 'Interaction smoke has failed steps', {
      failedSteps: interactionReport.failedSteps.length,
    })
    const targets = interactionReport.results.map((result) => result.target).sort()
    assert(JSON.stringify(targets) === JSON.stringify(['candidate', 'reference']), 'Interaction smoke must cover reference and candidate', {
      targets,
    })
    return { interactionReportPath, targets }
  })

  await check('machine contract report is passing', async () => {
    const contractReportPath = manifest.gates.machineContract.report
    assertExists(contractReportPath)
    contractReport = await readJson(contractReportPath)
    assert(contractReport.screen === 'wb-reports-abc', 'Unexpected contract report screen', {
      screen: contractReport.screen,
    })
    assert(contractReport.gate.status === 'pass', 'Machine contract is not passing', {
      status: contractReport.gate.status,
    })
    assert(contractReport.gate.failures.length === 0, 'Machine contract has failures', {
      failures: contractReport.gate.failures.length,
    })
    const state = contractReport.gate.states.find((item) => item.name === 'default')
    assert(Boolean(state), 'Machine contract is missing default state')
    assert(state.commonSelectorFailures.reference === 0, 'Contract has missing reference common selectors', state.commonSelectorFailures)
    assert(state.commonSelectorFailures.candidate === 0, 'Contract has missing candidate common selectors', state.commonSelectorFailures)
    assert(state.candidateOnlySelectorFailures === 0, 'Contract has missing candidate island selectors', {
      candidateOnlySelectorFailures: state.candidateOnlySelectorFailures,
    })
    assert(state.runtimeFunctionFailures.reference === 0, 'Contract has missing reference runtime functions', state.runtimeFunctionFailures)
    assert(state.runtimeFunctionFailures.candidate === 0, 'Contract has missing candidate runtime functions', state.runtimeFunctionFailures)
    assert(state.screenReactConvertedHandlerCount > 0, 'Contract found no React-converted screen handlers', {
      screenReactConvertedHandlerCount: state.screenReactConvertedHandlerCount,
    })
    return { contractReportPath, screenReactConvertedHandlerCount: state.screenReactConvertedHandlerCount }
  })

  await check('HTML baseline hash is frozen and current', async () => {
    const baselineFile = manifest.htmlBaseline.file || 'frontend/public/vella-production.html'
    assertExists(baselineFile)
    const currentHash = await sha256File(baselineFile)
    const contractHash = contractReport.source.staticRuntimeHints.htmlHash
    assert(manifest.htmlBaseline.htmlHash === contractHash, 'Manifest baseline hash does not match contract source hash', {
      manifestHash: manifest.htmlBaseline.htmlHash,
      contractHash,
    })
    assert(currentHash === contractHash, 'Current HTML baseline hash does not match contract source hash', {
      currentHash,
      contractHash,
    })
    return { baselineFile, htmlHash: currentHash }
  })

  await check('approval pack references current evidence and keeps guarded decision', async () => {
    assertExists(approvalPackPath)
    const approvalPack = await readText(approvalPackPath)
    assert(approvalPack.includes(manifest.gates.defaultVisual.states.default.report), 'Approval pack misses current visual report')
    assert(approvalPack.includes(manifest.gates.machineContract.report), 'Approval pack misses current machine contract report')
    assert(approvalPack.includes(manifest.gates.interaction.report), 'Approval pack misses current interaction report')
    if (isApprovedForPromotionReview(manifest)) {
      assert(approvalPack.includes('Status: **approved for promotion review**.'), 'Approval pack decision must show recorded approval')
      assert(approvalPack.includes('Production route still must not be switched automatically.'), 'Approved approval pack must keep automatic production switch blocked')
    } else {
      assert(approvalPack.includes('Status: **pending manual approval**.'), 'Approval pack decision must remain pending')
      assert(approvalPack.includes('Production route still must not be switched.'), 'Approval pack must keep production switch blocked')
    }
    assert(approvalPack.includes('review:vella-abc-approval:record'), 'Approval pack must document approval record command')
    assert(approvalPack.includes('VELLA_APPROVAL_DRY_RUN=1'), 'Approval pack must document approval record dry run')
    return { approvalPackPath }
  })

  const status = checks.every((item) => item.status === 'pass') ? 'pass' : 'fail'
  const report = {
    generatedAt: new Date().toISOString(),
    status,
    checks,
  }

  await mkdir(latestReviewRoot, { recursive: true })
  await writeFile(verificationReportPath, `${JSON.stringify(report, null, 2)}\n`)

  if (status !== 'pass') {
    console.error(`Vella ABC approval verification: fail`)
    console.error(`Report: ${verificationReportPath}`)
    process.exit(1)
  }

  const verifiedManifest = await readJson(manifestPath)
  verifiedManifest.gates.approvalVerification = {
    status: 'pass',
    report: relativeFromProject(verificationReportPath),
  }
  await writeFile(projectPath(manifestPath), `${JSON.stringify(verifiedManifest, null, 2)}\n`)

  console.log('Vella ABC approval verification: pass')
  console.log(`Report: ${verificationReportPath}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})

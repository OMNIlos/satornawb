import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  OpenAPIRegistry,
  OpenApiGeneratorV31,
  extendZodWithOpenApi,
} from '@asteasolutions/zod-to-openapi'
import YAML from 'yaml'
import { z } from 'zod'

extendZodWithOpenApi(z)

const [
  reportSchemas,
  repricerSchemas,
] = await Promise.all([
  import('../src/features/wb-reports/schemas'),
  import('../src/features/wb-repricer/schemas'),
])

const {
  AbcReportResponseSchema,
  AdsPerformanceResponseSchema,
  AiReviewApprovalSchema,
  ExpenseImportCommitResponseSchema,
  ExpenseImportPreviewResponseSchema,
  ExpensesReportResponseSchema,
  PnlReportResponseSchema,
  RnpReportResponseSchema,
  SourceStatusResponseSchema,
} = reportSchemas
const { ErrorResponseSchema, PriceGuardResponseSchema } = repricerSchemas

const registry = new OpenAPIRegistry()

const ErrorResponse = registry.register('ErrorResponse', ErrorResponseSchema)
const PnlReportResponse = registry.register('PnlReportResponse', PnlReportResponseSchema)
const ExpensesReportResponse = registry.register('ExpensesReportResponse', ExpensesReportResponseSchema)
const ExpenseImportPreviewResponse = registry.register('ExpenseImportPreviewResponse', ExpenseImportPreviewResponseSchema)
const ExpenseImportCommitResponse = registry.register('ExpenseImportCommitResponse', ExpenseImportCommitResponseSchema)
const SourceStatusResponse = registry.register('SourceStatusResponse', SourceStatusResponseSchema)
const AdsPerformanceResponse = registry.register('AdsPerformanceResponse', AdsPerformanceResponseSchema)
const RnpReportResponse = registry.register('RnpReportResponse', RnpReportResponseSchema)
const AbcReportResponse = registry.register('AbcReportResponse', AbcReportResponseSchema)
const PriceGuardResponse = registry.register('PriceGuardResponse', PriceGuardResponseSchema)
registry.register('AiReviewApproval', AiReviewApprovalSchema)

const PeriodQuerySchema = z.object({
  dateFrom: z.string().date().optional(),
  dateTo: z.string().date().optional(),
})

const ReportGroupByQuerySchema = PeriodQuerySchema.extend({
  groupBy: z.enum(['sku', 'brand', 'manager', 'category', 'status', 'warehouse', 'campaign']).optional(),
})

const ExpenseImportPreviewRequestSchema = z.object({
  sourceName: z.string().min(1),
  uploadedBy: z.string().min(1),
  rows: z.array(z.record(z.unknown())).default([]),
})

const ExpenseImportCommitRequestSchema = z.object({
  previewId: z.string().min(1),
  approvedBy: z.string().min(1).nullable().optional(),
  approve: z.boolean().optional(),
})

function jsonResponse(schema: z.ZodTypeAny, description = 'OK') {
  return {
    description,
    content: {
      'application/json': { schema },
    },
  }
}

const errorResponses = {
  400: jsonResponse(ErrorResponse, 'Validation error'),
  401: jsonResponse(ErrorResponse, 'Unauthorized'),
  429: jsonResponse(ErrorResponse, 'Rate limit'),
  500: jsonResponse(ErrorResponse, 'Internal error'),
}

registry.registerPath({
  method: 'get',
  path: '/api/v1/wb-reports/pnl',
  operationId: 'wbReportsGetPnl',
  summary: 'Get WB P&L report',
  description: '19.05 contract: P&L can be operative/preliminary/blocked; final state is forbidden while source blockers remain.',
  request: {
    query: PeriodQuerySchema.extend({
      source: z.enum(['operational', 'financial']).optional(),
      groupBy: z.enum(['sku', 'brand', 'manager', 'category', 'status']).optional(),
    }),
  },
  responses: {
    200: jsonResponse(PnlReportResponse, 'P&L report'),
    ...errorResponses,
  },
})

registry.registerPath({
  method: 'get',
  path: '/api/v1/wb-reports/expenses',
  operationId: 'wbReportsGetExpenses',
  summary: 'Get WB expenses report',
  description: 'Manual/Excel OPEX rows for P&L. Final P&L remains blocked until WB-12/WB-13/WB-24 close.',
  request: { query: PeriodQuerySchema },
  responses: {
    200: jsonResponse(ExpensesReportResponse, 'Expenses report'),
    ...errorResponses,
  },
})

registry.registerPath({
  method: 'post',
  path: '/api/v1/wb-reports/expenses/import/preview',
  operationId: 'wbReportsPreviewExpensesImport',
  summary: 'Preview WB expenses import',
  description: 'Excel/manual expenses import preview. Commit is forbidden while approval or finance blockers remain.',
  request: {
    query: PeriodQuerySchema,
    body: {
      content: {
        'application/json': { schema: ExpenseImportPreviewRequestSchema },
      },
    },
  },
  responses: {
    200: jsonResponse(ExpenseImportPreviewResponse, 'Expenses import preview'),
    ...errorResponses,
  },
})

registry.registerPath({
  method: 'post',
  path: '/api/v1/wb-reports/expenses/import/commit',
  operationId: 'wbReportsCommitExpensesImport',
  summary: 'Commit WB expenses import',
  description: 'Commits an approved expenses import. Without approval the response remains blocked and committed=false.',
  request: {
    query: PeriodQuerySchema,
    body: {
      content: {
        'application/json': { schema: ExpenseImportCommitRequestSchema },
      },
    },
  },
  responses: {
    200: jsonResponse(ExpenseImportCommitResponse, 'Expenses import commit'),
    ...errorResponses,
  },
})

registry.registerPath({
  method: 'get',
  path: '/api/v1/wb-sources/status',
  operationId: 'wbSourcesGetStatus',
  summary: 'Get WB source status registry',
  description: 'Source registry/freshness/blocker/evidence status for WB Phase 1 production metrics.',
  request: { query: PeriodQuerySchema },
  responses: {
    200: jsonResponse(SourceStatusResponse, 'Source status registry'),
    ...errorResponses,
  },
})

registry.registerPath({
  method: 'get',
  path: '/api/v1/wb-reports/ads/performance',
  operationId: 'wbReportsGetAdsPerformance',
  summary: 'Get WB Ads performance report',
  description: '19.05 contract: campaign-only spend stays campaign-level and must not be presented as exact SKU P&L.',
  request: { query: ReportGroupByQuerySchema },
  responses: {
    200: jsonResponse(AdsPerformanceResponse, 'Ads performance report'),
    ...errorResponses,
  },
})

registry.registerPath({
  method: 'get',
  path: '/api/v1/wb-reports/rnp',
  operationId: 'wbReportsGetRnp',
  summary: 'Get WB RNP report',
  description: '19.05 contract: DRR/formula and ads source blockers remain visible until WB-02/WB-11 are closed.',
  request: { query: ReportGroupByQuerySchema },
  responses: {
    200: jsonResponse(RnpReportResponse, 'RNP report'),
    ...errorResponses,
  },
})

registry.registerPath({
  method: 'get',
  path: '/api/v1/wb-reports/abc',
  operationId: 'wbReportsGetAbc',
  summary: 'Get WB ABC report',
  description: '19.05 contract: response includes filteredSummary for the current filter/group set.',
  request: { query: ReportGroupByQuerySchema },
  responses: {
    200: jsonResponse(AbcReportResponse, 'ABC report'),
    ...errorResponses,
  },
})

registry.registerPath({
  method: 'get',
  path: '/api/v1/wb-repricer/sku/{articleId}/price-guard',
  operationId: 'wbRepricerGetPriceGuard',
  summary: 'Get WB repricer price guard state',
  description: '19.05 contract: frontend displays backend guard state; canApply=true is incompatible with unresolved SPP/source blockers.',
  request: {
    params: z.object({
      articleId: z.string().min(1),
    }),
  },
  responses: {
    200: jsonResponse(PriceGuardResponse, 'Price guard state'),
    ...errorResponses,
  },
})

const generator = new OpenApiGeneratorV31(registry.definitions)
const document = generator.generateDocument({
  openapi: '3.1.0',
  info: {
    title: 'Vella WB API contracts',
    version: '0.19.05-runtime-boundary',
    description: 'Frontend-first OpenAPI artifact for 19.05 WB contract delta. Draft until backend review confirms WB source availability.',
  },
  servers: [{ url: '/' }],
})

const currentFile = fileURLToPath(import.meta.url)
const outputPath = resolve(dirname(currentFile), '../../contracts/openapi/v1.yaml')
mkdirSync(dirname(outputPath), { recursive: true })
writeFileSync(outputPath, YAML.stringify(document), 'utf8')

console.log(`OpenAPI 3.1 written to ${outputPath}`)

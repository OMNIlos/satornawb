import { z } from 'zod'

export const SourceStatusSchema = z.enum(['fresh', 'partial', 'stale', 'blocked', 'unknown'])
export type SourceStatus = z.infer<typeof SourceStatusSchema>

export const ConfidenceSchema = z.enum(['high', 'medium', 'low', 'blocked'])
export type Confidence = z.infer<typeof ConfidenceSchema>

export const SourceTypeSchema = z.enum(['wb_api', 'wb_excel', 'one_c', 'manual', 'derived', 'mock'])
export type SourceType = z.infer<typeof SourceTypeSchema>

export const DatePeriodSchema = z.object({
  dateFrom: z.string().date(),
  dateTo: z.string().date(),
})
  .refine((period) => period.dateTo >= period.dateFrom, {
    message: 'dateTo must be greater than or equal to dateFrom',
    path: ['dateTo'],
  })
export type DatePeriod = z.infer<typeof DatePeriodSchema>

export const SourceEvidenceSchema = z.object({
  sourceId: z.string().min(1),
  sourceType: SourceTypeSchema,
  sourceName: z.string().min(1),
  lastSyncedAt: z.string().datetime().nullable(),
  freshnessTtlMinutes: z.number().int().positive().nullable(),
  fieldsUsed: z.array(z.string().min(1)),
})
export type SourceEvidence = z.infer<typeof SourceEvidenceSchema>

export const SourceStateBaseSchema = z.object({
  sourceStatus: SourceStatusSchema,
  confidence: ConfidenceSchema,
  blockerIds: z.array(z.string().min(1)),
  sourceEvidence: z.array(SourceEvidenceSchema),
  calculatedAt: z.string().datetime(),
  period: DatePeriodSchema,
})
export type SourceStateBase = z.infer<typeof SourceStateBaseSchema>

export function validateSourceStateConsistency(state: SourceStateBase, ctx: z.RefinementCtx) {
  if ((state.sourceStatus === 'blocked' || state.sourceStatus === 'unknown') && state.blockerIds.length === 0) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Blocked or unknown source state must reference at least one blocker ID',
      path: ['blockerIds'],
    })
  }

  if (state.sourceStatus === 'blocked' && state.confidence !== 'blocked') {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Blocked source state must expose blocked confidence',
      path: ['confidence'],
    })
  }
}

export const SourceStateSchema = SourceStateBaseSchema
  .superRefine(validateSourceStateConsistency)
export type SourceState = z.infer<typeof SourceStateSchema>

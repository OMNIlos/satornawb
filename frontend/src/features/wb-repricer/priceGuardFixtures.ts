import { PriceGuardResponseSchema, type PriceGuardResponse } from './schemas'
import { SKU_LIST } from './skuListFixtures'

const SPP_BLOCKERS = ['WB-06', 'WB-22', 'WB-23']

export function getPriceGuardFixture(articleId: string): PriceGuardResponse {
  const row = SKU_LIST.find((item) => item.meta.articleId === articleId)
  const currentPriceKopecks = row?.meta.currentPriceKopecks ?? null
  return PriceGuardResponseSchema.parse({
    articleId,
    currentPriceKopecks,
    buyerPriceKopecks: null,
    sppSnapshot: {
      sourceStatus: 'unknown',
      sppPct: null,
      buyerPriceKopecks: null,
      capturedAt: null,
      blockerIds: ['WB-06'],
    },
    recommendedSellerPriceKopecks: null,
    lastKnownGoodPriceKopecks: currentPriceKopecks,
    canApply: false,
    blockedReason: 'SPP source is not confirmed',
    freezeState: 'source_blocked',
    guardTriggers: [{
      type: 'source_stale',
      severity: 'blocker',
      observedValue: 'unknown',
      previousValue: null,
      threshold: null,
      message: 'SPP source must be confirmed before price apply',
    }],
    sourceEvidence: [{
      sourceId: 'wb-spp-discovery-placeholder',
      sourceType: 'mock',
      sourceName: 'WB SPP discovery placeholder',
      lastSyncedAt: null,
      freshnessTtlMinutes: null,
      fieldsUsed: [],
    }],
    blockerIds: SPP_BLOCKERS,
  })
}

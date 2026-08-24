import { afterEach, describe, expect, it, vi } from 'vitest'

import { downloadAvitoOrdersPickingXlsx } from './avitoOrdersXlsx'

describe('downloadAvitoOrdersPickingXlsx', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('downloads the Avito picking list xlsx for the selected date and status', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(new Blob(['xlsx']), {
        status: 200,
        headers: {
          'content-type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          'content-disposition': 'attachment; filename="avito-picking-list-2026-07-01.xlsx"',
        },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const link = { href: '', download: '', click: vi.fn(), remove: vi.fn() }
    const createObjectUrl = vi.fn(() => 'blob:avito-orders')
    const revokeObjectUrl = vi.fn()

    const filename = await downloadAvitoOrdersPickingXlsx('access-token', {
      dateFrom: '2026-07-01',
      periodDays: 30,
      status: 'ready_to_ship',
    }, {
      createObjectUrl,
      revokeObjectUrl,
      createLink: () => link,
    })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/avito/orders/picking-list.xlsx?dateFrom=2026-07-01&periodDays=30&status=ready_to_ship'),
      expect.objectContaining({
        headers: { Authorization: 'Bearer access-token' },
        credentials: 'include',
      }),
    )
    expect(filename).toBe('avito-picking-list-2026-07-01.xlsx')
    expect(link.href).toBe('blob:avito-orders')
    expect(link.download).toBe('avito-picking-list-2026-07-01.xlsx')
    expect(link.click).toHaveBeenCalledTimes(1)
    expect(link.remove).toHaveBeenCalledTimes(1)
    expect(createObjectUrl).toHaveBeenCalledTimes(1)
    expect(revokeObjectUrl).toHaveBeenCalledWith('blob:avito-orders')
  })
})

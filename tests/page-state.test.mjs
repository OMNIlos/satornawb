import assert from 'node:assert/strict'
import test from 'node:test'

test('finds an Avito item hidden in React order-detail props', async () => {
  delete globalThis.SatornaAvitoPageState
  await import(`../src/page-state.js?red=${Date.now()}`).catch(() => {})

  const state = {
    children: {
      order: {
        marketplaceId: '70000000486515763',
        goods: [{
          avitoId: '8098482225',
          title: 'Лонгслив y2k opium archive anime',
          url: '/voronezh/odezhda_obuv_aksessuary/longsliv_y2k_opium_archive_anime_8098482225',
        }],
      },
    },
  }

  const candidates = globalThis.SatornaAvitoPageState?.findCandidates(
    state,
    'Лонгслив y2k opium archive anime',
  )

  assert.deepEqual(candidates, [{
    itemId: '8098482225',
    itemUrl: 'https://www.avito.ru/voronezh/odezhda_obuv_aksessuary/longsliv_y2k_opium_archive_anime_8098482225',
    title: 'Лонгслив y2k opium archive anime',
    score: 180,
  }])
})

test('builds a listing URL when React state exposes only the Avito item id', async () => {
  const candidates = globalThis.SatornaAvitoPageState.findCandidates(
    {
      order: {
        id: '70000000486519208',
        product: {
          itemId: '8226657890',
          title: 'Футболка ERD Mulholland Drive',
        },
      },
    },
    'Футболка ERD Mulholland Drive',
  )

  assert.equal(
    candidates[0]?.itemUrl,
    'https://www.avito.ru/items/8226657890',
  )
})

test('keeps only Avito order and item resource URLs for runtime diagnostics', () => {
  const resources = globalThis.SatornaAvitoPageState?.networkResourceUrls?.({
    getEntriesByType: () => [
      { name: 'https://www.avito.ru/assets/app.js' },
      { name: 'https://www.avito.ru/web/1/order/70000000486519208' },
      { name: 'https://www.avito.ru/api/18/items/8226657890' },
      { name: 'https://70.img.avito.st/image.jpg' },
    ],
  })

  assert.deepEqual(resources, [
    'https://www.avito.ru/web/1/order/70000000486519208',
    'https://www.avito.ru/api/18/items/8226657890',
  ])
})

test('finds an Avito item in a non-React component state attached to a DOM node', () => {
  const componentNode = {
    __vueParentComponent: {
      props: {
        order: {
          item: {
            avitoId: '8345678901',
            title: 'Худи google search',
          },
        },
      },
    },
  }
  const root = {
    documentElement: componentNode,
    body: null,
    querySelectorAll: () => [],
  }

  const candidates = globalThis.SatornaAvitoPageState.collectFromDocument(root, 'Худи google search')

  assert.equal(candidates[0]?.itemId, '8345678901')
  assert.equal(
    candidates[0]?.itemUrl,
    'https://www.avito.ru/items/8345678901',
  )
})

test('loads the ordered Avito item from the profile order JSON resource', async () => {
  const fetchApi = async (url) => ({
    ok: true,
    status: 200,
    url,
    json: async () => ({
      result: {
        order: {
          id: '70000000486519208',
          item: {
            id: '8226657890',
            title: 'Футболка ERD Mulholland Drive',
            description: 'Размер: M\nЦвет: черный',
          },
        },
      },
    }),
  })

  const loaded = await globalThis.SatornaAvitoPageState?.loadCandidatesFromOrderResources?.(
    ['https://www.avito.ru/web/2/profile/order?referenceID=70000000486519208'],
    'Футболка ERD Mulholland Drive',
    fetchApi,
  )

  assert.equal(loaded?.candidates[0]?.itemId, '8226657890')
  assert.equal(
    loaded?.candidates[0]?.itemUrl,
    'https://www.avito.ru/items/8226657890',
  )
  assert.deepEqual(loaded?.requests, [{
    url: 'https://www.avito.ru/web/2/profile/order?referenceID=70000000486519208',
    status: 200,
    candidates: 1,
  }])
  assert.match(loaded?.resourceText || '', /Размер:\s*M/)
  assert.match(loaded?.resourceText || '', /Цвет:\s*черный/)
})

test('builds the profile order JSON URL when the performance entry is missing', () => {
  const resourceUrl = globalThis.SatornaAvitoPageState?.profileOrderResourceUrl?.(
    'https://www.avito.ru/orders/70000000486695926?source=orders_list',
    'Asia/Yekaterinburg',
  )

  assert.equal(
    resourceUrl,
    'https://www.avito.ru/web/2/profile/order?referenceID=70000000486695926&templateVersion=0&srcp=orders_list&location=Asia%2FYekaterinburg',
  )
})

test('rejects an unrelated Avito item id when its title does not match the order', () => {
  const candidates = globalThis.SatornaAvitoPageState?.findCandidates?.(
    {
      unrelatedListing: {
        id: '365024549',
        title: 'Bless T',
      },
    },
    'Лонгслив 1017 alyx 9sm',
  )

  assert.deepEqual(candidates, [])
})

test('binds itemId to the matching product block in the profile order payload', async () => {
  const fetchApi = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      unrelatedListing: {
        id: '365024549',
        title: 'Bless T',
      },
      widgets: [{
        payload: 'action://open?itemId=8226657890',
        quantity: 1,
        title: 'Футболка ERD Mulholland Drive',
      }],
    }),
  })

  const loaded = await globalThis.SatornaAvitoPageState?.loadCandidatesFromOrderResources?.(
    ['https://www.avito.ru/web/2/profile/order?referenceID=70000000486519208'],
    'Футболка ERD Mulholland Drive',
    fetchApi,
  )

  assert.equal(loaded?.candidates[0]?.itemId, '8226657890')
  assert.equal(loaded?.candidates[0]?.itemUrl, 'https://www.avito.ru/items/8226657890')
})

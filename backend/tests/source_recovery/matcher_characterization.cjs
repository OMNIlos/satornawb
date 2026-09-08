'use strict';

// Reads exactly one code file, never a pool, customer workbook, or browser profile.
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const { test } = require('node:test');
const source = fs.readFileSync(process.env.MATCHER_SOURCE_APP_JS, 'utf8');
assert.equal(crypto.createHash('sha256').update(source).digest('hex'),
  'b20e29ee1fcaef4b122df709f1d51eae3a6348c69cce9e0e5668402d8f9aa610');

function section(start, end) {
  const first = source.indexOf(start);
  const last = source.indexOf(end, first + start.length);
  assert.ok(first >= 0 && last > first);
  return source.slice(first, last);
}

function context() {
  const state = { matched: [], chzPages: [], wbPages: [], serverChz: true };
  const c = vm.createContext({
    state, Blob, Set, console: { error() {} },
    fetch() { throw new Error('Network forbidden'); },
    progressFill: { style: {} }, progressText: {}, progressWrap: { style: {} },
    updateChzStatus() {}, showError(message) { c.error = message; },
    setChzPages(rows) { state.chzPages = rows; },
  });
  vm.runInContext([
    section('const FIRST_PICK_SHEET_BATCH_SIZE', 'const CHZ_BASE_URL'),
    section('const ORDINALS', 'const state'),
    section('function shortKis(', 'async function loadConsumedChzKeys('),
    section('function extractKisFromText(', 'function extractNameFromChzItems('),
    section('function stickerDigitGroups(', '// ----'),
    section('async function buildPdf()', '// Re-render each matched'),
  ].join('\n'), c, { timeout: 1000 });
  return c;
}

test('synthetic code parsing, separator escaping and used-key aliases', () => {
  const c = context();
  const short = '010000000000000021SYNTHETIC-ONLY';
  const full = short + '\x1d91SYNTHETIC\x1d92SYNTHETIC';
  assert.equal(c.shortKis(full), short);
  assert.equal(c.isFullKis(full), true);
  assert.equal(c.excelKisValue(full), full.replaceAll('\x1d', '_x001d_'));
  assert.equal(c.hasConsumedChzKey({ kis: full }, new Set([short])), true);
  const parsed = c.parseChzItems(['Synthetic garment', 'Состав', '100% хлопок', 'Размер:', 'M', 'Цвет: белый']);
  assert.equal(parsed.name, 'Synthetic garment');
  assert.equal(parsed.size, 'M');
  assert.equal(parsed.color, 'белый');
});

test('sticker matcher strips zeros and admits partial numeric matches', () => {
  const c = context();
  c.state.wbPages = [{ digitTokens: ['12'], text: 'synthetic' }];
  assert.equal(c.findWbByStickerNumber('0012-0099', new Set()), 0);
  assert.equal(c.findWbByStickerNumber('0012-0099', new Set([0])), -1);
});

test('download consumption suppresses duplicate calls only in this memory state', async () => {
  const c = context();
  c.state.matched = [{ chzFound: true, chzData: { kis: 'SYNTHETIC-ONLY' } }];
  c.rememberGeneratedChzUse();
  let calls = 0;
  c.consumeServerChzKeys = async () => { calls++; return { consumedKeys: ['SYNTHETIC-ONLY'], deletedCount: 1 }; };
  await Promise.all([c.consumeGeneratedChzOnce(), c.consumeGeneratedChzOnce()]);
  assert.equal(calls, 1);
  c.rememberGeneratedChzUse();
  await c.consumeGeneratedChzOnce();
  assert.equal(calls, 2);
});

test('uncertain server failure resets consumed flag and allows retry', async () => {
  const c = context();
  c.state.generatedChzUse = { keys: ['SYNTHETIC-ONLY'], consumed: false };
  c.consumeServerChzKeys = async () => { throw new Error('synthetic-timeout'); };
  await c.consumeGeneratedChzOnce();
  assert.equal(c.state.generatedChzUse.consumed, false);
  assert.ok(c.error.includes('synthetic-timeout'));
});

test('XLSX adapter forwards one row per match without quantity expansion', () => {
  const c = context();
  let rows;
  c.XLSX = { utils: {
    aoa_to_sheet(value) { rows = value; return {}; },
    book_new() { return {}; }, book_append_sheet() {},
  }, write() { return new Uint8Array(); } };
  c.state.matched = [{ item: { номерЗадания: '000synthetic', стикер: 'synthetic', quantity: 3 }, kis: 'SYNTHETIC' }];
  c.buildXlsx();
  assert.equal(rows.length, 2);
  assert.equal(rows[1][0], '000synthetic');
});

test('PDF orchestration uses 58x40 and first10/next11 divider grouping', async () => {
  const c = context();
  let pages = 1;
  c.jsPDF = function (options) {
    assert.equal(options.format.join(','), '58,40');
    return { addPage() { pages++; }, output() { return pages; } };
  };
  c.preloadSourceChzImages = async () => {};
  c.addFullLabelImage = () => {};
  c.makeDividerImage = text => text;
  c.makeBlankLabelImage = text => text;
  c.sleep = async () => {};
  c.state.matched = Array.from({ length: 22 }, () => ({}));
  assert.equal(await c.buildPdf(), 47); // 44 labels + three dividers, no actual rendering.
});

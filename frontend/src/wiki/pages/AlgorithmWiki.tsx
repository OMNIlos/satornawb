import { useState } from 'react'
import { WikiLayout, WikiSection } from '../WikiLayout'
import { ROUTES } from '@/lib/routes'

const SECTIONS = [
  { id: 'how-it-works', title: 'Как работает' },
  { id: 'instructions', title: 'Пошаговые инструкции' },
  { id: 'faq', title: 'Частые вопросы' },
  { id: 'glossary', title: 'Термины' },
]

export function AlgorithmWiki() {
  return (
    <WikiLayout
      title="Настройки алгоритма"
      subtitle="Параметры автоматического управления ценами"
      sections={SECTIONS}
      activeModule={ROUTES.wiki.algorithm}
    >
      <HowItWorks />
      <Instructions />
      <Faq />
      <Glossary />
    </WikiLayout>
  )
}

function HowItWorks() {
  return (
    <WikiSection id="how-it-works" title="Как работает">
      <p className="text-sm text-foreground leading-relaxed mb-6">
        Страница «Алгоритм» — глобальные параметры для всех SKU: шаг изменения цены, дневной лимит
        корректировок, порог для смены направления и режим ночной медианы. Изменения применяются ко
        всем SKU в автоматическом режиме.
      </p>

      <h3 className="text-sm font-semibold text-foreground mb-3">Шаг цены и дневной лимит</h3>
      <div className="bg-card border border-border rounded-lg overflow-hidden mb-6">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/40 border-b border-border">
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide w-40">Параметр</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Что делает</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide w-24">Рекомендация</th>
            </tr>
          </thead>
          <tbody>
            {PARAMS.map((p, i) => (
              <tr key={p.name} className={i % 2 === 0 ? 'bg-card' : 'bg-muted/40'}>
                <td className="px-4 py-3 font-medium text-foreground align-top">{p.name}</td>
                <td className="px-4 py-3 text-muted-foreground leading-relaxed align-top">{p.desc}</td>
                <td className="px-4 py-3 font-mono text-foreground align-top text-xs">{p.rec}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="text-sm font-semibold text-foreground mb-3">Ночная медиана (23:00–04:00)</h3>
      <p className="text-sm text-muted-foreground leading-relaxed mb-3">
        WB ранжирует товары по медиане цен похожих артикулов. Ночью конкурентов меньше — поднять цену
        временно выгоднее. Алгоритм автоматически поднимает цену в 23:00 и восстанавливает в 04:00.
      </p>
      <div className="grid grid-cols-2 gap-3 mb-6">
        {NIGHT_MODES.map((m) => (
          <div key={m.title} className="bg-card border border-border rounded-lg p-4">
            <div className="text-sm font-semibold text-foreground mb-1">{m.title}</div>
            <div className="text-xs text-muted-foreground leading-relaxed mb-2">{m.desc}</div>
            <div className="text-xs text-muted-foreground/70 italic">{m.tip}</div>
          </div>
        ))}
      </div>

      <h3 className="text-sm font-semibold text-foreground mb-3">Защита от прыжков цены</h3>
      <div className="space-y-3 text-sm mb-4">
        {JUMP_PROTECTION.map((j) => (
          <div key={j.label} className="flex gap-3">
            <span className="text-muted-foreground/60 font-mono w-4 flex-shrink-0 mt-0.5">→</span>
            <div>
              <span className="font-semibold text-foreground">{j.label}:</span>{' '}
              <span className="text-muted-foreground">{j.desc}</span>
            </div>
          </div>
        ))}
      </div>
    </WikiSection>
  )
}

function Instructions() {
  return (
    <WikiSection id="instructions" title="Пошаговые инструкции">
      <h3 className="text-sm font-semibold text-foreground mb-3">Настроить шаг и лимит изменений</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside mb-6">
        <li>Откройте <strong>Репрайсер → Алгоритм</strong>.</li>
        <li>В блоке «Шаг цены» задайте процент или рублёвое значение на один шаг.</li>
        <li>В блоке «Дневной лимит» задайте максимальное число корректировок в сутки на SKU.</li>
        <li>Сохраните — изменения применятся с ближайшего цикла.</li>
      </ol>

      <h3 className="text-sm font-semibold text-foreground mb-3">Включить ночную медиану</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside mb-6">
        <li>В блоке «Ночная медиана» переключите режим: <em>Выключено</em> / <em>Консервативный</em> / <em>Агрессивный</em>.</li>
        <li>Консервативный: +5% в 23:00, возврат в 04:00.</li>
        <li>Агрессивный: +10% в 23:00, возврат в 04:00.</li>
        <li>Сохраните. Настройка применяется ко всем SKU в автоматическом режиме.</li>
      </ol>

      <h3 className="text-sm font-semibold text-foreground mb-3">Изменить порог смены направления</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside">
        <li>В блоке «Корзины» найдите параметр «Порог отклонения от нормы».</li>
        <li>Значение в % — насколько корзины должны отличаться от нормы, чтобы сработал алгоритм.</li>
        <li>Низкий порог (5–10%): частые мелкие корректировки. Высокий (20–30%): редкие, но весомые.</li>
        <li>Сохраните. Изменение применяется ко всем SKU немедленно.</li>
      </ol>
    </WikiSection>
  )
}

function Faq() {
  const items = [
    {
      q: 'Что лучше — большой шаг или маленький?',
      a: 'Маленький шаг (1–3%) даёт более плавную динамику. Большой шаг (5–10%) быстрее реагирует на спрос, но повышает риск слишком резкого движения. Для старта рекомендуем 3%.',
    },
    {
      q: 'Как дневной лимит влияет на алгоритм?',
      a: 'Лимит ограничивает число изменений одного SKU за сутки. Если лимит = 2, то за день цена изменится максимум дважды: один раз вверх/вниз по алгоритму и один раз по ночной медиане. Без лимита алгоритм будет корректировать при каждом цикле.',
    },
    {
      q: 'Ночная медиана применяется ко всем SKU одновременно?',
      a: 'Да, настройка глобальная. Все SKU в автоматическом режиме получат повышение в 23:00 и восстановление в 04:00. SKU в ручном режиме или прогреве не затрагиваются.',
    },
    {
      q: 'Почему алгоритм иногда не меняет цену несмотря на отклонение корзин?',
      a: 'Причины: текущая цена уже на границе P_min или максимальной цены, SKU в прогреве, дневной лимит исчерпан, отклонение корзин меньше порога смены направления.',
    },
    {
      q: 'Как учитывать резкие скачки цены?',
      a: 'Алгоритм автоматически ограничивает шаг изменения цены. Сейчас шаг можно настроить до 50% за цикл, а дневной лимит задаётся отдельно.',
    },
  ]

  return (
    <WikiSection id="faq" title="Частые вопросы">
      <div className="space-y-1">
        {items.map((item) => <FaqItem key={item.q} q={item.q} a={item.a} />)}
      </div>
    </WikiSection>
  )
}

function Glossary() {
  const terms = [
    { term: 'Шаг цены', def: 'Величина изменения цены за один цикл алгоритма. Задаётся в % или ₽. Рекомендуемое значение: 3–5%.' },
    { term: 'Дневной лимит', def: 'Максимальное число ценовых корректировок для одного SKU за 24 часа.' },
    { term: 'Порог отклонения', def: 'Минимальное отклонение корзин от нормы (в %), при котором алгоритм принимает решение об изменении цены.' },
    { term: 'Ночная медиана', def: 'Режим повышения цены с 23:00 до 04:00 МСК. Консервативный (+5%) или агрессивный (+10%).' },
    { term: 'Глобальные настройки', def: 'Параметры страницы «Алгоритм» применяются ко всем SKU в автоматическом режиме одновременно.' },
  ]

  return (
    <WikiSection id="glossary" title="Термины">
      <div className="space-y-3">
        {terms.map((t) => (
          <div key={t.term} className="flex gap-3 text-sm">
            <span className="font-semibold text-foreground w-40 flex-shrink-0">{t.term}</span>
            <span className="text-muted-foreground leading-relaxed">{t.def}</span>
          </div>
        ))}
      </div>
    </WikiSection>
  )
}

function FaqItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-muted/40 transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="text-sm font-medium text-foreground">{q}</span>
        <svg className={`w-4 h-4 flex-shrink-0 text-muted-foreground/70 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && <div className="px-4 pb-4 text-sm text-muted-foreground leading-relaxed border-t border-border/60 pt-3">{a}</div>}
    </div>
  )
}

const PARAMS = [
  { name: 'Шаг цены', desc: 'На сколько изменяется цена за один цикл. Слишком большой шаг повышает риск резкого движения.', rec: '3–5%' },
  { name: 'Дневной лимит', desc: 'Максимум корректировок одного SKU за 24 часа. Защита от чрезмерной волатильности.', rec: '2–3' },
  { name: 'Порог отклонения', desc: 'Минимальное отклонение корзин от нормы для срабатывания алгоритма.', rec: '10–15%' },
]

const NIGHT_MODES = [
  {
    title: 'Консервативный (+5%)',
    desc: 'Умеренное повышение. Подходит для большинства категорий.',
    tip: 'Рекомендуется для старта — меньший риск потери корзин ночью.',
  },
  {
    title: 'Агрессивный (+10%)',
    desc: 'Максимальное повышение в ночное время.',
    tip: 'Подходит для товаров с устойчивым ночным спросом.',
  },
]

const JUMP_PROTECTION = [
  { label: 'Лимит шага', desc: 'Алгоритм ограничивает изменение цены выбранным шагом за цикл и отдельно проверяет дневной лимит.' },
  { label: 'Мягкие переходы', desc: 'При возврате ночной медианы к дневной цене система тоже использует шаговый возврат, не прыгает сразу.' },
  { label: 'Проверка границ', desc: 'Перед каждым изменением цены алгоритм проверяет, не выходит ли результат за P_min и максимальную цену.' },
]

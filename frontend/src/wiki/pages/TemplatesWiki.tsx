import { useState } from 'react'
import { WikiLayout, WikiSection } from '../WikiLayout'
import { ROUTES } from '@/lib/routes'

const SECTIONS = [
  { id: 'how-it-works', title: 'Как работает' },
  { id: 'instructions', title: 'Пошаговые инструкции' },
  { id: 'faq', title: 'Частые вопросы' },
  { id: 'glossary', title: 'Термины' },
]

export function TemplatesWiki() {
  return (
    <WikiLayout
      title="Шаблоны"
      subtitle="Массовое применение настроек репрайсера"
      sections={SECTIONS}
      activeModule={ROUTES.wiki.templates}
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
      <p className="text-sm text-foreground leading-relaxed mb-5">
        Шаблоны позволяют задать одинаковые настройки репрайсера сразу для группы SKU. Вместо того чтобы
        заходить в карточку каждого артикула, вы создаёте шаблон с нужными параметрами и применяете его
        к нужным товарам одним действием.
      </p>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <BenefitCard icon="⚡" title="Массовое применение" body="Один шаблон — тысяча SKU. Обновили шаблон → изменения применились ко всем." />
        <BenefitCard icon="🎯" title="Группировка по типу" body="Разные шаблоны для футболок, худи, лонгсливов с учётом разной маржинальности." />
        <BenefitCard icon="🔄" title="Приоритет индивидуальных" body="Настройки карточки SKU всегда перекрывают шаблон — исключения не нарушают правило." />
      </div>

      <h3 className="text-sm font-semibold text-foreground mb-3">Шаблон vs индивидуальные настройки</h3>
      <div className="bg-card border border-border rounded-lg overflow-hidden mb-6">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/40 border-b border-border">
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide w-40">Сценарий</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Что применяется</th>
            </tr>
          </thead>
          <tbody>
            {PRIORITY_TABLE.map((r, i) => (
              <tr key={r.scenario} className={i % 2 === 0 ? 'bg-card' : 'bg-muted/40'}>
                <td className="px-4 py-3 font-medium text-foreground align-top">{r.scenario}</td>
                <td className="px-4 py-3 text-muted-foreground leading-relaxed align-top">{r.result}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="text-sm font-semibold text-foreground mb-3">Параметры шаблона</h3>
      <div className="space-y-3 text-sm">
        {TEMPLATE_PARAMS.map((p) => (
          <div key={p.label} className="flex gap-3">
            <span className="text-muted-foreground/60 font-mono w-4 flex-shrink-0 mt-0.5">→</span>
            <div>
              <span className="font-semibold text-foreground">{p.label}:</span>{' '}
              <span className="text-muted-foreground">{p.desc}</span>
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
      <h3 className="text-sm font-semibold text-foreground mb-3">Создать новый шаблон</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside mb-6">
        <li>Откройте <strong>Репрайсер → Шаблоны</strong>.</li>
        <li>Нажмите <strong>Создать шаблон</strong>.</li>
        <li>Введите название (например: «Футболки базовые», «Худи новинки»).</li>
        <li>Заполните общие параметры: Комиссия WB, Логистика WB, Целевая маржа.</li>
        <li>Нажмите <strong>Сохранить</strong>.</li>
      </ol>

      <h3 className="text-sm font-semibold text-foreground mb-3">Применить шаблон к группе SKU</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside mb-6">
        <li>В разделе <strong>Репрайсер → Товары</strong> выберите нужные артикулы (галочки в таблице).</li>
        <li>Нажмите <strong>Применить шаблон</strong> в панели массовых действий.</li>
        <li>Выберите нужный шаблон из списка.</li>
        <li>Подтвердите — P_min пересчитается для всех выбранных SKU.</li>
      </ol>

      <h3 className="text-sm font-semibold text-foreground mb-3">Обновить шаблон (изменить параметры)</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside mb-6">
        <li>Откройте <strong>Репрайсер → Шаблоны</strong>.</li>
        <li>Кликните на нужный шаблон и отредактируйте параметры.</li>
        <li>Нажмите <strong>Сохранить</strong>.</li>
        <li>Изменения применятся ко всем SKU, использующим этот шаблон.</li>
      </ol>

      <h3 className="text-sm font-semibold text-foreground mb-3">Переопределить параметр для отдельного SKU</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside">
        <li>Откройте карточку нужного SKU.</li>
        <li>Измените нужный параметр (например, Комиссию WB для уникальной категории).</li>
        <li>Сохраните — этот SKU будет использовать индивидуальное значение, остальные — из шаблона.</li>
      </ol>
    </WikiSection>
  )
}

function Faq() {
  const items = [
    {
      q: 'Что будет, если изменить шаблон, когда у части SKU есть индивидуальные настройки?',
      a: 'SKU с индивидуальными настройками не затрагиваются — они игнорируют шаблон по тому параметру, который задан индивидуально. Остальные SKU получат обновлённые значения из шаблона.',
    },
    {
      q: 'Можно ли у одного SKU использовать несколько шаблонов?',
      a: 'Нет — к одному SKU применяется один шаблон. Если нужны разные параметры, создайте отдельный шаблон или используйте индивидуальные настройки для исключений.',
    },
    {
      q: 'Что происходит с P_min при смене шаблона?',
      a: 'P_min пересчитывается мгновенно на основе новых параметров шаблона. min_price в WB API обновляется при следующем цикле синхронизации (обычно в течение 15 минут).',
    },
    {
      q: 'Как понять, что SKU использует шаблон, а не индивидуальные настройки?',
      a: 'В карточке SKU параметры из шаблона помечены меткой «из шаблона». Переопределённые параметры показаны без этой метки.',
    },
    {
      q: 'Как лучше группировать товары по шаблонам?',
      a: 'Рекомендуем группировать по типу товара (Футболка / Худи / Лонгслив) и уровню маржинальности. У разных категорий WB разная комиссия — для каждой стоит создать отдельный шаблон.',
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
    { term: 'Шаблон', def: 'Набор общих параметров репрайсера (комиссия, логистика, целевая маржа), применяемый к группе SKU.' },
    { term: 'Индивидуальные настройки', def: 'Параметры, заданные непосредственно в карточке SKU. Имеют приоритет над шаблоном.' },
    { term: 'Приоритет', def: 'Индивидуальные настройки > Шаблон. SKU без шаблона и без индивидуальных настроек не может быть сохранён.' },
    { term: 'Массовое применение', def: 'Применение одного шаблона к нескольким выбранным SKU одним действием.' },
  ]

  return (
    <WikiSection id="glossary" title="Термины">
      <div className="space-y-3">
        {terms.map((t) => (
          <div key={t.term} className="flex gap-3 text-sm">
            <span className="font-semibold text-foreground w-44 flex-shrink-0">{t.term}</span>
            <span className="text-muted-foreground leading-relaxed">{t.def}</span>
          </div>
        ))}
      </div>
    </WikiSection>
  )
}

function BenefitCard({ icon, title, body }: { icon: string; title: string; body: string }) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="text-2xl mb-2">{icon}</div>
      <div className="text-sm font-semibold text-foreground mb-1">{title}</div>
      <div className="text-xs text-muted-foreground leading-relaxed">{body}</div>
    </div>
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

const PRIORITY_TABLE = [
  { scenario: 'SKU без шаблона, без индивидуальных', result: 'Нельзя сохранить — нет данных для расчёта P_min.' },
  { scenario: 'SKU с шаблоном, без индивидуальных', result: 'Все параметры из шаблона.' },
  { scenario: 'SKU с шаблоном + индивидуальная комиссия', result: 'Комиссия — индивидуальная, остальное — из шаблона.' },
  { scenario: 'SKU с шаблоном + все параметры индивидуально', result: 'Шаблон игнорируется полностью.' },
]

const TEMPLATE_PARAMS = [
  { label: 'Название шаблона', desc: 'Произвольное название для идентификации (напр. «Худи осень 2026»).' },
  { label: 'Комиссия WB', desc: 'Процент комиссии WB для данной категории товаров.' },
  { label: 'Логистика WB', desc: 'Средняя стоимость доставки товара от склада до покупателя.' },
  { label: 'Целевая маржа', desc: 'Минимальная желаемая маржа в % для товаров этой группы.' },
]

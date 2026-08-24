import { useState } from 'react'

export function HelpPage({ onBack }: { onBack: () => void }) {
  return (
    <div className="max-w-3xl mx-auto pb-16">
      <div className="py-6 flex items-center gap-3">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Назад к настройкам
        </button>
      </div>

      <h1 className="text-2xl font-bold text-foreground mb-1">Как работает репрайсер WB</h1>
      <p className="text-sm text-muted-foreground mb-8">Справка по настройке и работе модуля автоматического управления ценами</p>

      <SectionWhy />
      <SectionAlgorithm />
      <SectionFields />
      <SectionStatuses />
      <SectionLiquidation />
      <SectionFaq />
    </div>
  )
}

// ─── Зачем репрайсер ─────────────────────────────────────────────────────────

function SectionWhy() {
  return (
    <Section title="Зачем нужен репрайсер?">
      <p className="text-sm text-foreground leading-relaxed mb-5">
        На Wildberries тысячи продавцов конкурируют за место в поиске — и цена напрямую влияет на позицию. Вручную
        отслеживать корзины по каждому артикулу и своевременно менять цены невозможно. Репрайсер делает это
        автоматически: следит за спросом и двигает цену в нужную сторону, не выходя за установленные вами границы.
      </p>
      <div className="grid grid-cols-3 gap-4">
        <BenefitCard
          icon="⏱"
          title="Экономит время"
          body="Не нужно вручную менять цены на каждом артикуле — система делает это по расписанию."
        />
        <BenefitCard
          icon="📈"
          title="Максимизирует выручку"
          body="Поднимает цену при высоком спросе — вы зарабатываете больше без потери позиций."
        />
        <BenefitCard
          icon="🛡"
          title="Защищает от убытков"
          body="Никогда не опустит цену ниже P_min — точки безубыточности, которую считает сам."
        />
      </div>
    </Section>
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

// ─── Алгоритм ────────────────────────────────────────────────────────────────

function SectionAlgorithm() {
  const steps = [
    {
      num: '1',
      title: 'Мониторим корзины',
      body: 'Каждый цикл система смотрит, сколько раз покупатели добавили товар в корзину за последние 7 дней.',
    },
    {
      num: '2',
      title: 'Сравниваем с нормой',
      body: 'Если корзин больше нормы — спрос высокий, цену можно поднять. Меньше нормы — снизить, чтобы привлечь покупателей.',
    },
    {
      num: '3',
      title: 'Двигаем цену на шаг',
      body: 'Изменение происходит постепенно — на заданный шаг роста или снижения. Система ограничивает резкие скачки цены.',
    },
    {
      num: '4',
      title: 'Проверяем границы',
      body: 'Новая цена проверяется: не ниже P_min (иначе убыток) и не выше Максимальной цены (иначе теряем конкурентоспособность).',
    },
    {
      num: '5',
      title: 'Синхронизируем с WB',
      body: 'Финальная цена отправляется в WB через API. Также обновляется min_price — защита от принудительного снижения на акциях.',
    },
  ]

  return (
    <Section title="Как работает алгоритм">
      <div className="space-y-3">
        {steps.map((s, i) => (
          <div key={s.num} className="flex gap-4">
            <div className="flex-shrink-0 w-7 h-7 rounded-full bg-indigo-100 text-indigo-600 dark:text-indigo-400 text-xs font-bold flex items-center justify-center">
              {s.num}
            </div>
            <div className="flex-1 pt-0.5">
              <div className="text-sm font-semibold text-foreground">{s.title}</div>
              <div className="text-sm text-muted-foreground mt-0.5">{s.body}</div>
              {i < steps.length - 1 && (
                <div className="mt-3 ml-[-44px] pl-[44px]">
                  <div className="w-px h-3 bg-muted ml-3" />
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </Section>
  )
}

// ─── Поля ────────────────────────────────────────────────────────────────────

function SectionFields() {
  const rows: { field: string; what: string; example: string; computed?: true }[] = [
    {
      field: 'Себестоимость',
      what: 'Сколько стоит произвести одну единицу товара. Включает материалы, труд, печать.',
      example: '450 ₽',
    },
    {
      field: 'Комиссия WB',
      what: 'Процент, который WB берёт с каждой проданной единицы. Зависит от категории.',
      example: '25%',
    },
    {
      field: 'Логистика WB',
      what: 'Стоимость доставки товара от склада до покупателя. Зависит от склада и зоны доставки.',
      example: '50 ₽',
    },
    {
      field: 'Целевая маржа',
      what: 'Минимальная прибыль в процентах, с которой вы готовы продавать товар.',
      example: '15%',
    },
    {
      field: 'P_min',
      what: 'Минимальная цена продажи без убытка. Рассчитывается автоматически на основе четырёх полей выше. WB не опустит цену ниже в акциях.',
      example: '833 ₽',
      computed: true,
    },
    {
      field: 'Максимальная цена',
      what: 'Потолок для алгоритма. Выше этой цены система не поднимет стоимость, даже при высоком спросе.',
      example: '1 900 ₽',
    },
  ]

  return (
    <Section title="Что значат поля">
      <div className="border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/40 border-b border-border">
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide w-40">
                Поле
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Что это
              </th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide w-24">
                Пример
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.field} className={i % 2 === 0 ? 'bg-card' : 'bg-muted/40'}>
                <td className="px-4 py-3 font-medium text-foreground align-top">
                  {r.field}
                  {r.computed && (
                    <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium rounded bg-indigo-100 text-indigo-600 dark:text-indigo-400">
                      авто
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-muted-foreground leading-relaxed align-top">{r.what}</td>
                <td className="px-4 py-3 font-mono text-foreground align-top">{r.example}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  )
}

// ─── Статусы ─────────────────────────────────────────────────────────────────

function SectionStatuses() {
  const statuses = [
    {
      badge: 'auto',
      className: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
      title: 'Автоматика активна',
      body: 'Репрайсер управляет ценой самостоятельно по алгоритму корзин. Вмешательство не требуется.',
      tip: 'Норма: SKU проработал 30+ дней и накопил достаточно данных.',
    },
    {
      badge: 'manual',
      className: 'bg-muted text-foreground border-border',
      title: 'Ручное управление',
      body: 'Автоматика отключена. Цена меняется только вручную через кнопку «Изменить цену».',
      tip: 'Используйте для ценовых экспериментов или временных акций.',
    },
    {
      badge: 'warmup',
      className: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30',
      title: 'Накопление данных',
      body: 'SKU добавлен менее 30 дней назад. Системе не хватает статистики для работы алгоритма.',
      tip: 'Автоматика включится сама после накопления 30 дней данных.',
    },
  ]

  return (
    <Section title="Статусы SKU">
      <div className="grid grid-cols-2 gap-4">
        {statuses.map((s) => (
          <div key={s.badge} className="bg-card border border-border rounded-lg p-4">
            <span
              className={`inline-flex items-center px-2 py-0.5 text-xs font-medium uppercase rounded border mb-2 ${s.className}`}
            >
              {s.badge}
            </span>
            <div className="text-sm font-semibold text-foreground mb-1">{s.title}</div>
            <div className="text-xs text-muted-foreground leading-relaxed mb-2">{s.body}</div>
            <div className="text-xs text-muted-foreground/70 italic">{s.tip}</div>
          </div>
        ))}
      </div>
    </Section>
  )
}

// ─── Ликвидация ──────────────────────────────────────────────────────────────

function SectionLiquidation() {
  return (
    <Section title="Режим ликвидации">
      <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 mb-4">
        <div className="flex gap-3">
          <span className="text-lg leading-none mt-0.5">⚠️</span>
          <div>
            <div className="text-sm font-semibold text-amber-800 dark:text-amber-200 mb-1">Режим для распродажи остатков</div>
            <div className="text-sm text-amber-700 dark:text-amber-300 leading-relaxed">
              При включении режима ликвидации алгоритм может снижать цену <strong>ниже P_min</strong> — то есть
              продавать товар с убытком. Это осознанное решение, когда нужно быстро освободить склад.
            </div>
          </div>
        </div>
      </div>
      <div className="space-y-3 text-sm text-foreground">
        <Row label="Когда использовать">
          Смена коллекции, залежавшиеся остатки, товары с истекающим сроком годности или плановая ротация ассортимента.
        </Row>
        <Row label="Что происходит">
          P_min в расчётах обнуляется. Алгоритм может опустить цену до минимально возможной (но не ниже 1 ₽). Маржа
          при этом будет отрицательной.
        </Row>
        <Row label="Подтверждение">
          Режим требует подтверждения каждые 24 часа. Если не подтвердить — система автоматически его выключит и
          вернётся к обычной логике.
        </Row>
      </div>
    </Section>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3">
      <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide whitespace-nowrap mt-0.5 w-36 flex-shrink-0">
        {label}
      </span>
      <span className="leading-relaxed">{children}</span>
    </div>
  )
}

// ─── FAQ ─────────────────────────────────────────────────────────────────────

function SectionFaq() {
  const items = [
    {
      q: 'Что такое «норма корзин» и откуда она берётся?',
      a: 'Норма — это ориентир: сколько раз товар должен добавляться в корзину за 7 дней при нормальном спросе. Источник значения выбирается в таком порядке: (1) ручной ввод руководителя (кнопка «изменить» рядом с нормой в карточке SKU) — приоритет всегда; (2) авторасчёт по addToCart из WB Analytics за 7 дней — когда накопилась статистика; (3) fallback по типу товара (Футболка/Худи/Лонгслив) — на период прогрева, пока данных нет. Ручной ввод нужен, если авторасчёт даёт заниженную норму из-за плохого прошлого (завышенная цена, слабые фото, отсутствие рекламы) — иначе репрайсер закрепит эту слабость как цель.',
    },
    {
      q: 'Почему цена не меняется, хотя автоматика включена?',
      a: 'Возможные причины: SKU находится в периоде warmup (менее 30 дней), количество корзин совпадает с нормой и изменение не требуется, текущая цена уже находится на границе P_min или Максимальной цены.',
    },
    {
      q: 'Что произойдёт, если Максимальная цена окажется ниже P_min?',
      a: 'Система покажет ошибку валидации прямо в форме и не позволит сохранить настройки. Максимальная цена всегда должна быть выше P_min — иначе алгоритму не с чем работать.',
    },
  ]

  return (
    <Section title="Частые вопросы">
      <div className="space-y-1">
        {items.map((item) => (
          <FaqItem key={item.q} q={item.q} a={item.a} />
        ))}
      </div>
    </Section>
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
        <svg
          className={`w-4 h-4 flex-shrink-0 text-muted-foreground/70 transition-transform ${open ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="px-4 pb-4 text-sm text-muted-foreground leading-relaxed border-t border-border/60 pt-3">{a}</div>
      )}
    </div>
  )
}

// ─── Layout helpers ───────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="text-base font-semibold text-foreground mb-4 pb-2 border-b border-border">{title}</h2>
      {children}
    </section>
  )
}

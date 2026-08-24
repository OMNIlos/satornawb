# PRD: NRP РнП WB / реклама

## 1. Назначение

Собрать рекламную воронку WB: от показов и кликов до корзин, заказов, расходов и эффективности. РнП должен объяснять, что происходит в верхней части воронки и как это связано с ценами, маржой и действиями менеджеров.

## 2. Роли

- Мария: смотрит эффективность рекламы и риск по SKU/менеджерам.
- Менеджеры рекламы: анализируют кампании и кандидатов на проверку.
- Максим: смотрит влияние расходов на P&L.
- `finance_viewer`: видит связку расходов и маржи.

## 3. Пользовательские сценарии

- Открыть РнП за период и увидеть воронку по дням/неделям.
- Отфильтровать по менеджеру, SKU, бренду, категории, кампании.
- Раскрыть показы по статусам кампаний.
- Посмотреть кампании справа и открыть detail drawer/modal.
- Увидеть review candidates: высокий ДРР, слабая корзина, расход без заказов.
- Перейти из РнП в SKU drawer или price/repricer decision.

## 4. Данные

- campaign id/name/type/status;
- SKU/nmId/internal SKU;
- бренд, категория, менеджер;
- period grain;
- impressions;
- card views / переходы в карточку;
- ad clicks;
- CTR;
- add to cart;
- ATCR;
- orders count/rub;
- OCR;
- CR clicks -> order;
- CR carts -> order;
- ad spend;
- CPC;
- CPO;
- ad orders count/rub;
- ACoO;
- TACoO;
- CPM;
- attribution type: exact, allocated, campaign_only.

## 5. Поля, фильтры и контролы

- период;
- детализация: день/неделя/месяц, если доступно;
- тип кампании;
- статус кампании;
- кампания;
- кабинет;
- бренд;
- категория;
- менеджер;
- SKU/артикул;
- ID склейки товара;
- expand rows;
- campaign detail;
- export.

## 6. Расчеты и бизнес-правила

- CTR = clicks / impressions.
- ATCR = carts / card views или carts / clicks, если так подтвердит Мария.
- OCR = orders / carts или orders / visits, требуется точная формула.
- CR clicks -> order = orders / clicks.
- CR carts -> order = orders / carts.
- CPC = spend / clicks.
- CPO = spend / orders.
- ACoO/TACoO требуют подтвержденных формул.
- Если атрибуция только `campaign_only`, не распределять расход в SKU P&L и не создавать SKU stop-action.
- Рекомендации по рекламе в v1 только `review_candidate`, без автоотключения.

## 7. Состояния

| State | Поведение |
|---|---|
| `loading` | Skeleton матрицы и campaign list |
| `empty` | Нет кампаний/расходов за период |
| `partial_data` | Есть расходы, но нет SKU attribution |
| `ads_attribution_weak` | Только campaign_only |
| `mapping_missing` | Нет source mapping |
| `no_access` | Скрыть финансовые расходы |
| `campaign_detail_missing` | Кампания есть, detail недоступен |

## 8. Опасные действия

В v1 нет автоотключения рекламы. Опасные действия:

- массовая смена статуса кампаний, если появится в будущем;
- ручное распределение расходов;
- изменение формулы ACoO/TACoO;
- export рекламных расходов без права.

## 9. Что уже есть в Vella

- упрощенный report UI;
- связка РнП с репрайсером концептуально;
- review-candidate подход для рекламы.

## 10. Что нужно доделать

- ads source mapping;
- RnP funnel table;
- expand rows;
- campaign list;
- campaign detail drawer/modal;
- attribution states;
- drill-down to SKU.

## 11. v1 replacement minimum

- воронка: показы, клики/переходы, корзины, заказы, расходы;
- CTR, ATCR, CR, CPC, CPO, ДРР/ROI где подтверждено;
- фильтры SKU/менеджер/период;
- campaign status breakdown;
- review candidates без auto-stop.

## 12. Production hardening

- campaign detail parity;
- all-time vs selected-period metrics;
- charts of spend dynamics;
- smarter alerts after 2-3 недели высокого ДРР;
- attribution quality report.

## 13. P2 / change request

- полная INDEEPA campaign detail parity;
- автоматическое управление рекламой;
- сложная SKU attribution, если WB не дает прямой источник;
- все горизонтальные daily matrices как в INDEEPA.

## 14. Сложность

Базовый РнП v1: 6-10 рабочих дней. Campaign detail parity: еще 3-5 дней.

## 15. Открытые вопросы

- Какие WB Ads endpoints/exports доступны?
- Как считать ATCR, OCR, ACoO, TACoO в клиентской логике?
- Можно ли получить расход per-SKU/per-period?
- Какие пороги ДРР/ROI считать review candidates?
- Нужно ли показывать рекламные кампании без привязки к SKU?


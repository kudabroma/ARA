# Архитектура ARATax

## 1. Обзор

ARATax принимает данные о визах и пребывании в США, доходах и расходах, рассчитывает налоговое резидентство и ориентировочные федеральные налоги, показывает возможные вычеты/FICA-возврат и формирует PDF Form 8843. Основные расчёты выполняются Python-кодом; LLM используется для текстового объяснения и диалога, но не для налоговой арифметики.

```mermaid
flowchart LR
  U[Пользователь] --> FE[Frontend: TanStack Start + React]
  FE -->|HTTP JSON /api/*| BE[Backend: FastAPI на Vercel]
  BE -->|prompt, если настроен ключ| LLM[LLM-провайдер]
  LLM --> BE
  BE -->|JSON или PDF| FE
```

## 2. Бэкенд

### Запуск и маршрутизация

- Точка входа Vercel — [api/index.py](./api/index.py#L1): добавляет корень проекта в `sys.path` и экспортирует `app` из [app/main.py](./app/main.py#L28).
- Файла `vercel.json` в корне сейчас нет. Поэтому rewrite `/(.*) -> /api/index` отсутствует; маршрутизацию `/api/*` при деплое из корня нужно отдельно проверить/настроить в Vercel.
- FastAPI объявляет CORS с `allow_origins=["*"]`, `allow_credentials=False`, любыми методами и заголовками: [app/main.py](./app/main.py#L30). Frontend не отправляет cookies.

### HTTP API

Запросы/ответы — JSON, кроме PDF-ответа. Полные Pydantic-модели находятся в [app/schemas.py](./app/schemas.py#L17).

| Метод и путь | Назначение, основные входные поля | Основной ответ |
|---|---|---|
| `GET /`, `GET /api/health` | Проверка сервиса; тело запроса не нужно. | `status`, `service`, фиксированные сведения `subscription` и список endpoint-ов. |
| `GET /api/demo-presets` | Список встроенных демонстрационных сценариев. | `count`, `presets` с `title`, `subtitle`, `payload`. |
| `POST /api/residency/calculate` | `tax_year`, `stays[{visa_type,entry_date,exit_date}]`, `prior_exempt_calendar_years`, `has_green_card`, `country_of_citizenship`, `closer_connection_eligible`. | `ResidencyResponse`: статус, дни/веса, SPT, планы подачи, предупреждения и ссылки IRS. |
| `POST /api/taxes/calculate` | `tax_year`, `filing_status`, `residency_status`, `visa_type`, гражданство, `gross_1099_income`, вычеты, W-2/удержания, estimated payments. | `TaxCalculationResponse`: налог, SE tax, вычеты, удержания/FICA, баланс, квартальный график и разбивка по скобкам. |
| `POST /api/transactions/analyze` | `tax_year`, `transactions[{date,description,amount,type_hint}]` и/или `csv_text`; `marginal_tax_rate_estimate`, `use_ai`. | Итоги доходов/расходов, `category_summary`, список `transactions` с `classification`, категорией и суммами. |
| `POST /api/form-8843/pdf` | Поля `Form8843Request`: имя, адреса, виза, дни, паспорт и учебная программа/DSO. | Байты PDF (`application/pdf`, attachment). |
| `POST /api/form-8843/base64` | Тот же профиль Form 8843. | `filename`, `mime_type`, `size_bytes`, `pdf_base64`. |
| `POST /api/explain` | `language`, `residency_result`, `tax_result`, `user_question`. | `provider`, `language`, `explanation_markdown`, `disclaimer`. |
| `POST /api/chat` | `messages[{role,content}]`, `collected_profile`, `language`. | `reply`, профиль, `missing_fields`, `suggested_replies`, `live_calculation`. |
| `POST /api/analyze-all` | Обязательный `residency`; опциональные `taxes`, `transactions`, `form_8843_profile`, `language`. | `residency`, `transactions`, `taxes`, опциональный PDF в base64, `ai_explanation`, `subscription_active`. |

Маршруты объявлены в [app/main.py](./app/main.py#L39). `/api/analyze-all` и `/api/chat` преобразуют `ValueError` в HTTP 400; остальные расчётные маршруты также возвращают HTTP 400 при ошибке. Невалидный формат даты отклоняется Pydantic как HTTP 422.

### Модули и типы расчётов

- [app/services/residency.py](./app/services/residency.py#L45) нормализует визовые статусы, считает дни и тест существенного присутствия, учитывает исключения для студенческих/учёных виз и формирует план форм. Расчёт детерминированный.
- [app/services/taxes.py](./app/services/taxes.py#L44) считает прогрессивный федеральный налог, self-employment tax, вычеты, QBI, возможный FICA refund и estimated quarterly payments. Расчёт детерминированный.
- [app/services/transactions.py](./app/services/transactions.py#L14) разбирает CSV и классифицирует операции регулярными выражениями в `RULES`. Это правила, не AI: поле `use_ai` объявлено в схеме, но в реализации не читается. Неизвестные описания попадают в `PERSONAL`.
- [app/services/pdf_8843.py](./app/services/pdf_8843.py#L17) строит PDF с ReportLab; при отсутствии ReportLab использует упрощённый PDF fallback.
- [app/services/advisor.py](./app/services/advisor.py#L90) обращается к LLM для текстового объяснения/ответа чата; профиль и результаты также предварительно обрабатываются локальными функциями residency/taxes. Список провайдеров и fallback находятся здесь же.
- [app/schemas.py](./app/schemas.py#L17) содержит входные/выходные Pydantic-модели; `VisaStay.exit_date` допускает отсутствие значения, которое сервис считает как 31 декабря налогового года. Поля `entry_date` и `exit_date` проверяются на формат `YYYY-MM-DD`.
- [app/presets.py](./app/presets.py#L3) — 3 жёстко заданных демонстрационных payload. Персональные defaults модели Form 8843 пустые; данные демо-профилей находятся в presets.
- [app/config.py](./app/config.py#L1) содержит визовые группы и `TAX_YEARS`: ставки/скобки, standard deduction, Social Security wage base, квартальные и годовые сроки. Данные заданы только для 2025 и 2026; неизвестный год сервисы подменяют на 2025.

### Переменные окружения и AI fallback

В [`.env.example`](./.env.example#L1) перечислены пустые ключи. Ключи не обязательны для запуска API или детерминированных расчётов; каждый нужен лишь как необязательный вариант LLM-провайдера.

| Переменная | Назначение | Обязательна |
|---|---|---|
| `OPENROUTER_API_KEY` | Ключ OpenRouter, первый проверяемый провайдер. | Нет |
| `OPENAI_API_KEY` | Ключ OpenAI, следующий провайдер. | Нет |
| `DEEPSEEK_API_KEY` | Ключ DeepSeek. | Нет |
| `GROQ_API_KEY` | Ключ Groq. | Нет |
| `GEMINI_API_KEY` | Ключ Gemini, проверяется после OpenAI-совместимых API. | Нет |
| `OPENROUTER_MODEL` | Переопределение модели OpenRouter; в `.env.example` не указан. | Нет |
| `OPENAI_MODEL` | Переопределение модели OpenAI; в `.env.example` не указан. | Нет |

При отсутствии всех рабочих ключей `call_llm` возвращает `deterministic-irs-explainer`: локальный шаблон формирует объяснение на английском или русском и шаблонные реплики чата. Меняются текст `explanation_markdown`/`reply` и `provider`; налоговые и residency-цифры от этого не меняются. Для `es` backend-перевода нет: фронтенд отправляет `en`. Обработка ошибок провайдеров в [app/services/advisor.py](./app/services/advisor.py#L75) также переходит к следующему провайдеру или локальному ответу.

### Тесты

[tests/test_api.py](./tests/test_api.py#L1) покрывает health/presets, интеграционный `analyze-all`, chat и правила дат; frontend-тесты проверяют маппинг Form 8843. Команда из корня backend: `python -m pytest`.

## 3. Фронтенд (`Frontend/`)

### Стек, конфигурация и страницы

- Зависимости по [Frontend/package.json](./Frontend/package.json#L45): TanStack Router `1.170.41`, TanStack Start `1.168.60`, React/React DOM `^19.2.0`, Vite `8.1.5`, TypeScript `^5.8.3`. Скрипты: `dev` — `vite dev`, `build` — `vite build`, `preview` — `vite preview`, `lint` — `eslint .`, `test` — `vitest run` ([package.json](./Frontend/package.json#L7)).
- Файловые маршруты: `/` — workspace с формой, результатами, чатом и документами ([src/routes/index.tsx](./Frontend/src/routes/index.tsx#L7)); `/pricing` — планы ([pricing.tsx](./Frontend/src/routes/pricing.tsx#L3)); `/checkout` — локальная тестовая форма ([checkout.tsx](./Frontend/src/routes/checkout.tsx#L3)); `/success` — подтверждение Pro ([success.tsx](./Frontend/src/routes/success.tsx#L3)). Shell/общий layout задаёт [src/routes/__root.tsx](./Frontend/src/routes/__root.tsx#L11).
- URL API задаётся `VITE_API_URL`; `BASE_URL` удаляет завершающий `/`, а `backendConfigured()` истинен только при непустом адресе: [Frontend/src/lib/ara/api.ts](./Frontend/src/lib/ara/api.ts#L1). В `Frontend/.env.local` указан `https://ara-api-orpin.vercel.app`; `.env.local` игнорируется правилом `*.local`.
- API-вызовы фронтенда: `/api/demo-presets` и `/api/analyze-all` из [calculation.tsx](./Frontend/src/components/ara/calculation.tsx#L113); `/api/chat` и `/api/analyze-all` из [chat.tsx](./Frontend/src/components/ara/chat.tsx#L27). Отдельные residency, taxes, transactions и Form PDF endpoints напрямую фронтендом не вызываются.

### Paywall, i18n и данные

- `plan` хранится в React state и меняется на `pro` после прохождения локальной тестовой формы; состояние действует только до перезагрузки/закрытия вкладки ([provider.tsx](./Frontend/src/components/ara/provider.tsx#L8), [plans.tsx](./Frontend/src/components/ara/plans.tsx#L53)). Ограничения Free/Pro работают только в UI; backend не проверяет план.
- Stripe не подключён. Checkout проверяет email, Luhn, срок карты и CVC в браузере, ничего не отправляет и не сохраняет; это демонстрация разблокировки, а не платёж.
- Словари EN/RU/ES находятся в [Frontend/src/lib/ara/i18n.ts](./Frontend/src/lib/ara/i18n.ts#L2), [RU](./Frontend/src/lib/ara/i18n.ts#L187), [ES](./Frontend/src/lib/ara/i18n.ts#L374). Язык хранится в `localStorage` только для настройки интерфейса ([provider.tsx](./Frontend/src/components/ara/provider.tsx#L17)). `backendLanguage()` сохраняет `ru`, а `en` и `es` преобразует в `en` ([api.ts](./Frontend/src/lib/ara/api.ts#L4)).
- Введённые данные/результаты хранятся в React state на время сессии; отдельного backend-хранилища в коде не найдено. Выбранный язык сохраняется в `localStorage`.

### Контракт фронтенда и backend

- Frontend вызывает `demo-presets`, `analyze-all` и `chat`. Поля результатов, транзакций (`classification`, `schedule_c_category`, top-level totals, `category_summary`) и live-оценки чата читаются по контракту backend. Для Form 8843 `buildBody()` преобразует UI-поля в `Form8843Request`; профиль без имени не отправляется ([Frontend/src/lib/ara/api.ts](./Frontend/src/lib/ara/api.ts#L102), [app/schemas.py](./app/schemas.py#L184)).
- Для FICA frontend показывает статичную инструкцию Form 843/8316 из локализаций: суммы ответа backend не подменяются и не выдумываются ([Frontend/src/components/ara/results.tsx](./Frontend/src/components/ara/results.tsx#L256), [Frontend/src/lib/ara/i18n.ts](./Frontend/src/lib/ara/i18n.ts#L96)).
- При пустом `exit_date` backend использует 31 декабря налогового года; неверный формат отклоняется валидатором ([app/services/residency.py](./app/services/residency.py#L57), [app/schemas.py](./app/schemas.py#L24)).

### Lovable и влияние при деплое

- [Frontend/vite.config.ts](./Frontend/vite.config.ts#L1) использует `@lovable.dev/vite-tanstack-config`; комментарий к конфигу указывает на Nitro с Cloudflare как default target и добавляемые конфигурацией плагины/env injection.
- [Frontend/src/routes/__root.tsx](./Frontend/src/routes/__root.tsx#L14) вызывает Lovable error reporting, а [src/lib/lovable-error-reporting.ts](./Frontend/src/lib/lovable-error-reporting.ts#L8) отправляет события только через `window.__lovableEvents`/`window.__lovableReportRuntimeError`. Вне Lovable эти глобальные хуки в репозитории не определены, поэтому внешняя телеметрия может быть неактивна.
- [Frontend/src/server.ts](./Frontend/src/server.ts#L1) — SSR-обёртка, которая нормализует ошибки TanStack/Nitro; её наличие и Cloudflare-target важны для совместимости хостинга.

## 4. Деплой

### Backend на Vercel

1. Создать Vercel-проект с Root Directory = корень backend (каталог с `api/`, `app/`, `requirements.txt`).
2. Оставить Python entrypoint [api/index.py](./api/index.py#L1). Корневой `vercel.json` намеренно отсутствует, поэтому до деплоя нужно проверить и настроить Vercel routing для `/api/*`; фактическая конфигурация проекта не хранится в репозитории.
3. Добавить в Environment Variables один или несколько ключей LLM-провайдеров из таблицы выше только если нужны реальные AI-тексты. Без них API и расчёты работают с deterministic fallback.

### Frontend

1. Создать отдельный проект, Root Directory = `Frontend`; build script — `npm run build` (или соответствующий установленному lockfile package manager), development — `npm run dev`.
2. Задать `VITE_API_URL` как URL backend (локальный шаблон описан в `Frontend/.env.example`; production URL указан в `.env.local`, который не коммитится).
3. Текущий Vite wrapper настроен на Nitro Cloudflare по умолчанию, а не явно на Vercel. Для Vercel SSR возможен конфликт формата/target server bundle; проверьте адаптер/target и deployment output, либо используйте совместимый с Cloudflare хостинг. Скрипта `deploy` в `package.json` нет.
4. Корневого `vercel.json` нет; фронтенд-проект с Root Directory = `Frontend` не должен зависеть от backend routing. Если backend и frontend деплоятся как отдельные проекты, настройка маршрутов одного проекта не должна попадать в другой.

## 5. Риски и проблемы

### Критично

1. **Vercel-маршрутизация backend не задана в репозитории.** Корневой `vercel.json` отсутствует; проверить, что задеплоенный проект маршрутизирует `/api/*` в `api/index.py`, иначе frontend не сможет обратиться к API. Настроить маршрутизацию в Vercel без смешивания с отдельным frontend-проектом.

### Важно

1. **Checkout не является оплатой или авторизацией.** Тестовый checkout меняет только клиентский React state; backend не подтверждает план, а ответы содержат `subscription_active: true` независимо от оплаты. Не представлять Pro как реально оплаченный; для production нужны платежный провайдер и серверная проверка прав: [Frontend/src/components/ara/provider.tsx](./Frontend/src/components/ara/provider.tsx#L8), [Frontend/src/components/ara/plans.tsx](./Frontend/src/components/ara/plans.tsx#L53), [app/main.py](./app/main.py#L189).
2. **CORS разрешает любой origin.** `allow_credentials=False` исключает cookies, но `allow_origins=["*"]` всё равно доступен любому сайту; заменить на список frontend-origin перед production: [app/main.py](./app/main.py#L30).
3. **LLM получает текст запроса и профиль/расчёт.** В prompt чата могут попадать `collected_profile`, результаты residency/tax и сообщения пользователя; сообщить о передаче данных и не включать ненужные персональные сведения: [app/services/advisor.py](./app/services/advisor.py#L356).
4. **Классификация транзакций — эвристики, не AI и не гарантия вычета.** `use_ai` не меняет поведение, неизвестные описания считаются `PERSONAL`; пользователь должен проверять предварительные категории: [app/schemas.py](./app/schemas.py#L93), [app/services/transactions.py](./app/services/transactions.py#L14).
5. **Год вне таблицы молча считается 2025.** Это может выдать результат другого налогового года без ошибки; валидировать поддерживаемые годы или возвращать явную ошибку: [app/services/residency.py](./app/services/residency.py#L45), [app/services/taxes.py](./app/services/taxes.py#L45).

### Мелочь / проверка перед релизом

1. **Демонстрационные сценарии содержат фиксированные входные данные.** Backend отдаёт три примера, а во frontend есть sample CSV; это demo-входы, а не подмена вычисленных результатов. Явно помечать их как демонстрационные: [app/presets.py](./app/presets.py#L3), [Frontend/src/components/ara/calculation.tsx](./Frontend/src/components/ara/calculation.tsx#L399).
2. **Frontend target для Vercel не подтверждён.** Конфиг указывает Cloudflare default; проверить SSR runtime/output перед релизом на Vercel: [Frontend/vite.config.ts](./Frontend/vite.config.ts#L1).
3. **Проверить правила ignore перед публикацией.** Backend `.gitignore` игнорирует `.env`, `.venv`, `__pycache__`; Frontend дополнительно игнорирует `node_modules`, `dist` и `*.local`. Шаблон `.env.production` явно не игнорируется — не хранить в нём секреты: [Frontend/.gitignore](./Frontend/.gitignore#L1), [`.gitignore`](./.gitignore#L1).

**Фейковые результаты:** основные суммы рассчитываются backend-кодом; обнаружены только фиксированные demo-входы. Form 8843 defaults очищены, а UI-результаты приведены к схеме backend.

## 6. Чек-лист перед демо

- [ ] Настроить routing backend-проекта Vercel для `/api/*`, задеплоить из корня и проверить `/api/health`.
- [ ] Задать `VITE_API_URL` во frontend; проверить CORS с домена фронтенда.
- [ ] Прогнать реальный пользовательский сценарий: residency, налог, транзакции, Form 8843; проверить поля результата и PDF на персональных данных, а не defaults.
- [ ] Проверить сценарий без LLM-ключей и с ключом: deterministic fallback должен работать.
- [ ] Проверить пустую дату выезда и ответы 422/400 для неверных дат.
- [ ] Проверить frontend build/deploy на выбранном хостинге (Cloudflare или Vercel) и прямое открытие `/pricing`, `/checkout`, `/success`.
- [ ] Не демонстрировать тестовый Pro checkout как оплату: Stripe/серверная проверка платежа отсутствуют.
- [ ] До показа заменить demo-пресеты на явно помеченные примеры и не представлять их значения как реальные данные клиента.

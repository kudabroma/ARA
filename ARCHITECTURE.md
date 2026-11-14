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

Фронтенд сейчас содержит placeholder для URL API — фактический HTTP-вызов не заработает до его замены: [Frontend/src/lib/ara/api.ts](./Frontend/src/lib/ara/api.ts#L1).

## 2. Бэкенд

### Запуск и маршрутизация

- Точка входа Vercel — [api/index.py](./api/index.py#L1): добавляет корень проекта в `sys.path` и экспортирует `app` из [app/main.py](./app/main.py#L28).
- [vercel.json](./vercel.json#L1) перенаправляет каждый путь `/(.*)` на `/api/index`. Это catch-all, включая `/`; FastAPI затем выбирает маршрут по исходному HTTP-пути.
- FastAPI объявляет CORS с `allow_origins=["*"]`, `allow_credentials=True`, любыми методами и заголовками: [app/main.py](./app/main.py#L30). Браузер не разрешает credentialed CORS с wildcard origin в стандартном режиме; клиентские запросы сейчас не задают `credentials`.

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

Маршруты объявлены в [app/main.py](./app/main.py#L39). Только отдельные residency/tax/transaction обработчики оборачивают ошибки в HTTP 400; `/api/analyze-all` и `/api/chat` такого перехвата не имеют.

### Модули и типы расчётов

- [app/services/residency.py](./app/services/residency.py#L45) нормализует визовые статусы, считает дни и тест существенного присутствия, учитывает исключения для студенческих/учёных виз и формирует план форм. Расчёт детерминированный.
- [app/services/taxes.py](./app/services/taxes.py#L44) считает прогрессивный федеральный налог, self-employment tax, вычеты, QBI, возможный FICA refund и estimated quarterly payments. Расчёт детерминированный.
- [app/services/transactions.py](./app/services/transactions.py#L14) разбирает CSV и классифицирует операции регулярными выражениями в `RULES`. Это правила, не AI: поле `use_ai` объявлено в схеме, но в реализации не читается. Неизвестные описания попадают в `PERSONAL`.
- [app/services/pdf_8843.py](./app/services/pdf_8843.py#L17) строит PDF с ReportLab; при отсутствии ReportLab использует упрощённый PDF fallback.
- [app/services/advisor.py](./app/services/advisor.py#L90) обращается к LLM для текстового объяснения/ответа чата; профиль и результаты также предварительно обрабатываются локальными функциями residency/taxes. Список провайдеров и fallback находятся здесь же.
- [app/schemas.py](./app/schemas.py#L17) содержит входные/выходные Pydantic-модели; [app/presets.py](./app/presets.py#L3) — 3 жёстко заданных демонстрационных payload.
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

[tests/test_api.py](./tests/test_api.py#L1) покрывает health и число presets, интеграционный `analyze-all` на первом preset (статус, ожидаемый FICA refund и сигнатура PDF), а также два шага chat-профиля. Тесты не запускались по требованию. Команда из корня backend: `python -m pytest`.

## 3. Фронтенд (`Frontend/`)

### Стек, конфигурация и страницы

- Зависимости по [Frontend/package.json](./Frontend/package.json#L45): TanStack Router `1.170.41`, TanStack Start `1.168.60`, React/React DOM `^19.2.0`, Vite `8.1.5`, TypeScript `^5.8.3`. Скрипты: `dev` — `vite dev`, `build` — `vite build`, `preview` — `vite preview`, `lint` — `eslint .`, `test` — `vitest run` ([package.json](./Frontend/package.json#L7)).
- Файловые маршруты: `/` — workspace с формой, результатами, чатом и документами ([src/routes/index.tsx](./Frontend/src/routes/index.tsx#L7)); `/pricing` — планы ([pricing.tsx](./Frontend/src/routes/pricing.tsx#L3)); `/checkout` — заглушка оплаты ([checkout.tsx](./Frontend/src/routes/checkout.tsx#L3)); `/success` — экран «оплата не выполнена» ([success.tsx](./Frontend/src/routes/success.tsx#L3)). Shell/общий layout задаёт [src/routes/__root.tsx](./Frontend/src/routes/__root.tsx#L11).
- URL API не берётся из `VITE_API_URL`: `BASE_URL` захардкожен в [Frontend/src/lib/ara/api.ts](./Frontend/src/lib/ara/api.ts#L1) как `https://YOUR-VERCEL-BACKEND.vercel.app`. При placeholder `backendConfigured()` возвращает false, а `request()` бросает `not_connected`.
- API-вызовы фронтенда: `/api/demo-presets` и `/api/analyze-all` из [calculation.tsx](./Frontend/src/components/ara/calculation.tsx#L113); `/api/chat` и `/api/analyze-all` из [chat.tsx](./Frontend/src/components/ara/chat.tsx#L27). Отдельные residency, taxes, transactions и Form PDF endpoints напрямую фронтендом не вызываются.

### Paywall, i18n и данные

- Состояние `plan` не загружается с сервера/платёжной системы, а всегда задаётся как `"free"` в [provider.tsx](./Frontend/src/components/ara/provider.tsx#L35). Free/Pro-ограничения работают только в React UI: блокировки результатов/документов и лимит 5 сообщений; серверной авторизации/проверки плана нет ([api.ts](./Frontend/src/lib/ara/api.ts#L5), [results.tsx](./Frontend/src/components/ara/results.tsx#L14)).
- Stripe не подключён: Stripe SDK/серверного payment endpoint нет; checkout сообщает об отключённых платежах и кнопка disabled ([plans.tsx](./Frontend/src/components/ara/plans.tsx#L69)).
- Словари EN/RU/ES находятся в [Frontend/src/lib/ara/i18n.ts](./Frontend/src/lib/ara/i18n.ts#L2), [RU](./Frontend/src/lib/ara/i18n.ts#L187), [ES](./Frontend/src/lib/ara/i18n.ts#L374). Язык хранится в `localStorage` только для настройки интерфейса ([provider.tsx](./Frontend/src/components/ara/provider.tsx#L17)). `backendLanguage()` сохраняет `ru`, а `en` и `es` преобразует в `en` ([api.ts](./Frontend/src/lib/ara/api.ts#L4)).
- Введённые данные/результаты хранятся в React state на время сессии; отдельного backend-хранилища в коде не найдено. Выбранный язык сохраняется в `localStorage`.

### Контракт фронтенда и backend

- Frontend вызывает только `demo-presets`, `analyze-all` и `chat`, перечисленные выше. `/api/analyze-all` возвращает реальный результат backend, но представление ряда полей не совпадает с контрактом: UI просит `net_1099_income`, `standard_deduction`, `qbi_deduction`, `money_saved_by_deductions`, тогда как backend возвращает `net_self_employment_income`, `standard_deduction_applied`, `qbi_deduction_applied`, `Deduction_tax_savings_usd`. Несколько строк breakdown поэтому показывают `—` ([results.tsx](./Frontend/src/components/ara/results.tsx#L92), [app/schemas.py](./app/schemas.py#L130)).
- Backend выдаёт транзакции с `classification`, `category_summary` и totals на верхнем уровне, а экран читает `t.category` и `transactions.totals`; поле категории будет пустым, totals не будут показаны ([results.tsx](./Frontend/src/components/ara/results.tsx#L100), [app/schemas.py](./app/schemas.py#L80)).
- Экран также читает `erroneous_fica_next_steps`, которого нет в ответе backend ([results.tsx](./Frontend/src/components/ara/results.tsx#L246)).
- Chat API кладёт расчёт в `live_calculation.taxes.net_tax_owed_or_refund`, UI читает `live_calculation.net_tax_owed_or_refund`; live estimate останется пустым ([advisor.py](./app/services/advisor.py#L418), [chat.tsx](./Frontend/src/components/ara/chat.tsx#L206)).
- Профиль Form 8843 на фронтенде содержит `name`, `home_address`, `passport_country`, `days_present_current`, `days_excluded` и другие UI-ключи ([calculation.tsx](./Frontend/src/components/ara/calculation.tsx#L42)), а backend ждёт `first_name`, `home_country_address`, `country_of_passport`, `days_present_current_year`, `days_excluded_current_year` ([app/schemas.py](./app/schemas.py#L169)). `buildBody()` передаёт объект без преобразования; лишние поля Pydantic по умолчанию игнорирует, поэтому PDF может использовать demo-default значения вместо данных пользователя ([api.ts](./Frontend/src/lib/ara/api.ts#L122)).
- `VisaStay.exit_date` обязателен как строка на backend, но UI объявляет его необязательным и при пустом поле отправляет `null`: запрос с таким пребыванием получает ошибку валидации 422 ([app/schemas.py](./app/schemas.py#L17), [api.ts](./Frontend/src/lib/ara/api.ts#L90)).

### Lovable и влияние при деплое

- [Frontend/vite.config.ts](./Frontend/vite.config.ts#L1) использует `@lovable.dev/vite-tanstack-config`; комментарий к конфигу указывает на Nitro с Cloudflare как default target и добавляемые конфигурацией плагины/env injection.
- [Frontend/src/routes/__root.tsx](./Frontend/src/routes/__root.tsx#L14) вызывает Lovable error reporting, а [src/lib/lovable-error-reporting.ts](./Frontend/src/lib/lovable-error-reporting.ts#L8) отправляет события только через `window.__lovableEvents`/`window.__lovableReportRuntimeError`. Вне Lovable эти глобальные хуки в репозитории не определены, поэтому внешняя телеметрия может быть неактивна.
- [Frontend/src/server.ts](./Frontend/src/server.ts#L1) — SSR-обёртка, которая нормализует ошибки TanStack/Nitro; её наличие и Cloudflare-target важны для совместимости хостинга.

## 4. Деплой

### Backend на Vercel

1. Создать Vercel-проект с Root Directory = корень репозитория (каталог, где находятся `vercel.json`, `api/`, `app/`, `requirements.txt`).
2. Оставить Python entrypoint `api/index.py` и rewrite из [vercel.json](./vercel.json#L1).
3. Добавить в Environment Variables один или несколько ключей LLM-провайдеров из таблицы выше только если нужны реальные AI-тексты. Без них API и расчёты работают с deterministic fallback.

### Frontend

1. Создать отдельный проект, Root Directory = `Frontend`; build script — `npm run build` (или соответствующий установленному lockfile package manager), development — `npm run dev`.
2. Перед использованием заменить placeholder `BASE_URL` на домен backend. Переменной `VITE_API_URL` код не читает; переменных frontend, обязательных по текущему коду, не найдено.
3. Текущий Vite wrapper настроен на Nitro Cloudflare по умолчанию, а не явно на Vercel. Для Vercel SSR возможен конфликт формата/target server bundle; проверьте адаптер/target и deployment output, либо используйте совместимый с Cloudflare хостинг. Скрипта `deploy` в `package.json` нет.
4. Корневой rewrite `/(.*) -> /api/index` относится к Vercel-проекту, чей Root Directory — корень репозитория. При отдельном проекте с Root Directory = `Frontend` этот родительский `vercel.json` обычно не является его конфигом; проверьте scope/настройки проекта Vercel, чтобы не направить frontend-маршруты на FastAPI.

## 5. Риски и проблемы

### Критично

1. **Frontend не подключён к backend.** `BASE_URL` — буквальный placeholder, поэтому `backendConfigured()` выключает presets, а запросы завершаются `not_connected`. Заменить на реальный адрес API или внедрить сборочную конфигурацию URL: [Frontend/src/lib/ara/api.ts](./Frontend/src/lib/ara/api.ts#L1).
2. **Form 8843 может содержать не данные пользователя.** UI и API используют разные имена полей профиля; backend игнорирует незнакомые ключи и подставляет defaults вроде Ali Abylgazy / Stanford. Согласовать DTO/маппинг и убрать персонально выглядящие defaults: [Frontend/src/components/ara/calculation.tsx](./Frontend/src/components/ara/calculation.tsx#L42), [Frontend/src/lib/ara/api.ts](./Frontend/src/lib/ara/api.ts#L122), [app/schemas.py](./app/schemas.py#L169).

### Важно

1. **Результаты частично отображаются пустыми/неверными.** Несовпадают ключи налоговых полей, transaction `category` vs `classification`, totals и FICA next steps; привести UI к схеме backend либо согласовать контракт: [Frontend/src/components/ara/results.tsx](./Frontend/src/components/ara/results.tsx#L92), [app/schemas.py](./app/schemas.py#L80).
2. **Пустая дата выезда приводит к 422.** Форма разрешает оставить поле пустым, но отправляет `null`, а модель требует строку. Согласовать nullable-модель/поведение формы: [Frontend/src/components/ara/calculation.tsx](./Frontend/src/components/ara/calculation.tsx#L279), [Frontend/src/lib/ara/api.ts](./Frontend/src/lib/ara/api.ts#L90), [app/schemas.py](./app/schemas.py#L17).
3. **В некоторых путях некорректная дата превращается в 500.** `parse_iso_date()` вызывает `datetime.strptime`; `/api/analyze-all` и `/api/chat` не перехватывают ошибку парсинга, в отличие от отдельного residency endpoint. Добавить валидацию даты в schema или единое преобразование в 4xx: [app/services/residency.py](./app/services/residency.py#L36), [app/main.py](./app/main.py#L129).
4. **Paywall не является оплатой/авторизацией.** Frontend всегда хранит `plan: "free"`, checkout disabled, при этом backend сообщает `subscription_active: true` и health — активный Pro tier. Не использовать эти UI/health-флаги как доказательство оплаты; подключить серверную верификацию платежа и права доступа: [provider.tsx](./Frontend/src/components/ara/provider.tsx#L35), [plans.tsx](./Frontend/src/components/ara/plans.tsx#L87), [app/main.py](./app/main.py#L43), [app/main.py](./app/main.py#L134).
5. **CORS слишком широк для пользовательских финансовых данных.** `*` вместе с credentials создаёт некорректную credentialed-конфигурацию и не ограничивает origin. Задать список реальных frontend-origin и включать credentials только при необходимости: [app/main.py](./app/main.py#L30).
6. **LLM получает текст запроса и профиль/расчёт.** В chat prompt сериализуются `collected_profile`, residency/tax результаты и последнее сообщение; не передавать секреты/лишние персональные сведения и явно сообщить пользователю об обработке провайдером: [app/services/advisor.py](./app/services/advisor.py#L356).
7. **Классификация транзакций — эвристики, не AI и не гарантия вычета.** `use_ai` не меняет поведение, неизвестные описания считаются `PERSONAL`; правила содержат фиксированные проценты deductible. Обозначить результат как предварительную классификацию и дать проверку пользователю: [app/schemas.py](./app/schemas.py#L93), [app/services/transactions.py](./app/services/transactions.py#L14).
8. **Год вне таблицы молча считается 2025.** Это может выдать результат другого налогового года без ошибки; валидировать поддерживаемые годы или возвращать явную ошибку: [app/services/residency.py](./app/services/residency.py#L45), [app/services/taxes.py](./app/services/taxes.py#L45).

### Мелочь / проверка перед релизом

1. **Демонстрационные сценарии захардкожены.** Backend отдаёт три заполненных примера, в том числе вымышленные личные данные/суммы; sample CSV также встроен во frontend. Это входные demo-данные, а не подмена вычисленного результата; явно отделять их от пользовательских данных и не показывать как реальные кейсы: [app/presets.py](./app/presets.py#L3), [Frontend/src/components/ara/calculation.tsx](./Frontend/src/components/ara/calculation.tsx#L399).
2. **AI-классификация может восприниматься как доступная, но отсутствует.** Поле `use_ai=True` присутствует в API-контракте, однако обработчик его игнорирует: [app/schemas.py](./app/schemas.py#L98), [app/services/transactions.py](./app/services/transactions.py#L106).
3. **Проверить ignore-файлы.** Backend `.gitignore` игнорирует `.env`, `.venv`, `__pycache__`, но не содержит `node_modules`/`dist`; frontend игнорирует их в собственном [Frontend/.gitignore](./Frontend/.gitignore#L1). `.env.example` содержит только пустые строки ключей. Корневой шаблон `.env` не покрывает все варианты вроде `.env.production` — не добавлять туда секреты: [`.gitignore`](./.gitignore#L1).
4. **Frontend Vercel-target не подтверждён конфигом.** Конфиг указывает Cloudflare default; проверить SSR runtime/output перед релизом на Vercel: [Frontend/vite.config.ts](./Frontend/vite.config.ts#L1).

**Фейковые результаты:** детерминированные расчёты действительно запускаются в backend; обнаружены захардкоженные demo-входы и Form 8843 defaults, которые из-за несовпадения ключей могут попасть в документ. Иных мест, где экран напрямую подменяет рассчитанный результат готовой фиктивной суммой, не найдено.

## 6. Чек-лист перед демо

- [ ] Развернуть backend на Vercel из корня и проверить `/api/health`.
- [ ] Установить реальный backend URL во frontend; проверить CORS с домена фронтенда.
- [ ] Прогнать реальный пользовательский сценарий: residency, налог, транзакции, Form 8843; проверить поля результата и PDF на персональных данных, а не defaults.
- [ ] Проверить сценарий без LLM-ключей и с ключом: deterministic fallback должен работать.
- [ ] Исправить контракт дат и проверить все даты, которые пользователь может оставить пустыми.
- [ ] Проверить frontend build/deploy на выбранном хостинге (Cloudflare или Vercel) и прямое открытие `/pricing`, `/checkout`, `/success`.
- [ ] Не демонстрировать Pro как оплаченную функцию: Stripe/серверная проверка платежа отсутствуют.
- [ ] До показа заменить demo-пресеты на явно помеченные примеры и не представлять их значения как реальные данные клиента.

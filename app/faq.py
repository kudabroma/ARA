"""Small multilingual FAQ used by the chat when no LLM is available.

Answers never invent numbers or dates: deadlines and amounts are filled in from
app.config.TAX_YEARS for the user's tax year; otherwise the text stays general.
"""

import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from app.config import TAX_YEARS

_MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"],
    "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
}


def format_date(language: str, iso: str) -> str:
    d = date.fromisoformat(iso)
    month = _MONTHS[language][d.month - 1]
    if language == "ru":
        return f"{d.day} {month} {d.year}"
    if language == "es":
        return f"{d.day} de {month} de {d.year}"
    return f"{month} {d.day}, {d.year}"


def _year_facts(language: str, tax_year: int) -> Dict[str, str]:
    cfg = TAX_YEARS.get(tax_year) or TAX_YEARS[max(TAX_YEARS)]
    joiner = {"en": ", ", "ru": ", ", "es": ", "}[language]
    return {
        "year": str(tax_year if tax_year in TAX_YEARS else max(TAX_YEARS)),
        "q_dates": joiner.join(format_date(language, q["due_date"]) for q in cfg["quarterly_deadlines"]),
        "annual": format_date(language, cfg["annual_deadline"]),
        "f8843": format_date(language, cfg["form_8843_deadline"]),
        "sd": f"${cfg['standard_deduction']['single']:,.0f}",
    }


# Each topic: keywords (lower-case substrings or regexes, any language) and answers per language.
FAQ: List[Dict[str, Any]] = [
    {
        "id": "pay",
        "keywords": [r"\bpay\b", "paying", "payment", "direct pay", "eftps", "заплатить", "оплатить", "платить", "оплат", "pagar", r"\bpago"],
        "answers": {
            "en": "You can pay online with **IRS Direct Pay** (irs.gov/payments) straight from a bank account, through **EFTPS**, or by card via IRS-approved processors. If you have 1099 income with no withholding, pay estimated tax each quarter with **Form 1040-ES** (due {q_dates}); any balance for {year} is due by {annual}.",
            "ru": "Платить можно онлайн через **IRS Direct Pay** (irs.gov/payments) прямо с банковского счёта, через **EFTPS** или картой через одобренных IRS операторов. Если есть доход по 1099 без удержаний, платите расчётный налог ежеквартально по **Form 1040-ES** (сроки: {q_dates}); остаток за {year} год нужно оплатить до {annual}.",
            "es": "Puedes pagar en línea con **IRS Direct Pay** (irs.gov/payments) desde tu cuenta bancaria, mediante **EFTPS** o con tarjeta a través de procesadores aprobados por el IRS. Si tienes ingresos 1099 sin retención, paga el impuesto estimado cada trimestre con el **Form 1040-ES** (vence {q_dates}); el saldo de {year} vence el {annual}.",
        },
    },
    {
        "id": "forms",
        "keywords": ["1040-nr", "1040nr", "1040 nr", "which form", "what form", "tax form do i need", "какая форма", "какую форму", "какой формой", "qué formulario", "que formulario", "cuál formulario"],
        "status_note": True,
        "answers": {
            "en": "**Form 1040** is the return for US citizens and resident aliens, who are taxed on worldwide income and can take the standard deduction. **Form 1040-NR** is for nonresident aliens: only US-source income is taxed and the standard deduction is generally not available. Which one you file depends on your residency status for the year (see IRS Publication 519).",
            "ru": "**Form 1040** — декларация для граждан и налоговых резидентов США: облагается общемировой доход, доступен стандартный вычет. **Form 1040-NR** — для нерезидентов: облагается только доход из источников в США, стандартный вычет обычно недоступен. Какую подавать, зависит от вашего налогового статуса за год (IRS Publication 519).",
            "es": "El **Form 1040** es la declaración para ciudadanos y residentes fiscales de EE. UU.: tributan por su renta mundial y pueden usar la deducción estándar. El **Form 1040-NR** es para no residentes: solo tributa la renta de fuente estadounidense y en general no hay deducción estándar. Cuál presentas depende de tu estatus de residencia del año (IRS Publication 519).",
        },
    },
    {
        "id": "residency",
        "keywords": ["resident", "substantial presence", r"\bspt\b", "резидент", "существенного присутствия", "residente", "presencia sustancial", "183 days", "183 дн", "183 días"],
        "status_note": True,
        "answers": {
            "en": "For tax purposes you are a **resident** if you have a green card or pass the **substantial presence test**: at least 31 days this year and 183 weighted days over 3 years (all days this year + 1/3 of last year + 1/6 of the year before). Days as an exempt individual (for example F-1/J-1 students in their first 5 calendar years) don't count. Otherwise you are a **nonresident**.",
            "ru": "Для налогов вы **резидент**, если у вас грин-карта или вы проходите **тест существенного присутствия**: не меньше 31 дня в этом году и 183 взвешенных дня за 3 года (все дни этого года + 1/3 прошлого + 1/6 позапрошлого). Дни «освобождённого лица» (например, студенты F-1/J-1 в первые 5 календарных лет) не учитываются. Иначе вы **нерезидент**.",
            "es": "A efectos fiscales eres **residente** si tienes green card o cumples la **prueba de presencia sustancial**: al menos 31 días este año y 183 días ponderados en 3 años (todos los días de este año + 1/3 del anterior + 1/6 del previo). Los días como persona exenta (por ejemplo, estudiantes F-1/J-1 en sus primeros 5 años calendario) no cuentan. Si no, eres **no residente**.",
        },
    },
    {
        "id": "visas",
        "keywords": ["f-1 vs", "opt vs", "h-1b vs", "f-1 and opt", "opt and h-1b", "f-1 or opt", "what is opt", "my visa", "which visa", "что такое opt", "какая у меня виза", "чем f-1", "отличается opt", "qué es opt", "que es opt", "mi visa", "qué visa tengo"],
        "answers": {
            "en": "For taxes, **F-1** and **OPT** are the same student status: OPT is work permission on an F-1 visa, so you stay an exempt individual (usually a nonresident) for your first 5 calendar years in the US and your wages are typically exempt from FICA. **H-1B** is a work visa: its days count toward the substantial presence test from day one, so many H-1B holders become residents and FICA applies.",
            "ru": "Для налогов **F-1** и **OPT** — один и тот же студенческий статус: OPT — это разрешение на работу по визе F-1, поэтому первые 5 календарных лет в США вы «освобождённое лицо» (обычно нерезидент), а зарплата, как правило, освобождена от FICA. **H-1B** — рабочая виза: её дни сразу учитываются в тесте существенного присутствия, поэтому многие на H-1B становятся резидентами, и FICA удерживается.",
            "es": "Para impuestos, **F-1** y **OPT** son el mismo estatus de estudiante: OPT es un permiso de trabajo con visa F-1, así que sigues siendo persona exenta (normalmente no residente) durante tus primeros 5 años calendario en EE. UU. y tu salario suele estar exento de FICA. **H-1B** es una visa de trabajo: sus días cuentan para la presencia sustancial desde el primer día, por lo que muchos titulares de H-1B pasan a ser residentes y se aplica FICA.",
        },
    },
    {
        "id": "fica",
        "keywords": ["fica", "social security", "medicare", "фика", "соцстрах", "seguro social"],
        "answers": {
            "en": "**FICA** is Social Security (6.2%) plus Medicare (1.45%) withheld from wages. Nonresident students and scholars on F, J, M or Q status are generally exempt (IRC §3121(b)(19)) while they are nonresidents. If it was withheld by mistake, ask your employer for a refund first; if they won't, file **Form 843** with **Form 8316** to the IRS.",
            "ru": "**FICA** — это налоги Social Security (6,2%) и Medicare (1,45%), удерживаемые из зарплаты. Студенты и исследователи-нерезиденты со статусом F, J, M или Q, как правило, освобождены (IRC §3121(b)(19)), пока они нерезиденты. Если налог удержали по ошибке, сначала попросите возврат у работодателя; если он откажет — подайте в IRS **Form 843** вместе с **Form 8316**.",
            "es": "**FICA** es el Seguro Social (6,2%) más Medicare (1,45%) que se retiene del salario. Los estudiantes e investigadores no residentes con estatus F, J, M o Q generalmente están exentos (IRC §3121(b)(19)) mientras son no residentes. Si te lo retuvieron por error, pide primero el reembolso a tu empleador; si no lo hace, presenta el **Form 843** con el **Form 8316** al IRS.",
        },
    },
    {
        "id": "form8843",
        "keywords": ["8843"],
        "answers": {
            "en": "**Form 8843** is filed by exempt individuals (F, J, M, Q students, teachers and trainees) to exclude their days from the substantial presence test, even with no income. Each person, including dependents, files their own. Attach it to Form 1040-NR, or mail it on its own by {f8843} if you have no return to file for {year}.",
            "ru": "**Form 8843** подают «освобождённые лица» (студенты, преподаватели и стажёры F, J, M, Q), чтобы исключить свои дни из теста существенного присутствия, даже без дохода. Каждый, включая иждивенцев, подаёт свою форму. Её прикладывают к Form 1040-NR или, если декларацию за {year} подавать не нужно, отправляют отдельно до {f8843}.",
            "es": "El **Form 8843** lo presentan las personas exentas (estudiantes, profesores y aprendices F, J, M, Q) para excluir sus días de la prueba de presencia sustancial, incluso sin ingresos. Cada persona, incluidos los dependientes, presenta el suyo. Se adjunta al Form 1040-NR o, si no tienes que presentar declaración de {year}, se envía por separado antes del {f8843}.",
        },
    },
    {
        "id": "w2_vs_1099",
        "keywords": ["1099 vs", "w-2 vs", "w2 vs", "1099 or w-2", "w-2 or 1099", "difference between 1099", "difference between w-2", "contractor or employee", "1099 или w-2", "w-2 или 1099", "разница между 1099", "разница между w-2", "1099 o w-2", "w-2 o 1099", "diferencia entre 1099", "diferencia entre w-2"],
        "answers": {
            "en": "A **W-2** means you are an employee: your employer withholds income tax and FICA from each paycheck. A **1099** (for example 1099-NEC) means you were paid as an independent contractor: nothing is withheld, you pay **self-employment tax** on top of income tax, you can deduct business expenses on Schedule C, and you usually make quarterly estimated payments.",
            "ru": "**W-2** означает, что вы сотрудник: работодатель удерживает подоходный налог и FICA из каждой зарплаты. **1099** (например, 1099-NEC) — оплата как независимому подрядчику: ничего не удерживается, сверх подоходного налога вы платите **налог на самозанятость**, можете вычитать деловые расходы по Schedule C и обычно вносите квартальные платежи.",
            "es": "Un **W-2** significa que eres empleado: tu empleador retiene el impuesto sobre la renta y FICA de cada pago. Un **1099** (por ejemplo, 1099-NEC) significa que te pagaron como contratista independiente: no se retiene nada, pagas el **impuesto de trabajo por cuenta propia** además del impuesto sobre la renta, puedes deducir gastos en el Schedule C y normalmente haces pagos trimestrales estimados.",
        },
    },
    {
        "id": "se_tax",
        "keywords": ["self-employment tax", "self employment tax", "schedule se", "налог на самозанят", "самозанятост", "trabajo por cuenta propia", "autónomo", "autonomo"],
        "answers": {
            "en": "**Self-employment tax** is the Social Security and Medicare tax for people who work for themselves: about 15.3% of net 1099 earnings (calculated on Schedule SE), and half of it is deductible. Nonresident aliens generally don't owe it unless a totalization agreement applies; residents do.",
            "ru": "**Налог на самозанятость** — это Social Security и Medicare для тех, кто работает на себя: около 15,3% чистого дохода по 1099 (считается по Schedule SE), половину можно вычесть. Нерезиденты, как правило, его не платят (если не применяется соглашение о соцобеспечении), резиденты — платят.",
            "es": "El **impuesto de trabajo por cuenta propia** es el Seguro Social y Medicare para quienes trabajan por su cuenta: alrededor del 15,3% de la ganancia neta 1099 (se calcula en el Schedule SE) y la mitad es deducible. Los no residentes en general no lo pagan salvo que aplique un acuerdo de totalización; los residentes sí.",
        },
    },
    {
        "id": "quarterly",
        "keywords": ["quarterly", "estimated tax", "estimated payment", "1040-es", "квартальн", "ежеквартальн", "расчётный налог", "trimestral", "impuesto estimado", "pagos estimados"],
        "answers": {
            "en": "If you expect to owe at least $1,000 for the year (common with 1099 income), the IRS expects **quarterly estimated payments** with **Form 1040-ES**. For {year} the due dates are {q_dates}. You can pay through IRS Direct Pay (irs.gov/payments) or EFTPS.",
            "ru": "Если за год вы, скорее всего, будете должны $1,000 и больше (частая ситуация с доходом по 1099), IRS ожидает **квартальные расчётные платежи** по **Form 1040-ES**. Сроки за {year} год: {q_dates}. Платить можно через IRS Direct Pay (irs.gov/payments) или EFTPS.",
            "es": "Si esperas deber al menos $1,000 en el año (habitual con ingresos 1099), el IRS espera **pagos trimestrales estimados** con el **Form 1040-ES**. Para {year} las fechas son {q_dates}. Puedes pagar con IRS Direct Pay (irs.gov/payments) o EFTPS.",
        },
    },
    {
        "id": "wrong_form",
        "keywords": ["wrong form", "1040-x", "amend", "filed 1040 instead", "не ту форму", "неправильную форму", "неверную форму", "formulario equivocado", "formulario incorrecto", "enmendar", "enmienda"],
        "answers": {
            "en": "If you filed the wrong return (for example Form 1040 while you were a nonresident), you fix it with an amended return: **Form 1040-X** with a corrected Form 1040-NR attached. Doing it promptly limits interest and penalties; refunds or credits you weren't entitled to (like some education credits) may have to be paid back.",
            "ru": "Если подана не та декларация (например, Form 1040, хотя вы были нерезидентом), её исправляют уточнённой декларацией: **Form 1040-X** с приложенной правильной Form 1040-NR. Чем раньше, тем меньше процентов и штрафов; возвраты и кредиты, на которые не было права (например, некоторые образовательные), может потребоваться вернуть.",
            "es": "Si presentaste la declaración equivocada (por ejemplo, el Form 1040 siendo no residente), se corrige con una declaración enmendada: **Form 1040-X** con un Form 1040-NR corregido adjunto. Hacerlo pronto limita intereses y multas; es posible que debas devolver reembolsos o créditos a los que no tenías derecho (como algunos créditos educativos).",
        },
    },
    {
        "id": "itin",
        "keywords": [r"\bitin\b", "w-7", r"\bssn\b", "итин", "social security number", "número de seguro social"],
        "answers": {
            "en": "You need a taxpayer ID to file. If you aren't eligible for a Social Security Number (SSN), apply for an **ITIN** with **Form W-7**, usually submitted together with your tax return and a passport or certified copies. If you have an SSN (for example through OPT or H-1B work authorization), use it instead.",
            "ru": "Для подачи нужен налоговый номер. Если вам не положен номер социального страхования (SSN), оформите **ITIN** по **Form W-7** — обычно её подают вместе с декларацией и паспортом или заверенными копиями. Если SSN есть (например, благодаря разрешению на работу OPT или H-1B), используйте его.",
            "es": "Necesitas un número de contribuyente para declarar. Si no puedes obtener un número de Seguro Social (SSN), solicita un **ITIN** con el **Form W-7**, normalmente junto con tu declaración y el pasaporte o copias certificadas. Si tienes SSN (por ejemplo, por la autorización de trabajo OPT o H-1B), usa ese.",
        },
    },
    {
        "id": "standard_deduction",
        "keywords": ["standard deduction", "стандартный вычет", "стандартного вычета", "deducción estándar", "deduccion estandar"],
        "status_note": True,
        "answers": {
            "en": "Residents filing Form 1040 can take the **standard deduction** ({sd} for a single filer in {year}). Nonresidents filing Form 1040-NR generally cannot; the main exception is students and business apprentices from India under Article 21(2) of the US-India tax treaty.",
            "ru": "Резиденты, подающие Form 1040, могут взять **стандартный вычет** ({sd} для одиночного налогоплательщика за {year} год). Нерезиденты с Form 1040-NR, как правило, не могут; главное исключение — студенты и стажёры из Индии по статье 21(2) налогового соглашения США и Индии.",
            "es": "Los residentes que presentan el Form 1040 pueden usar la **deducción estándar** ({sd} para soltero/a en {year}). Los no residentes con Form 1040-NR generalmente no pueden; la principal excepción son los estudiantes y aprendices de la India según el artículo 21(2) del tratado fiscal EE. UU.-India.",
        },
    },
    {
        "id": "deadline",
        "keywords": ["deadline", "when to file", "when do i file", "due date", "срок", "когда подавать", "до какого", "plazo", "fecha límite", "cuándo presentar", "cuando presentar"],
        "answers": {
            "en": "For tax year {year}, Form 1040 / 1040-NR (with wages) is due {annual}. Form 8843 filed on its own is due {f8843}. Quarterly 1040-ES payments are due {q_dates}.",
            "ru": "За {year} год Form 1040 / 1040-NR (при наличии зарплаты) нужно подать до {annual}. Отдельная Form 8843 — до {f8843}. Квартальные платежи 1040-ES: {q_dates}.",
            "es": "Para el año fiscal {year}, el Form 1040 / 1040-NR (con salarios) vence el {annual}. El Form 8843 por separado vence el {f8843}. Los pagos trimestrales 1040-ES vencen {q_dates}.",
        },
    },
    {
        "id": "software",
        "keywords": ["software", "which program", "what program", "какие программы", "какая программа", "в какой программе", "qué programa", "que programa", "programas admiten"],
        "answers": {
            "en": "Check before you pay for anything: many popular tax programs only prepare the standard Form 1040. If you are a nonresident, make sure the software or preparer supports **Form 1040-NR** (and Form 8843). Students should also ask their international student office: many universities provide free access to nonresident tax software.",
            "ru": "Проверьте до оплаты: многие популярные налоговые программы готовят только стандартную Form 1040. Если вы нерезидент, убедитесь, что программа или специалист поддерживают **Form 1040-NR** (и Form 8843). Студентам стоит спросить в международном офисе университета: многие дают бесплатный доступ к программам для нерезидентов.",
            "es": "Compruébalo antes de pagar: muchos programas fiscales populares solo preparan el Form 1040 estándar. Si eres no residente, asegúrate de que el programa o el preparador admita el **Form 1040-NR** (y el Form 8843). Los estudiantes también pueden preguntar en su oficina internacional: muchas universidades dan acceso gratuito a programas para no residentes.",
        },
    },
]

_STATUS_FORM = {
    "RESIDENT_ALIEN": {"en": "Form 1040", "ru": "Form 1040", "es": "Form 1040"},
    "NONRESIDENT_ALIEN": {"en": "Form 1040-NR", "ru": "Form 1040-NR", "es": "Form 1040-NR"},
    "DUAL_STATUS_ALIEN": {
        "en": "a dual-status return (Form 1040 + 1040-NR statement)",
        "ru": "декларация с двойным статусом (Form 1040 + приложение 1040-NR)",
        "es": "una declaración de doble estatus (Form 1040 + anexo 1040-NR)",
    },
}


def _matches(keyword: str, text: str) -> bool:
    if keyword.startswith(r"\b") or "\\" in keyword:
        return re.search(keyword, text) is not None
    return keyword in text


def find_topics(text: str) -> List[str]:
    """Matching topic ids, best first (by number and length of matched keywords)."""
    low = text.lower()
    scored: List[Tuple[int, str]] = []
    for topic in FAQ:
        score = sum(len(k) for k in topic["keywords"] if _matches(k, low))
        if score:
            scored.append((score, topic["id"]))
    scored.sort(key=lambda item: -item[0])
    return [topic_id for _, topic_id in scored]


def answer(topic_id: str, language: str, tax_year: int, status: Optional[str] = None, status_label: str = "") -> str:
    topic = next(t for t in FAQ if t["id"] == topic_id)
    text = topic["answers"][language].format(**_year_facts(language, tax_year))
    if topic.get("status_note") and status in _STATUS_FORM and status_label:
        note = {
            "en": "Based on what you've told me so far, you're likely {status}, so your return is {form}.",
            "ru": "По тому, что вы уже рассказали, вы, скорее всего, {status}, значит ваша декларация — {form}.",
            "es": "Según lo que me has contado, probablemente eres {status}, así que tu declaración es {form}.",
        }[language]
        text += " " + note.format(status=status_label, form=_STATUS_FORM[status][language])
    return text

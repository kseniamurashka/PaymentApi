# Kvitto Payments API

Тестовое задание Junior Python: API оплаты курсов на FastAPI. Сервис хранит тарифы и платежи, рассчитывает скидку и рассрочку, обрабатывает повторные запросы и подписанные уведомления банка.

Стек: Python 3.13, FastAPI, Pydantic v2, синхронный SQLAlchemy, SQLite, Alembic, pytest и httpx. Реальных списаний и возвратов денег нет: вебхук обновляет статус платежа в базе.

## Получение проекта

```powershell
git clone https://github.com/kseniamurashka/PaymentApi.git
cd PaymentApi
```

Команды ниже приведены для Windows PowerShell и выполняются из корня проекта. Для Docker-запуска достаточно Git и запущенного Docker Desktop с Linux-контейнерами; локальный Python не требуется.

## Запуск через Docker Compose

При первом запуске создать файл настроек:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Если `.env` уже настроен, повторно копировать его не нужно. В `.env.example` указан демонстрационный секрет для локальной разработки.

При запуске контейнер применяет миграции, затем запускает API. Приложение добавляет отсутствующие тарифы без дублирования существующих.

- API: <http://127.0.0.1:8000>
- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI: <http://127.0.0.1:8000/openapi.json>

Запуск в фоне, просмотр логов и остановка:

```powershell
docker compose up --build -d
docker compose logs -f api
docker compose down
```

SQLite хранится в `/data/payments.db`, каталог `/data` подключён к именованному тому `payments_data`. Обычный `docker compose down` сохраняет том. Команда `docker compose down -v` удалит его вместе с данными.

В `compose.yaml` явно задано имя проекта `kvitto-payments-api`, поэтому запуск не зависит от названия локальной папки.

## Локальный запуск без Docker

Нужен Python 3.11 или новее; проект проверен на Python 3.13.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Копирование `.env` требуется только при первом запуске. Документация также доступна по адресу <http://127.0.0.1:8000/docs>. Локальный сервер и Docker-контейнер используют порт 8000: запускать только один из этих вариантов одновременно.

## Настройки

| Переменная | Назначение |
|---|---|
| `DATABASE_URL` | Адрес базы. По умолчанию `sqlite:///./payments.db` - файл в рабочей папке. |
| `WEBHOOK_SECRET` | Обязательный общий секрет для проверки подписи банковского вебхука. |

Приложение читает переменные окружения и `.env`; окружение имеет приоритет. Compose задаёт свой адрес базы `sqlite:////data/payments.db` и передаёт `WEBHOOK_SECRET` из окружения или корневого `.env`. Сам `.env` исключён из Git и Docker-образа.

## Правила платежей

Все денежные значения в API и базе - целые числа в копейках, без `float`.

| Тариф | Цена в рублях | `price` в API |
|---|---:|---:|
| basic | 9 900 | 990000 |
| standard | 19 900 | 1990000 |
| premium | 29 900 | 2990000 |

- `KVITTO10` даёт скидку 10%, регистр не важен. Неизвестный, в том числе пустой, код возвращает `422`.
- `amount` - итоговая сумма после скидки; `discount` - размер скидки в копейках.
- Способы оплаты: `card`, `sbp`, `installment`.
- Для `installment` обязателен `installment_months`: 3, 6 или 12. Для карты и СБП сохранённые срок и график равны `null`.
- Сумма платежей графика точно равна `amount`; лишние копейки распределяются по одной в первые платежи. Например, `1990000` на 3 месяца: `[663334, 663333, 663333]`.
- Новый платёж имеет статус `pending`.

Разрешены только переходы:

```text
pending   -> succeeded
pending   -> failed
succeeded -> refunded
```

Остальные переходы, включая переход в тот же статус, возвращают `409` и не меняют запись.

Обновление проверяет прежний статус непосредственно в базе. Если два вебхука одновременно прочитали один статус, сохранить изменение сможет только один; второй получит `409` без перезаписи результата первого.

## Эндпоинты

| Метод и путь | Результат |
|---|---|
| `GET /tariffs` | `200`: список тарифов с `id`, `title`, `price`. |
| `POST /payments` | `201`: новый платёж; `200`: ранее созданный платёж с тем же `Idempotency-Key`. |
| `GET /payments/{payment_id}` | `200`: платёж; `404`: запись отсутствует. |
| `GET /payments` | `200`: список платежей по возрастанию ID, необязательные фильтры `email` и `status`. |
| `POST /webhooks/bank` | Подписанное уведомление о смене статуса. Успех: `200 {"result": "ok"}`. |

Создание платежа принимает `tariff_id`, `email`, `method`, необязательные `promo_code` и `installment_months` (обязателен для рассрочки). Неизвестный тариф возвращает `404`.

Платёж в ответе содержит `id`, `status`, `tariff_id`, `amount`, `discount`, `method`, `installment_months`, `schedule`, `email`, `created_at`. Ключ идемпотентности в ответ не включается.

Если передан `Idempotency-Key`, повтор с тем же ключом возвращает прежнюю запись без обновления её данных. Проверяется уникальность ключа в базе, конфликт вставки обрабатывается через откат и повторный поиск. Без ключа одинаковые запросы создают отдельные платежи.

Фильтры списка соединяются условием «И». При отсутствии совпадений возвращается `[]`. Ошибки валидации используют стандартный формат FastAPI с кодом `422`.

## Примеры запросов

Получить тарифы:

```powershell
curl.exe -i "http://127.0.0.1:8000/tariffs"
```

Создать платёж в рассрочку со скидкой. При необходимости заменить `tariff_id=2` на ID тарифа из предыдущего ответа:

```powershell
@'
{"tariff_id":2,"email":"student@example.com","method":"installment","installment_months":3,"promo_code":"kvitto10"}
'@ | curl.exe -i "http://127.0.0.1:8000/payments" -H "Content-Type: application/json" -H "Idempotency-Key: readme-payment-1" --data-binary "@-"
```

При первом запросе ожидается `201`, при повторении команды с тем же ключом - `200` и тот же ID. Для тарифа standard сумма после скидки - `1791000`, скидка - `199000`, график - `[597000, 597000, 597000]`.

Получить платёж и отфильтровать список. Заменить `1` на ID из ответа создания:

```powershell
curl.exe -i "http://127.0.0.1:8000/payments/1"
curl.exe -i "http://127.0.0.1:8000/payments?email=student%40example.com&status=pending"
```

## Подпись банковского вебхука

Тело уведомления: `{"payment_id":1,"status":"succeeded"}`. Заголовок `X-Signature` содержит HMAC-SHA256 от исходных байтов тела с секретом `WEBHOOK_SECRET`, представленный 64 шестнадцатеричными символами в нижнем регистре.

Важно подписывать и отправлять одни и те же байты: изменение пробелов, порядка полей или значений меняет подпись. Отсутствующая или неверная подпись возвращает `401` до изменения платежа. С правильной подписью отсутствующий платёж возвращает `404`, а запрещённый переход - `409 {"error": "invalid_transition"}`.

Пример для уже запущенного Docker-контейнера. Заменить `payment_id` на ID созданного платежа в статусе `pending`:

```powershell
@'
import hashlib
import hmac
import json

import httpx

from app.config import settings

payment_id = 1
body = json.dumps(
    {"payment_id": payment_id, "status": "succeeded"},
    separators=(",", ":"),
).encode("utf-8")
signature = hmac.new(
    settings.webhook_secret.encode("utf-8"),
    body,
    hashlib.sha256,
).hexdigest()

response = httpx.post(
    "http://127.0.0.1:8000/webhooks/bank",
    content=body,
    headers={
        "Content-Type": "application/json",
        "X-Signature": signature,
    },
)
print(response.status_code)
print(response.json())
'@ | docker compose exec -T api python -
```

Для локального запуска заменить последнюю строку на `'@ | python -` и использовать активированное виртуальное окружение. Пример берёт секрет из настроек приложения и не выводит его.

Первое уведомление `pending -> succeeded` вернёт `200`. Повтор того же уведомления вернёт `409`, поскольку переход `succeeded -> succeeded` запрещён.

## Тесты и проверки

В активированном локальном окружении:

```powershell
python -m pytest -q
python -m ruff check .
python -m ruff format --check app tests migrations
alembic check
```

Или внутри запущенного контейнера:

```powershell
docker compose exec -T api python -m pytest -q
docker compose exec -T api python -m ruff check .
docker compose exec -T api alembic check
```

Тесты используют отдельную SQLite в памяти и тестовый секрет. Они проверяют тарифы, денежные расчёты, рассрочку на 3/6/12 месяцев, создание и получение платежей, идемпотентность, все сочетания статусов, подпись вебхука и фильтры. Конфликт ключа проверяется через моделирование пропуска записи при первом поиске и реальное нарушение уникальности в тестовой базе; это не нагрузочный тест параллельных запросов.

Отдельный тест одновременных вебхуков использует временную файловую SQLite с независимыми соединениями. Два запроса читают `pending` до обновления; тест проверяет ответы `200` и `409`, а также сохранение статуса успешного запроса.

GitHub Actions запускает Ruff, применение и проверку миграций, pytest на каждый `push` и `pull_request`. Конфигурация находится в `.github/workflows/ci.yml`.

## Изменение схемы базы

После изменения моделей создать миграцию, проверить сгенерированный файл и применить её:

```powershell
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
alembic check
```

Приложение не создаёт таблицы через `create_all`: схема управляется Alembic. `create_all` используется только для подготовки тестовой базы.

## Структура

```text
app/
  main.py        # Приложение и загрузка тарифов при запуске
  config.py      # Настройки окружения
  database.py    # Движок, фабрика сессий, зависимость get_db
  models.py      # Модели SQLAlchemy
  schemas.py     # Схемы запросов и ответов, валидация
  routes.py      # Эндпоинты и проверка подписи как зависимость
  services.py    # Расчёты и правила переходов статусов
  security.py    # Проверка HMAC-SHA256
  seed.py        # Начальные тарифы
migrations/      # Миграции Alembic
tests/           # Проверки API и бизнес-логики
.github/workflows/ci.yml
Dockerfile
compose.yaml
```

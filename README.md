# Telegram-бот «Склад»

Бот ведёт учёт товарных остатков в SQLite. Поддерживает добавление и списание товаров, просмотр остатков, поиск, подтверждаемое удаление и историю последних операций. Доступ разрешён только Telegram ID из `ALLOWED_USERS`.

## Требования

- Python 3.10 или новее
- Telegram-бот, созданный через [@BotFather](https://t.me/BotFather)

## Установка и запуск

```bash
git clone https://github.com/azatswe/warehouse_bot.git
cd warehouse_bot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Откройте `.env` и задайте значения:

- `BOT_TOKEN` — токен, выданный BotFather.
- `ALLOWED_USERS` — один или несколько Telegram ID через запятую.
- `DATABASE_PATH` — путь к SQLite-файлу (по умолчанию `warehouse.db`).

Запустите бота:

```bash
python main.py
```

Файл базы создаётся при первом запуске и сохраняется между перезапусками. `.env` и файлы SQLite исключены из Git.

## Развёртывание на Ubuntu через Docker Compose

Установите Docker Engine и Compose plugin из официального [репозитория Docker для Ubuntu](https://docs.docker.com/engine/install/ubuntu/), затем проверьте `sudo docker run hello-world` и `sudo docker compose version`. Для production не используйте convenience install script.

```bash
git clone https://github.com/azatswe/warehouse_bot.git
cd warehouse_bot
cp .env.example .env
nano .env
chmod 600 .env
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps
sudo docker compose logs --tail=100 bot
```

В `.env` задайте `BOT_TOKEN` и реальные Telegram ID в `ALLOWED_USERS`. Не отправляйте `.env` в Git и не публикуйте его содержимое. Compose сохраняет SQLite в отдельном Docker volume; сам volume не является резервной копией — настройте и проверьте отдельный backup базы.

Обновление после получения новой версии проекта:

```bash
git pull --ff-only
sudo docker compose up -d --build
```

Бот использует Telegram long polling и не предоставляет входящий HTTP-сервис: порты не публикуются, домен и TLS для самого бота не нужны. Серверу требуется исходящий доступ к Telegram API. Использование группы `docker` даёт пользователю практически root-доступ; в примерах оставлен `sudo`.

## Функции

- **Добавить товар** — название 2–100 символов и количество от 1 до 1 000 000; совпадающие названия объединяются без учёта регистра и лишних пробелов.
- **Списать товар** — выбор кнопкой; остаток не может стать отрицательным, товар с нулём остаётся в списке.
- **Остатки** — список по алфавиту, число позиций и суммарное количество; длинный список разбивается на сообщения.
- **Найти товар** — поиск по части названия без учёта регистра.
- **Удалить товар** — удаление только после подтверждения.
- **История операций** — последние 20 добавлений, списаний и удалений.
- **Понятное меню** — действия подписаны эмодзи, а подсказки и подтверждения короткие и последовательные.
- **Автоудаление по желанию** — выключено по умолчанию. Включите или выключите его кнопкой «🧹 Автоудаление (вкл/выкл)» в меню. Когда режим включён, в личном чате удаляются сообщения пользователя и устаревшие подсказки; результаты операций и остатки остаются. В группах бот ничего не удаляет. Настройка сохраняется отдельно для каждого пользователя.

Команды: `/start` — меню, `/list` — остатки, `/find <часть названия>` — поиск, `/cancel` — отменить текущий диалог и вернуться в меню.

## Проверки

Запуск автоматических проверок из корня проекта:

```bash
python -m unittest discover -s tests -v
```

Приёмочные сценарии и порядок проверки перечислены в [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

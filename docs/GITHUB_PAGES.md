# 🌐 Хостинг мини-приложения на GitHub Pages

Мини-приложение (`webapp/index.html`) — self-contained SPA, поэтому его
можно бесплатно раздавать через GitHub Pages, а FastAPI-часть оставить
только для API (или отключить вовсе, если оплата и генерация ключей
пока не подключены).

## Шаг 1. Создать приватный репозиторий

1. Открой https://github.com/new.
2. Repository name → например `blacklotus`.
3. Visibility → **Private** (см. `LICENSE.md` — код проприетарный).
4. Create repository.

## Шаг 2. Запушить проект

```bash
git remote add origin git@github.com:<username>/blacklotus.git
git branch -M main
git push -u origin main
```

## Шаг 3. Включить Pages

1. **Settings → Pages** в репозитории.
2. **Source**: `Deploy from a branch`.
3. **Branch**: `main`, **folder**: `/webapp`.
4. Save. Через 1–2 минуты появится URL вида:

   ```
   https://<username>.github.io/<repo-name>/
   ```

## Шаг 4. Прописать URL в `.env`

```
WEBAPP_URL=https://<username>.github.io/<repo-name>/
```

Перезапусти бота — на `/start` появится кнопка «🖤 Открыть BlackLotusVPN».

## Шаг 5. Меню-кнопка бота (@BotFather)

1. Открой [@BotFather](https://t.me/BotFather).
2. `/mybots` → выбери свой бот.
3. **Bot Settings → Menu Button → Configure Menu Button**.
4. Введи тот же URL из шага 4 и текст кнопки, например `🖤 Открыть`.

Теперь мини-приложение будет доступно и по кнопке в чате, и через
глобальное меню Telegram.

## Что если репозиторий приватный?

GitHub Pages для приватных репозиториев доступен только на **GitHub Pro /
Team / Enterprise**. Альтернативы:

- Cloudflare Pages (бесплатно, приватный source возможен).
- Vercel / Netlify (bind private repo, deploy `webapp/` как static).
- Свой nginx + Let's Encrypt (см. `../README.md`).

## Обновление приложения

Любой `git push` в `main` автоматически передеплоит Pages в течение
1–2 минут. Инвалидация кеша браузера может потребовать `Ctrl+Shift+R`.

## Пути и base URL

`webapp/index.html` использует только относительные и абсолютные `https://`
ссылки — никаких `/static/`. Работает и на корневом домене, и на
подпапке `<repo>/`.

## Ограничения

- GitHub Pages отдаёт только статику. Все `/api/*` из FastAPI-версии
  недоступны — при переезде на Pages API-часть должна жить на другом
  домене (или в MVP её нет вовсе — SPA работает с заглушками).
- Telegram WebApp принимает только HTTPS-URL — GitHub Pages это условие
  выполняет.

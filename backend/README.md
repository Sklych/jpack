# Backend

Минимальный backend для текущей игры на `Flask + SQLite`.

## Что есть

- Валидация `Telegram WebApp initData`
- Автосоздание и обновление пользователя при входе
- Хранение `balance` и `best_score`
- Реферальная связь `referrer -> referred`
- Система заданий с backend-статусами и наградами
- Лидерборд `top 10` + позиция текущего пользователя
- Создание заявки на вывод кристаллов со статусом `pending`
- Приём `wallet_info` из TON Connect прямо в заявке на вывод
- Не больше одной `pending`-заявки на `uid` или `TON wallet address`
- Лимит на сумму одной заявки задаётся через `MAX_WITHDRAW_CRYSTALS_PER_REQUEST`
- Курс для отображения `TON` в клиенте отдаётся в `auth/init` как `withdraw.tonRatePerCrystal`
- Экономика по умолчанию: `45` кристаллов минимум, `90` кристаллов максимум за заявку, `1` кристалл = `0.001111 TON`, `1 TON = 100 ₽`

## Запуск

1. Создай `.env` на основе `.env.example`
2. Установи зависимости:

```bash
pip install -r requirements.txt
```

3. Запусти сервер:

```bash
python main.py
```

## Основные маршруты

- `POST /api/auth/init`
- `POST /api/game/finish`
- `GET /api/leaderboard?kind=distance|referrals`
- `GET /api/tasks`
- `POST /api/tasks/complete-task`
- `POST /api/withdraw/request`
- `GET /api/withdraw/history`
- `POST /api/admin/tasks`
- `POST /api/admin/withdraw/complete`

## Задания

`GET /api/tasks` возвращает список заданий, их статус, текущий множитель кристаллов, баланс кристаллов и `inviteUrl` для реферального шаринга.

Сейчас реализованы:
- `share_app` с наградой `+0.1x`
- реферальные задания `invite_3`, `invite_10`, `invite_20` и дальше с шагом `+10`, каждое даёт `+0.3x`

Инвайт-задания контролируются только backend и не имеют клиентской ручки завершения.

`POST /api/tasks/complete-task` принимает `taskId`. Backend сам проверяет, можно ли завершать эту задачу с клиента.

Если задача клиентская, backend:
- помечает её выполненной
- начисляет награду в кристаллах или пересчитывает множитель
- возвращает обновлённый payload заданий

Если задача серверная, backend вернёт ошибку.

Пример:

```json
{
  "initData": "...",
  "taskId": "share_app"
}
```

## Добавление новой задачи

`POST /api/admin/tasks` защищён через `ADMIN_API_TOKEN` и позволяет добавить новую задачу, которая начнёт появляться у пользователей.

Пример body:

```json
{
  "taskId": "share_story",
  "type": "share",
  "title": "Поделиться историей",
  "description": "Поделись приложением с друзьями.",
  "rewardType": "crystal_multiplier",
  "rewardValue": 0.2,
  "clientCompletable": true,
  "isActive": true,
  "sortOrder": 20
}
```

## Формат вывода

`POST /api/withdraw/request` принимает `wallet_info` в body по аналогии с `Flappy`, то есть можно передавать объект из `tonConnectUI.wallet.account`:

```json
{
  "initData": "...",
  "amount": 12.5,
  "wallet_info": {
    "address": "UQ...",
    "chain": "-239",
    "publicKey": "...",
    "walletStateInit": "..."
  }
}
```

## Подтверждение выплат

`POST /api/admin/withdraw/complete` защищён через `ADMIN_API_TOKEN`.

Можно передать токен:
- в заголовке `Authorization: Bearer <token>`
- или в заголовке `X-Admin-Token: <token>`
- или в body как `token`

Пример body:

```json
{
  "ids": [12, 15, 18]
}
```

Ответ:

```json
{
  "ok": true,
  "data": {
    "completedIds": [12, 15],
    "alreadyCompletedIds": [18],
    "notFoundIds": []
  }
}
```

## Контракт auth-ошибки

Если `initData` отсутствует или невалиден, backend отвечает так:

```json
{
  "ok": false,
  "error": {
    "code": "INVALID_INIT_DATA",
    "message": "Не удалось подтвердить вход через Telegram: ..."
  }
}
```

"""
Админка внутри бота.
Команда /admin, доступ только по ADMIN_ID из .env (через @admin_only).
Возможности:
- статистика (юзеры, активные подписки, доход);
- рассылка всем пользователям;
- выдача/отзыв подписки вручную (по tg_id).
Все действия пишутся в audit.log.
"""
import asyncio

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from db.database import AsyncSessionLocal
from db.repo import (
    stats,
    get_all_user_ids,
    get_user_by_tg_id,
    grant_subscription,
    revoke_subscription,
    PLANS,
)
from security.logging_setup import audit

from .keyboards import admin_menu_kb
from .security import admin_only


router = Router(name="admin")


class AdminStates(StatesGroup):
    """FSM-состояния для админских диалогов."""
    waiting_broadcast = State()
    waiting_grant = State()   # ждём "<tg_id> <plan>"
    waiting_revoke = State()  # ждём "<tg_id>"


@router.message(Command("admin"))
@admin_only
async def cmd_admin(message: Message) -> None:
    """/admin — показать меню (только для владельца)."""
    audit(message.from_user.id, "admin_open")
    await message.answer("🛠 <b>Админ-панель</b>", reply_markup=admin_menu_kb(),
                         parse_mode="HTML")


# ---------- Статистика ----------

@router.callback_query(F.data == "admin:stats")
@admin_only
async def cb_stats(cb: CallbackQuery) -> None:
    async with AsyncSessionLocal() as session:
        s = await stats(session)
    text = (
        "📊 <b>Статистика BlackLotusVPN</b>\n\n"
        f"👥 Пользователей: <b>{s['users']}</b>\n"
        f"💎 Активных подписок: <b>{s['active_subs']}</b>\n"
        f"💰 Общий доход: <b>{s['revenue']:.2f} ₽</b>"
    )
    audit(cb.from_user.id, "admin_stats_view")
    await cb.message.answer(text, parse_mode="HTML")
    await cb.answer()


# ---------- Рассылка ----------

@router.callback_query(F.data == "admin:broadcast")
@admin_only
async def cb_broadcast(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_broadcast)
    await cb.message.answer("Отправь текст рассылки (или /cancel).")
    await cb.answer()


@router.message(AdminStates.waiting_broadcast, Command("cancel"))
@admin_only
async def broadcast_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Рассылка отменена.")


@router.message(AdminStates.waiting_broadcast)
@admin_only
async def broadcast_send(message: Message, state: FSMContext, bot: Bot) -> None:
    """Массовая рассылка. Ошибки (заблокировали бота и т.п.) — просто игнорим."""
    text = message.html_text
    async with AsyncSessionLocal() as session:
        ids = await get_all_user_ids(session)

    ok = 0
    fail = 0
    for tg_id in ids:
        try:
            await bot.send_message(tg_id, text, parse_mode="HTML")
            ok += 1
        except Exception:
            fail += 1
        # Ограничение Telegram ~30 сообщений/сек: делаем небольшую задержку
        await asyncio.sleep(0.05)

    await state.clear()
    audit(message.from_user.id, "broadcast", ok=ok, fail=fail,
          length=len(text or ""))
    await message.answer(f"✅ Отправлено: {ok}\n❌ Не удалось: {fail}")


# ---------- Выдать подписку ----------

@router.callback_query(F.data == "admin:grant")
@admin_only
async def cb_grant(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_grant)
    await cb.message.answer(
        "Отправь в формате: <code>&lt;tg_id&gt; &lt;plan&gt;</code>\n"
        "Планы: 1m / 3m / 6m\n"
        "Пример: <code>1783373795 3m</code>",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(AdminStates.waiting_grant)
@admin_only
async def grant_process(message: Message, state: FSMContext) -> None:
    parts = (message.text or "").strip().split()
    if len(parts) != 2:
        await message.answer("Неверный формат. Пример: <code>1783373795 3m</code>",
                             parse_mode="HTML")
        return
    tg_id_str, plan = parts
    if plan not in PLANS:
        await message.answer("Неизвестный тариф. Доступно: 1m / 3m / 6m")
        return
    try:
        tg_id = int(tg_id_str)
    except ValueError:
        await message.answer("tg_id должен быть числом.")
        return

    async with AsyncSessionLocal() as session:
        user = await get_user_by_tg_id(session, tg_id)
        if user is None:
            await message.answer("Пользователь не найден в БД (должен /start сначала).")
            return
        sub = await grant_subscription(session, user, plan)

    await state.clear()
    audit(message.from_user.id, "grant", target=tg_id, plan=plan)
    await message.answer(
        f"✅ Подписка выдана.\nПользователь: <code>{tg_id}</code>\n"
        f"Тариф: {plan}\nДо: {sub.expires_at:%d.%m.%Y}",
        parse_mode="HTML",
    )


# ---------- Отозвать подписку ----------

@router.callback_query(F.data == "admin:revoke")
@admin_only
async def cb_revoke(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_revoke)
    await cb.message.answer("Пришли tg_id пользователя, у которого отозвать подписку.")
    await cb.answer()


@router.message(AdminStates.waiting_revoke)
@admin_only
async def revoke_process(message: Message, state: FSMContext) -> None:
    try:
        tg_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("tg_id должен быть числом.")
        return
    async with AsyncSessionLocal() as session:
        user = await get_user_by_tg_id(session, tg_id)
        if user is None:
            await message.answer("Пользователь не найден.")
            return
        await revoke_subscription(session, user)
    await state.clear()
    audit(message.from_user.id, "revoke", target=tg_id)
    await message.answer(f"🚫 Подписка отозвана у <code>{tg_id}</code>.",
                         parse_mode="HTML")

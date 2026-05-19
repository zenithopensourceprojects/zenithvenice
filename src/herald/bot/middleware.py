"""Middlewares: user upsert + structured error logging."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update, User

from herald.data import users
from herald.logging_setup import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

log = get_logger(__name__)


def _user_from_event(event: TelegramObject) -> tuple[User | None, int | None]:
    """Best-effort extraction of (User, chat_id) from any Telegram event."""
    if isinstance(event, Message):
        return event.from_user, event.chat.id
    if isinstance(event, CallbackQuery):
        chat_id = event.message.chat.id if event.message else None
        return event.from_user, chat_id
    if isinstance(event, Update):
        if event.message:
            return event.message.from_user, event.message.chat.id
        if event.callback_query:
            chat_id = event.callback_query.message.chat.id if event.callback_query.message else None
            return event.callback_query.from_user, chat_id
    return None, None


class UserActivityMiddleware(BaseMiddleware):
    """Upsert telegram_users and refresh last_active_at on every interaction."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user, chat_id = _user_from_event(event)
        if user is not None and chat_id is not None and not user.is_bot:
            try:
                users.upsert_user(
                    tg_user_id=user.id,
                    tg_chat_id=chat_id,
                    username=user.username,
                    first_name=user.first_name,
                    language_code=user.language_code,
                )
            except Exception as exc:
                log.warning("user_upsert_failed", error=str(exc), tg_user_id=user.id)
        return await handler(event, data)


class ErrorLoggingMiddleware(BaseMiddleware):
    """Catch and log unhandled exceptions in handlers."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as exc:
            log.exception("handler_failed", error=str(exc), event_type=type(event).__name__)
            if isinstance(event, CallbackQuery):
                with contextlib.suppress(Exception):
                    await event.answer("Something went wrong. Please try again.", show_alert=False)
            return None

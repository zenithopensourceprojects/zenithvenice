"""Callback handlers for every `hub:*` callback.

Decoupled from `bot/callbacks.py` (which keeps the legacy feed-card
callbacks for fanout-delivered messages). All handlers here only edit the
hub message in place — never spawn new messages in the chat.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router

from herald.bot import views
from herald.bot.hub import close_hub, edit_hub
from herald.data import bookmarks, posts
from herald.logging_setup import get_logger

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery

router = Router(name="hub_callbacks")
log = get_logger(__name__)


# ----- Helpers --------------------------------------------------------------


def _split(data: str | None, *, parts: int) -> list[str] | None:
    """Split callback data, returning None if the shape doesn't match."""
    if not data:
        return None
    out = data.split(":", parts - 1)
    if len(out) != parts:
        return None
    return out


# ----- Root / nav -----------------------------------------------------------


@router.callback_query(F.data == "hub:noop")
async def on_noop(query: CallbackQuery) -> None:
    """The non-interactive page-counter pill swallows taps silently."""
    await query.answer()


@router.callback_query(F.data == "hub:close")
async def on_close(query: CallbackQuery) -> None:
    """Close the hub — feed stays clean, hub message becomes a small farewell."""
    await close_hub(query)
    await query.answer()


@router.callback_query(F.data == "hub:root")
async def on_root(query: CallbackQuery) -> None:
    """Render the hub's home screen."""
    first_name = query.from_user.first_name if query.from_user else None
    text, keyboard = views.render_root(first_name=first_name)
    await edit_hub(query, text=text, keyboard=keyboard)
    await query.answer()


# ----- Latest ---------------------------------------------------------------


@router.callback_query(F.data.startswith("hub:latest:"))
async def on_latest(query: CallbackQuery) -> None:
    """Paginated latest-news list."""
    parts = _split(query.data, parts=3)
    if parts is None:
        await query.answer()
        return
    try:
        page = int(parts[2])
    except ValueError:
        page = 0

    items = posts.fetch_latest(limit=20)
    text, keyboard = views.render_latest(items, page=page)
    await edit_hub(query, text=text, keyboard=keyboard)
    await query.answer()


# ----- Categories -----------------------------------------------------------


@router.callback_query(F.data == "hub:cats")
async def on_categories_grid(query: CallbackQuery) -> None:
    """Grid of all categories."""
    text, keyboard = views.render_categories_grid()
    await edit_hub(query, text=text, keyboard=keyboard)
    await query.answer()


@router.callback_query(F.data.startswith("hub:cat:"))
async def on_category_list(query: CallbackQuery) -> None:
    """Paginated list of a single category's stories.

    Callback shape: `hub:cat:<key>:<page>`.
    """
    parts = _split(query.data, parts=4)
    if parts is None:
        await query.answer()
        return
    category = parts[2]
    try:
        page = int(parts[3])
    except ValueError:
        page = 0

    items = posts.fetch_latest(limit=20, category=category)
    text, keyboard = views.render_category_list(items, category=category, page=page)
    await edit_hub(query, text=text, keyboard=keyboard)
    await query.answer()


# ----- Saved ----------------------------------------------------------------


@router.callback_query(F.data.startswith("hub:saved:"))
async def on_saved(query: CallbackQuery) -> None:
    """Paginated bookmarks for the current user."""
    if not query.from_user:
        await query.answer()
        return
    parts = _split(query.data, parts=3)
    if parts is None:
        await query.answer()
        return
    try:
        page = int(parts[2])
    except ValueError:
        page = 0

    items = bookmarks.list_saved(query.from_user.id, limit=50)
    text, keyboard = views.render_saved(items, page=page)
    await edit_hub(query, text=text, keyboard=keyboard)
    await query.answer()


# ----- Search prompt --------------------------------------------------------


@router.callback_query(F.data == "hub:search")
async def on_search(query: CallbackQuery) -> None:
    """How-to-search prompt — Telegram callbacks can't capture free text."""
    text, keyboard = views.render_search_prompt()
    await edit_hub(query, text=text, keyboard=keyboard)
    await query.answer()


# ----- About ----------------------------------------------------------------


@router.callback_query(F.data == "hub:about")
async def on_about(query: CallbackQuery) -> None:
    """About / how-we-verify screen."""
    text, keyboard = views.render_about()
    await edit_hub(query, text=text, keyboard=keyboard)
    await query.answer()


# ----- Article view ---------------------------------------------------------


@router.callback_query(F.data.startswith("hub:art:"))
async def on_article(query: CallbackQuery) -> None:
    """Single-article view inside the hub.

    Callback shape: `hub:art:<post_id>:<return_cd>` where `<return_cd>` is
    a fully-qualified callback (e.g. `hub:latest:0`) the [« Back] button
    will fire to return the user to the list they came from.
    """
    parts = _split(query.data, parts=4)
    if parts is None:
        await query.answer()
        return
    post_id, return_cd = parts[2], parts[3]

    post = posts.fetch_post_by_id(post_id)
    if post is None:
        await query.answer("This story is no longer available.", show_alert=True)
        return

    saved = False
    if query.from_user:
        saved = bookmarks.is_saved(query.from_user.id, post_id)

    text, keyboard, preview_url = views.render_article(
        post, return_cd=return_cd, saved=saved
    )
    await edit_hub(
        query, text=text, keyboard=keyboard,
        disable_preview=False, preview_url=preview_url,
    )
    await query.answer()


# ----- Save / unsave from inside the hub -----------------------------------


@router.callback_query(F.data.startswith("hub:save:"))
async def on_hub_save_toggle(query: CallbackQuery) -> None:
    """Toggle the bookmark on the post currently viewed in the hub.

    Callback shape: `hub:save:<post_id>:<return_cd>`.
    """
    parts = _split(query.data, parts=4)
    if parts is None or not query.from_user:
        await query.answer()
        return
    post_id, return_cd = parts[2], parts[3]

    post = posts.fetch_post_by_id(post_id)
    if post is None:
        await query.answer("This story is no longer available.", show_alert=True)
        return

    if bookmarks.is_saved(query.from_user.id, post_id):
        bookmarks.remove(query.from_user.id, post_id)
        toast = "Removed from saved"
        saved = False
    else:
        bookmarks.save(query.from_user.id, post_id)
        toast = "Saved ⭐"
        saved = True

    text, keyboard, preview_url = views.render_article(
        post, return_cd=return_cd, saved=saved
    )
    await edit_hub(
        query, text=text, keyboard=keyboard,
        disable_preview=False, preview_url=preview_url,
    )
    await query.answer(toast, show_alert=False)


# ----- All-sources view -----------------------------------------------------


@router.callback_query(F.data.startswith("hub:src:"))
async def on_hub_sources(query: CallbackQuery) -> None:
    """All-sources view inside the hub.

    Callback shape: `hub:src:<post_id>:<return_cd>`. The `« Back to story`
    button will return the user to the article view.
    """
    parts = _split(query.data, parts=4)
    if parts is None:
        await query.answer()
        return
    post_id, return_cd = parts[2], parts[3]

    post = posts.fetch_post_by_id(post_id)
    if post is None:
        await query.answer("This story is no longer available.", show_alert=True)
        return

    text, keyboard = views.render_sources_view(post, return_cd=return_cd)
    await edit_hub(query, text=text, keyboard=keyboard)
    await query.answer()

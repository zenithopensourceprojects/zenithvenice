"""Hub view renderers — pure functions that return (text, keyboard) pairs.

Each function is deterministic and has no I/O, so callers (commands,
callbacks) can compose them freely. I/O happens only at the call site.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from herald.config import get_settings
from herald.render.card import (
    render_full_sources_card,
    render_list_item,
    render_post_card,
)
from herald.render.category import all_themes, theme_for
from herald.utils.escape import escape_html, truncate

if TYPE_CHECKING:
    from herald.data.models import Post


# ----- Constants ------------------------------------------------------------

PAGE_SIZE = 5
LIST_HEADLINE_LIMIT = 90


# ----- Root menu ------------------------------------------------------------


def render_root(*, first_name: str | None = None) -> tuple[str, InlineKeyboardMarkup]:
    """The hub's home screen: 4 fat buttons + concise hero copy."""
    settings = get_settings()
    name = escape_html(first_name) if first_name else "there"

    text = (
        "🇮🇳   <b>INDIA  VERIFIED</b>\n"
        "<i>The verified-news desk for India.</i>\n\n"
        f"Welcome back, <b>{name}</b>.\n"
        "Every story below is cross-checked against multiple sources before it lands here.\n\n"
        "<i>Pick where to dive in</i> ↓"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📰  Latest stories",       callback_data="hub:latest:0"),
        InlineKeyboardButton(text="📂  Browse categories",    callback_data="hub:cats"),
    )
    builder.row(
        InlineKeyboardButton(text="🔎  Search",               callback_data="hub:search"),
        InlineKeyboardButton(text="⭐  Saved",                 callback_data="hub:saved:0"),
    )
    builder.row(
        InlineKeyboardButton(text="⚙️  Preferences",           callback_data="set:root"),
        InlineKeyboardButton(text="ℹ️  About",                 callback_data="hub:about"),
    )
    if settings.public_site_url:
        builder.row(
            InlineKeyboardButton(
                text="🌐  Open India Verified  ↗",
                url=settings.public_site_url + "/",
            ),
        )

    return text, builder.as_markup()


# ----- Categories grid ------------------------------------------------------


def render_categories_grid() -> tuple[str, InlineKeyboardMarkup]:
    """Two-column grid of every category. Tapping one drills into a paged list."""
    text = (
        "📂   <b>Categories</b>\n\n"
        "<i>Tap a topic to see verified stories — newest first.</i>"
    )

    builder = InlineKeyboardBuilder()
    for theme in all_themes():
        builder.button(
            text=f"{theme.emoji}  {theme.label}",
            callback_data=f"hub:cat:{theme.key}:0",
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="« Menu", callback_data="hub:root"))
    return text, builder.as_markup()


# ----- Paginated list views (latest / category / saved / search) -----------


def _list_header(title_html: str, page: int, total_pages: int, total: int) -> str:
    """Compact list header used by every paginated view."""
    page_label = f"Page {page + 1}/{max(total_pages, 1)}"
    return f"{title_html}\n<i>{total} verified · {page_label}</i>"


def _list_body(items: list[Post], *, offset: int) -> str:
    """Render one page worth of one-line list items."""
    lines = [render_list_item(post, index=offset + i + 1) for i, post in enumerate(items)]
    return "\n\n".join(lines)


def _list_keyboard(
    *,
    items: list[Post],
    page: int,
    total_pages: int,
    base_back_cd: str,
    article_return_cd: str,
    page_cd_prefix: str,
) -> InlineKeyboardMarkup:
    """Keyboard for a list page: item buttons + pager + back/close.

    `article_return_cd` is the callback the article view's [« Back] button
    should fire to return the user here.
    """
    builder = InlineKeyboardBuilder()

    # Numeric drill-in row(s): up to 5 slots, 5-wide.
    if items:
        for i, post in enumerate(items):
            builder.button(
                text=str(i + 1),
                callback_data=f"hub:art:{post.id}:{article_return_cd}",
            )
        builder.adjust(min(len(items), 5))

    pager: list[InlineKeyboardButton] = []
    if total_pages > 1:
        if page > 0:
            pager.append(
                InlineKeyboardButton(text="‹  Prev", callback_data=f"{page_cd_prefix}:{page - 1}")
            )
        pager.append(
            InlineKeyboardButton(
                text=f"·  {page + 1}/{total_pages}  ·", callback_data="hub:noop"
            )
        )
        if page < total_pages - 1:
            pager.append(
                InlineKeyboardButton(text="Next  ›", callback_data=f"{page_cd_prefix}:{page + 1}")
            )
        builder.row(*pager)

    builder.row(
        InlineKeyboardButton(text="« Back",  callback_data=base_back_cd),
        InlineKeyboardButton(text="✕ Close", callback_data="hub:close"),
    )
    return builder.as_markup()


def paginate(items: list[Post], page: int) -> tuple[list[Post], int, int]:
    """Slice a result set into a page; returns (page_items, page, total_pages)."""
    total = len(items)
    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    return items[start : start + PAGE_SIZE], page, total_pages


def render_latest(items: list[Post], *, page: int) -> tuple[str, InlineKeyboardMarkup]:
    """Paged list of latest verified posts."""
    page_items, page, total_pages = paginate(items, page)
    title = "📰   <b>Latest verified stories</b>"

    if not items:
        empty = (
            f"{title}\n\n"
            "<i>No verified stories yet — check back in a few minutes.</i>"
        )
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="« Menu",  callback_data="hub:root"),
            InlineKeyboardButton(text="✕ Close", callback_data="hub:close"),
        )
        return empty, builder.as_markup()

    header = _list_header(title, page, total_pages, len(items))
    body = _list_body(page_items, offset=page * PAGE_SIZE)
    text = f"{header}\n\n{body}"
    keyboard = _list_keyboard(
        items=page_items,
        page=page,
        total_pages=total_pages,
        base_back_cd="hub:root",
        article_return_cd=f"hub:latest:{page}",
        page_cd_prefix="hub:latest",
    )
    return text, keyboard


def render_category_list(
    items: list[Post],
    *,
    category: str,
    page: int,
) -> tuple[str, InlineKeyboardMarkup]:
    """Paged list for one category."""
    page_items, page, total_pages = paginate(items, page)
    theme = theme_for(category)
    title = f"{theme.emoji}   <b>{escape_html(theme.label)}</b>"

    if not items:
        empty = (
            f"{title}\n\n"
            "<i>No verified stories in this category yet.</i>"
        )
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="« Categories", callback_data="hub:cats"),
            InlineKeyboardButton(text="✕ Close",      callback_data="hub:close"),
        )
        return empty, builder.as_markup()

    header = _list_header(title, page, total_pages, len(items))
    body = _list_body(page_items, offset=page * PAGE_SIZE)
    text = f"{header}\n\n{body}"
    keyboard = _list_keyboard(
        items=page_items,
        page=page,
        total_pages=total_pages,
        base_back_cd="hub:cats",
        article_return_cd=f"hub:cat:{category}:{page}",
        page_cd_prefix=f"hub:cat:{category}",
    )
    return text, keyboard


def render_saved(items: list[Post], *, page: int) -> tuple[str, InlineKeyboardMarkup]:
    """Paged list of the user's bookmarks."""
    page_items, page, total_pages = paginate(items, page)
    title = "⭐   <b>Saved stories</b>"

    if not items:
        empty = (
            f"{title}\n\n"
            "<i>You haven't saved anything yet.</i>\n"
            "Tap <b>⭐ Save</b> on any incoming story to bookmark it."
        )
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="« Menu",  callback_data="hub:root"),
            InlineKeyboardButton(text="✕ Close", callback_data="hub:close"),
        )
        return empty, builder.as_markup()

    header = _list_header(title, page, total_pages, len(items))
    body = _list_body(page_items, offset=page * PAGE_SIZE)
    text = f"{header}\n\n{body}"
    keyboard = _list_keyboard(
        items=page_items,
        page=page,
        total_pages=total_pages,
        base_back_cd="hub:root",
        article_return_cd=f"hub:saved:{page}",
        page_cd_prefix="hub:saved",
    )
    return text, keyboard


def render_search_prompt() -> tuple[str, InlineKeyboardMarkup]:
    """Tells the user how to search; can't read free text from a callback."""
    text = (
        "🔎   <b>Search verified news</b>\n\n"
        "<i>Send any keyword or phrase — for example:</i>\n"
        "<code>/search modi northeast</code>\n"
        "<code>/search isro chandrayaan</code>\n\n"
        "Results appear as a paginated list right here in the hub."
    )
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="« Menu",  callback_data="hub:root"),
        InlineKeyboardButton(text="✕ Close", callback_data="hub:close"),
    )
    return text, builder.as_markup()


def render_search_results(
    items: list[Post], *, query: str, page: int
) -> tuple[str, InlineKeyboardMarkup]:
    """Paged search results for a single query."""
    page_items, page, total_pages = paginate(items, page)
    safe_q = escape_html(truncate(query, 80))
    title = f"🔎   <b>Results for «{safe_q}»</b>"

    if not items:
        empty = f"{title}\n\n<i>No matches.</i>"
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="« Menu",  callback_data="hub:root"),
            InlineKeyboardButton(text="✕ Close", callback_data="hub:close"),
        )
        return empty, builder.as_markup()

    header = _list_header(title, page, total_pages, len(items))
    body = _list_body(page_items, offset=page * PAGE_SIZE)
    text = f"{header}\n\n{body}"
    keyboard = _list_keyboard(
        items=page_items,
        page=page,
        total_pages=total_pages,
        base_back_cd="hub:root",
        article_return_cd="hub:root",  # one-shot — back goes to menu
        page_cd_prefix="hub:noop",     # search pagination requires the query, omitted for now
    )
    return text, keyboard


# ----- Article view (single post inside the hub) ----------------------------


def render_article(
    post: Post, *, return_cd: str, saved: bool = False
) -> tuple[str, InlineKeyboardMarkup, str | None]:
    """Full article card rendered inside the hub. Returns (text, keyboard, preview_url)."""
    card = render_post_card(post)
    settings = get_settings()
    web_url = settings.post_web_url(post.id)

    builder = InlineKeyboardBuilder()

    # Source links use full URL row above to maximise tap target
    from herald.render.sources import primary_source

    primary = primary_source(post.sources)
    if primary:
        from herald.render.sources import display_name

        primary_label = truncate(f"📰  Read on {display_name(primary)}", 56) + "  ↗"
        builder.row(InlineKeyboardButton(text=primary_label, url=primary.url))

    builder.row(InlineKeyboardButton(text="🌐  Open on India Verified  ↗", url=web_url))

    save_label = "⭐  Saved" if saved else "⭐  Save"
    builder.row(
        InlineKeyboardButton(text=save_label,        callback_data=f"hub:save:{post.id}:{return_cd}"),
        InlineKeyboardButton(text="📚  All sources", callback_data=f"hub:src:{post.id}:{return_cd}"),
    )
    builder.row(
        InlineKeyboardButton(text="« Back",  callback_data=return_cd),
        InlineKeyboardButton(text="✕ Close", callback_data="hub:close"),
    )

    return card.text, builder.as_markup(), card.preview_url


def render_sources_view(
    post: Post, *, return_cd: str
) -> tuple[str, InlineKeyboardMarkup]:
    """All-sources view rendered inside the hub."""
    text = render_full_sources_card(post)
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="« Back to story",
            callback_data=f"hub:art:{post.id}:{return_cd}",
        ),
    )
    builder.row(
        InlineKeyboardButton(text="« Menu",  callback_data="hub:root"),
        InlineKeyboardButton(text="✕ Close", callback_data="hub:close"),
    )
    return text, builder.as_markup()


# ----- About ----------------------------------------------------------------


def render_about() -> tuple[str, InlineKeyboardMarkup]:
    """About / how-we-verify screen."""
    settings = get_settings()
    text = (
        "ℹ️   <b>About India Verified</b>\n\n"
        "We aggregate Indian news from trusted publishers, verify each story across "
        "multiple sources, and assign a <b>credibility score</b> before publishing.\n\n"
        "<b>Verification pipeline</b>\n"
        "1.  Fetch from a curated set of established publishers.\n"
        "2.  Cluster by topic so duplicates collapse into one post.\n"
        "3.  AI fact-check cross-references claims and flags discrepancies.\n"
        "4.  Only stories that pass clear are published.\n\n"
        "<b>Every card shows</b>\n"
        "•  Credibility score (0-100) and source count\n"
        "•  Three-bullet summary\n"
        "•  Direct links to every original publication\n"
        "•  Live preview from the primary source"
    )

    builder = InlineKeyboardBuilder()
    if settings.public_site_url:
        builder.row(
            InlineKeyboardButton(
                text="🌐  Visit the website  ↗",
                url=settings.public_site_url + "/",
            )
        )
    if settings.telegram_channel_invite_url:
        builder.row(
            InlineKeyboardButton(
                text="📣  Join the channel  ↗",
                url=settings.telegram_channel_invite_url,
            )
        )
    builder.row(
        InlineKeyboardButton(text="« Menu",  callback_data="hub:root"),
        InlineKeyboardButton(text="✕ Close", callback_data="hub:close"),
    )
    return text, builder.as_markup()

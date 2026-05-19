"""Category display metadata, mirroring the frontend's getCategoryTheme."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryTheme:
    """Display label and emoji glyph for a category key."""

    key: str
    label: str
    emoji: str


_THEMES: dict[str, CategoryTheme] = {
    "politics":      CategoryTheme("politics",      "Politics",      "📜"),
    "business":      CategoryTheme("business",      "Business",      "💼"),
    "sports":        CategoryTheme("sports",        "Sports",        "🏏"),
    "crime":         CategoryTheme("crime",         "Crime",         "⚖️"),
    "science":       CategoryTheme("science",       "Science",       "🔬"),
    "health":        CategoryTheme("health",        "Health",        "🩺"),
    "tech":          CategoryTheme("tech",          "Tech",          "💻"),
    "world":         CategoryTheme("world",         "World",         "🌐"),
    "entertainment": CategoryTheme("entertainment", "Entertainment", "🎬"),
    "education":     CategoryTheme("education",     "Education",     "🎓"),
}


_FALLBACK = CategoryTheme(key="general", label="News", emoji="📰")


def theme_for(category: str | None) -> CategoryTheme:
    """Return the category theme for a key, or a generic fallback."""
    if not category:
        return _FALLBACK
    return _THEMES.get(category.lower(), _FALLBACK)


def all_themes() -> list[CategoryTheme]:
    """Return every supported category theme in display order."""
    return list(_THEMES.values())

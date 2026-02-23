"""Page manager for multi-page dashboard layout.

Organizes cards into pages with a fixed grid. Only one page is
visible at a time. Navigation via prev/next buttons or edge taps.
No scrolling -- pagination is more reliable on Pi touchscreens.
"""

import tkinter as tk
import logging
from typing import List

logger = logging.getLogger(__name__)


class PageManager:
    """Manages multiple pages of cards in a fixed grid layout."""

    def __init__(self, parent, cols=3, rows=2, gap=8):
        self.parent = parent
        self.cols = cols
        self.rows = rows
        self.gap = gap
        self.cards_per_page = cols * rows
        self._pages: List[tk.Frame] = []
        self._all_cards = []
        self._current_page = 0

        # Container that holds the visible page
        self._container = tk.Frame(parent, bg=parent["bg"])
        self._container.pack(fill="both", expand=True)

    def create_page(self) -> tk.Frame:
        """Create a new page frame and return it (use as card parent)."""
        page = tk.Frame(self._container, bg=self._container["bg"])
        for col in range(self.cols):
            page.columnconfigure(col, weight=1, uniform="card")
        for row in range(self.rows):
            page.rowconfigure(row, weight=1, uniform="card")
        self._pages.append(page)
        return page

    def place_card(self, card, page_idx: int, position: int):
        """Grid a card onto a page at the given position."""
        r = position // self.cols
        c = position % self.cols
        card_cols = getattr(card, "COLS", 1)
        card_rows = getattr(card, "ROWS", 1)
        card.grid(
            row=r,
            column=c,
            columnspan=card_cols,
            rowspan=card_rows,
            padx=self.gap // 2,
            pady=self.gap // 2,
            sticky="nsew",
        )
        if card not in self._all_cards:
            self._all_cards.append(card)

    def show_first_page(self):
        """Show the first page. Call after all cards are placed."""
        if self._pages:
            self._show_page(0)

    def _show_page(self, idx):
        """Show a specific page, hide others."""
        for page in self._pages:
            page.pack_forget()
        if 0 <= idx < len(self._pages):
            self._current_page = idx
            self._pages[idx].pack(fill="both", expand=True)

    def next_page(self):
        """Navigate to next page (wraps around)."""
        if self._pages:
            self._show_page((self._current_page + 1) % len(self._pages))

    def prev_page(self):
        """Navigate to previous page (wraps around)."""
        if self._pages:
            self._show_page((self._current_page - 1) % len(self._pages))

    @property
    def page_count(self):
        return len(self._pages)

    @property
    def current_page(self):
        return self._current_page

    def get_all_cards(self):
        """Return flat list of all cards across all pages."""
        return list(self._all_cards)

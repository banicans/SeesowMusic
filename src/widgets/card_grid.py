import os
from typing import Callable, Optional

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk


class CardGrid(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._on_card_activated: Optional[Callable] = None

        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_vexpand(True)
        self._scrolled.set_hexpand(True)

        self._flowbox = Gtk.FlowBox()
        self._flowbox.set_homogeneous(False)
        self._flowbox.set_valign(Gtk.Align.START)
        self._flowbox.set_max_children_per_line(20)
        self._flowbox.set_min_children_per_line(2)
        self._flowbox.set_row_spacing(16)
        self._flowbox.set_column_spacing(16)
        self._flowbox.set_margin_start(16)
        self._flowbox.set_margin_end(16)
        self._flowbox.set_margin_top(16)
        self._flowbox.connect('child-activated', self._on_child_activated)
        self._scrolled.set_child(self._flowbox)

        self.append(self._scrolled)

    def set_cards(self, cards: list[Gtk.Widget]):
        self._clear()
        for card in cards:
            self._flowbox.append(card)
            fb_child = self._flowbox.get_last_child()
            if fb_child:
                fb_child.set_halign(Gtk.Align.START)

    def set_propagate_natural_height(self, propagate: bool):
        self._scrolled.set_propagate_natural_height(propagate)

    def on_card_activated(self, callback: Callable):
        self._on_card_activated = callback

    def _clear(self):
        while child := self._flowbox.get_first_child():
            self._flowbox.remove(child)

    def _on_child_activated(self, flowbox, child):
        if self._on_card_activated:
            actual_card = child.get_child()  # unwrap the FlowBoxChild
            if hasattr(actual_card, '_data'):
                self._on_card_activated(actual_card._data)

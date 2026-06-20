from typing import Callable

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk


class ContextMenu(Gtk.Popover):
    def __init__(self, items: list[tuple[str, Callable]]):
        super().__init__()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        for label, callback in items:
            btn = Gtk.Button(label=label)
            btn.add_css_class('flat')
            btn.add_css_class('context-menu-item')
            btn.connect('clicked', lambda b, cb=callback: (cb(), self.popdown()))
            box.append(btn)
        self.set_child(box)

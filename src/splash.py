import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib


class LoadingOverlay(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_halign(Gtk.Align.FILL)
        self.set_valign(Gtk.Align.FILL)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.add_css_class('loading-overlay')

        center = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        center.set_halign(Gtk.Align.CENTER)
        center.set_valign(Gtk.Align.CENTER)
        center.set_hexpand(True)
        center.set_vexpand(True)
        center.add_css_class('loading-box')

        title = Gtk.Label(label='Seesow Music')
        title.add_css_class('title-1')
        center.append(title)

        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_halign(Gtk.Align.CENTER)
        self._progress_bar.set_size_request(300, -1)
        center.append(self._progress_bar)

        self._info_label = Gtk.Label(label='Loading library\u2026')
        self._info_label.add_css_class('dim-label')
        center.append(self._info_label)

        self.append(center)

    def set_progress(self, loaded: int, total: int):
        fraction = loaded / total if total > 0 else 0
        self._progress_bar.set_fraction(fraction)
        self._info_label.set_label(f'Loading library\u2026 ({loaded}/{total})')

    def set_complete_text(self):
        self._info_label.set_label('Loading library\u2026 complete')

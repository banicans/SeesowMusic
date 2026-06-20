#!/usr/bin/env python3
import signal
import sys
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GLib, Adw


class SeesowMusicApp(Adw.Application):
    def do_activate(self):
        from src.window import MainWindow
        win = MainWindow(application=self)
        win.present()

    def do_startup(self):
        Adw.Application.do_startup(self)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self._on_sigint, None)

    def _on_sigint(self, user_data=None):
        self.quit()
        return GLib.SOURCE_REMOVE


if __name__ == '__main__':
    app = SeesowMusicApp(application_id='com.seesow.musicplayer')
    app.run(sys.argv)

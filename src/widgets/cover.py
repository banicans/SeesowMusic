import functools
from typing import Optional

import gi
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf, GLib


@functools.lru_cache(maxsize=256)
def load_cover_pixbuf(path: str, size: int) -> Optional[GdkPixbuf.Pixbuf]:
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
        w, h = pixbuf.get_width(), pixbuf.get_height()
        if w == 0 or h == 0:
            return None
        if w < h:
            nw, nh = size, int(h * size / w)
        else:
            nw, nh = int(w * size / h), size
        scaled = pixbuf.scale_simple(nw, nh, GdkPixbuf.InterpType.BILINEAR)
        if not scaled:
            return None
        x, y = (nw - size) // 2, (nh - size) // 2
        return scaled.new_subpixbuf(x, y, size, size)
    except GLib.Error:
        return None

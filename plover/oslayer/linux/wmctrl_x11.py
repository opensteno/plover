from Xlib import X, display
from Xlib.error import BadWindow
from Xlib.protocol.event import ClientMessage


class WmCtrl:
    def __init__(self):
        self._display = display.Display()
        self._root = self._display.screen().root
        self._atoms = {
            name: self._display.intern_atom(name)
            for name in [
                "_NET_ACTIVE_WINDOW",
                "_NET_CURRENT_DESKTOP",
                "_NET_WM_DESKTOP",
                "_WIN_WORKSPACE",
            ]
        }

    def _get_wm_property(self, window, atom_name):
        prop = window.get_full_property(self._atoms[atom_name], X.AnyPropertyType)
        return None if prop is None else prop.value[0]

    def _client_msg(self, window, atom_name, data):
        ev_data = (data,) + (0,) * 4
        ev = ClientMessage(
            window=window, client_type=self._atoms[atom_name], data=(32, ev_data)
        )
        ev_mask = X.SubstructureRedirectMask | X.SubstructureNotifyMask
        self._root.send_event(ev, event_mask=ev_mask)
        self._display.sync()

    def _map_raised(self, window):
        window.map()
        window.raise_window()
        self._display.sync()

    def get_foreground_window(self):
        return self._get_wm_property(self._root, "_NET_ACTIVE_WINDOW")

    def set_foreground_window(self, w):
        try:
            window = self._display.create_resource_object("window", w)
            for atom in ("_NET_WM_DESKTOP", "_WIN_WORKSPACE"):
                desktop = self._get_wm_property(window, atom)
                if desktop is not None:
                    self._client_msg(self._root, "_NET_CURRENT_DESKTOP", desktop)
                    break
            self._client_msg(window, "_NET_ACTIVE_WINDOW", 0)
            self._map_raised(window)
        except BadWindow:
            pass

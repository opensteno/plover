import xcffib
from xcffib import xproto


class WmCtrl:
    def __init__(self):
        self._display = xcffib.connect()
        self._root = self._display.get_setup().roots[self._display.pref_screen].root
        self._atoms = {
            name: self._display.core.InternAtom(False, len(name), name.encode())
            .reply()
            .atom
            for name in (
                "_NET_ACTIVE_WINDOW",
                "_NET_CURRENT_DESKTOP",
                "_NET_WM_DESKTOP",
                "_WIN_WORKSPACE",
            )
        }

    def _get_wm_property(self, window, atom_name):
        prop = self._display.core.GetProperty(
            False,
            window,
            self._atoms[atom_name],
            xproto.GetPropertyType.Any,
            0,
            1,
        ).reply()
        return None if not prop.value else prop.value.to_atoms()[0]

    def _client_msg(self, window, atom_name, data):
        event = xproto.ClientMessageEvent.synthetic(
            32,
            window,
            self._atoms[atom_name],
            xproto.ClientMessageData.synthetic((data, 0, 0, 0, 0), "=5I"),
        )
        self._display.core.SendEventChecked(
            False,
            self._root,
            xproto.EventMask.SubstructureRedirect | xproto.EventMask.SubstructureNotify,
            event.pack(),
        ).check()
        self._display.flush()

    def _map_raised(self, window):
        self._display.core.MapWindowChecked(window).check()
        self._display.core.ConfigureWindowChecked(
            window, xproto.ConfigWindow.StackMode, [xproto.StackMode.Above]
        ).check()
        self._display.flush()

    def get_foreground_window(self):
        return self._get_wm_property(self._root, "_NET_ACTIVE_WINDOW")

    def set_foreground_window(self, w):
        try:
            for atom in ("_NET_WM_DESKTOP", "_WIN_WORKSPACE"):
                desktop = self._get_wm_property(w, atom)
                if desktop is not None:
                    self._client_msg(self._root, "_NET_CURRENT_DESKTOP", desktop)
                    break
            self._client_msg(w, "_NET_ACTIVE_WINDOW", 0)
            self._map_raised(w)
            self._display.flush()
        except xproto.BadWindow:
            pass

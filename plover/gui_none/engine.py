from threading import Thread, current_thread

from plover.engine import StenoEngine
from plover.gui_none.add_translation import AddTranslation


class Engine(StenoEngine, Thread):
    def __init__(self, config, controller, keyboard_emulation):
        StenoEngine.__init__(self, config, controller, keyboard_emulation)
        Thread.__init__(self)
        self.name += "-engine"
        self._add_translation = AddTranslation(self)
        # self.hook_connect('quit', self.quit)

    def _in_engine_thread(self):
        return current_thread() == self

    def start(self):
        Thread.start(self)
        StenoEngine.start(self)

    def join(self):
        Thread.join(self)
        return self.code

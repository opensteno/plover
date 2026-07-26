from threading import Event

from plover.gui_none.engine import Engine
from plover.oslayer.keyboardcontrol import KeyboardEmulation


def show_error(title, message):
    print(f"{title}: {message}")


def main(config, controller):
    engine = Engine(config, controller, KeyboardEmulation())
    if not engine.load_config():
        return 3
    quitting = Event()
    engine.hook_connect("quit", quitting.set)
    engine.start()
    try:
        quitting.wait()
    except KeyboardInterrupt:
        engine.quit()
    return engine.join()

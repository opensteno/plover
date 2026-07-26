import locale
from ctypes import windll


def get_system_language():
    return locale.windows_locale[windll.kernel32.GetUserDefaultUILanguage()]

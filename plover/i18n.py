import os
import gettext

from plover.oslayer.config import CONFIG_DIR
from plover.oslayer.i18n import get_system_language
from plover.resource import ASSET_SCHEME, resource_filename


def get_language():
    # Give priority to LANGUAGE environment variable.
    lang = os.environ.get("LANGUAGE")
    if lang is not None:
        return lang
    # Try to get system language.
    lang = get_system_language()
    if lang is not None:
        return lang
    # Fallback to English.
    return "en"


def get_locale_dir(package, resource_dir):
    locale_dir = os.path.join(CONFIG_DIR, "messages")
    if gettext.find(package, locale_dir):
        return locale_dir
    return resource_filename(f"{ASSET_SCHEME}{package}:{resource_dir}")


class Translator:
    def __init__(self, package, resource_dir="messages", lang=None):
        self.package = package
        self.resource_dir = resource_dir
        if lang is None:
            lang = get_language()
        self.lang = lang

    @property
    def lang(self):
        return self._lang

    @lang.setter
    def lang(self, lang):
        self._lang = lang
        localedir = get_locale_dir(self.package, self.resource_dir)
        self._translation = gettext.translation(
            self.package, localedir=localedir, languages=[lang], fallback=True
        )
        self.gettext = self._translation.gettext
        self.ngettext = self._translation.ngettext

    def __call__(self, message):
        return self.gettext(message)

    def _(self, message):
        return message

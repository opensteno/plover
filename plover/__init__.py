# Copyright (c) 2010-2011 Joshua Harlan Lifton.
# See LICENSE.txt for details.

"""Plover: Open Source Stenography Software"""

if __name__ == "plover":
    from plover.i18n import Translator

    _ = Translator(__package__)
else:
    # exec from `setup.py`, package data
    # may not be available, and we don't
    # want to translate anyway.
    def _(s):
        return s


__version__ = "5.2.0"
__copyright__ = "(C) Open Steno Project"
__url__ = "http://www.openstenoproject.org/"
__download_url__ = "http://www.openstenoproject.org/plover"
__credits__ = _("""\
Founded by stenographer Mirabai Knight.

Developers:

Joshua Lifton
Hesky Fisher
Thea Morin
Benoit Pierre
Sammi Ta
Martin Koerner

and many more on GitHub:
<https://github.com/openstenoproject/plover>""")
__license__ = "GNU General Public License v2 or later (GPLv2+)"
# i18n: Short description for Plover, currently not used in the interface.
__description__ = _("Open Source Stenography Software")
__long_description__ = _("""\
Plover is a free open source program intended to bring realtime
stenographic technology not just to stenographers, but also to
hackers, hobbyists, accessibility mavens, and all-around speed demons.""")

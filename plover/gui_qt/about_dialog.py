import re

from PySide6.QtWidgets import QDialog

import plover
from plover.gui_qt.about_dialog_ui import Ui_AboutDialog


class AboutDialog(QDialog, Ui_AboutDialog):
    ROLE = "about"

    def __init__(self, engine):
        super().__init__()
        self.setupUi(self)
        credits = plover.__credits__
        credits = re.sub(r"<([^>]*)>", r'<a href="\1">\1</a>', credits)
        credits = credits.replace("\n", "<br/>")
        self.text.setHtml(
            """
            <style>
            h1 {{text-align:center;}}
            h2 {{text-align:center;}}
            p {{text-align:center;}}
            </style>
            <p><img src="{icon}"/></p>
            <h1>{name} {version}</h1>
            <p>{description}</p>
            <p><i>Copyright {copyright}</i></p>
            <p>License: <a href="{license_url}">{license}</a></p>
            <p>Project Homepage: <a href='{url}'>{url}</a></p>
            <h2>Credits:</h2>
            <p>{credits}</p>
            """.format(
                icon=":/resources/plover.png",
                name=plover.__name__.capitalize(),
                version=plover.__version__,
                description=plover.__long_description__,
                copyright=plover.__copyright__.replace("(C)", "&copy;"),
                license=plover.__license__,
                license_url="https://www.gnu.org/licenses/gpl-2.0-standalone.html",
                url=plover.__download_url__,
                credits=credits,
            )
        )

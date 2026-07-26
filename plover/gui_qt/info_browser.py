import re

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QImage, QTextDocument
from PySide6.QtWidgets import QTextBrowser

from plover import log
from plover.plugins_manager.requests import CachedFuturesSession, CachedSession


class InfoBrowser(QTextBrowser):
    _resource_downloaded = Signal(str, bytes)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Regex to remove any explicit font-family attribute
        self._font_family_re = re.compile(
            r'\s*font-family\s*=\s*["\'][^"\']*["\']', re.IGNORECASE
        )
        self.setOpenExternalLinks(True)
        self._images = {}
        self._session = CachedSession()
        self._futures_session = None
        self._resource_downloaded.connect(self._update_image_resource)

    def loadResource(self, resource_type, resource_url):
        if resource_url.isLocalFile():
            resource = super().loadResource(resource_type, resource_url)
        else:
            resource = None
        resource_url = resource_url.url()
        if (
            resource is None
            and resource_type == QTextDocument.ResourceType.ImageResource
            and resource_url not in self._images
        ):
            future = self._futures_session.get(resource_url)
            future.add_done_callback(self._request_finished)
            self._images[resource_url] = future
        return resource

    def _request_finished(self, future):
        if not future.done():
            return
        try:
            resp = future.result()
        except Exception as exc:
            log.error("error fetching %s", exc.request.url, exc_info=True)
            return
        if not resp.ok:
            log.info("error fetching %s: %s", resp.url, resp.reason)
            return
        self._resource_downloaded.emit(resp.request.url, resp.content)

    def _reset_session(self):
        self._images.clear()
        if self._futures_session is not None:
            self._futures_session.close()
        self._futures_session = CachedFuturesSession(session=self._session)

    def setHtml(self, html):
        self._reset_session()
        super().setHtml(html)

    def setSource(self, url, kind):
        self._reset_session()
        super().setSource(url, kind)

    def _iter_fragments(self):
        bl = self.document().firstBlock()
        while bl.blockNumber() != -1:
            i = bl.begin()
            while not i.atEnd():
                frag = i.fragment()
                if frag.isValid():
                    yield frag
                i += 1
            bl = bl.next()

    def _sanitize_svg(self, data: bytes, url: str = "") -> bytes:
        """
        If *data* represents an SVG image, remove any explicit ``font-family``
        attributes so Qt will not attempt to resolve fonts that might be
        missing on the host system (which triggers slow alias‑population
        scans and warnings).

        Detection is done by:
        1.  URL ending with ``.svg`` **or**
        2.  Looking for ``<svg`` within the first ~256 decoded bytes.

        The function returns the (possibly modified) byte string.
        """
        # try to detect SVG by extension or content sniff.
        is_svg = url.lower().endswith(".svg")
        if not is_svg:
            try:
                head = data[:256].decode("utf-8", "ignore").lstrip().lower()
                is_svg = head.startswith("<svg") or "<svg" in head[:20]
            except Exception:
                # If decoding fails, assume it's not SVG.
                return data

        if not is_svg:
            return data

        # Strip any font-family attribute.
        try:
            text = data.decode("utf-8", "replace")
            text = self._font_family_re.sub("", text)
            return text.encode("utf-8")
        except Exception:
            # On failure, return the original bytes unchanged.
            return data

    def _update_image_resource(self, url, data):
        if url not in self._images:
            # Ignore request from a previous document.
            return

        data = self._sanitize_svg(data, url)

        image = QImage.fromData(data)
        if image is None:
            log.warning("could not load image from %s", url)
            return
        doc = self.document()
        doc.addResource(QTextDocument.ResourceType.ImageResource, QUrl(url), image)
        for frag in self._iter_fragments():
            fmt = frag.charFormat()
            if fmt.isImageFormat() and fmt.toImageFormat().name() == url:
                doc.markContentsDirty(frag.position(), frag.length())

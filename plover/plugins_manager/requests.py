import requests_cache
from requests_futures import sessions


class CachedSession(requests_cache.CachedSession):
    def __init__(self):
        super().__init__(backend="memory", expire_after=600)
        self.cache.delete(expired=True)


class CachedFuturesSession(sessions.FuturesSession):
    def __init__(self, session=None):
        if session is None:
            session = CachedSession()
        super().__init__(session=session, max_workers=4)

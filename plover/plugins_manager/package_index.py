import json
import os
from concurrent.futures import as_completed

from plover.plugins_manager.requests import CachedFuturesSession

PYPI_URL = "https://pypi.org/pypi"
REGISTRY_URL = "https://raw.githubusercontent.com/openstenoproject/plover_plugins_registry/master/registry.json"


def find_plover_plugins_releases(pypi_url=None, registry_url=None, capture=None):
    if pypi_url is None:
        pypi_url = os.environ.get("PYPI_URL", PYPI_URL)

    if registry_url is None:
        registry_url = os.environ.get("REGISTRY_URL", REGISTRY_URL)

    session = CachedFuturesSession()

    in_progress = set()
    all_releases = {}

    def fetch_release(name, version=None):
        if (name, version) in all_releases:
            return
        all_releases[(name, version)] = None
        if version is None:
            url = f"{pypi_url}/{name}/json"
        else:
            url = f"{pypi_url}/{name}/{version}/json"
        in_progress.add(session.get(url))

    with session:
        for name in session.get(registry_url).result().json():
            fetch_release(name)

        while in_progress:
            for future in as_completed(list(in_progress)):
                in_progress.remove(future)
                if not future.done():
                    continue
                resp = future.result()
                if resp.status_code != 200:
                    # Can happen if a package has been deleted.
                    continue
                release = resp.json()
                info = release["info"]
                if "plover_plugin" not in info["keywords"].split():
                    # Not a plugin.
                    continue
                name, version = info["name"], info["version"]
                all_releases[(name, version)] = release

    all_releases = [release for release in all_releases.values() if release is not None]

    if capture is not None:
        with open(capture, "w") as fp:
            json.dump(all_releases, fp, indent=2, sort_keys=True)

    return all_releases

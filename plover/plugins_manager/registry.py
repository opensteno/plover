from plover import log, __version__

from plover.plugins_manager import global_registry, local_registry

from plover.plugins_manager.requests import CachedFuturesSession


class PackageState:
    def __init__(self, name, installed=None, available=None):
        self.name = name
        self.installed = installed or []
        self.available = available or []
        self.status = "installed" if installed else ""

    @property
    def current(self):
        return self.installed[-1] if self.installed else None

    @current.setter
    def current(self, metadata):
        self.installed.append(metadata)
        self.status = "removed" if metadata is None else "updated"

    @property
    def latest(self):
        return self.available[-1] if self.available else None

    @property
    def metadata(self):
        return self.current or self.latest

    def __getattr__(self, name):
        return getattr(self.metadata, name)

    def __str__(self):
        s = self.name
        if self.latest:
            s += " " + self.latest.version
        if self.current:
            s += " [" + self.status + " " + self.current.version + "]"
        return s

    def __lt__(self, other):
        return self.name < other.name

    def __repr__(self):
        return str(self)


UNSUPPORTED_PLUGINS_URL = "https://raw.githubusercontent.com/openstenoproject/plover_plugins_registry/master/unsupported.json"


class Registry:
    def __init__(self):
        self._packages = {
            name: PackageState(name, installed=metadata)
            for name, metadata in local_registry.list_plugins().items()
        }

    def __len__(self):
        return len(self._packages)

    def __contains__(self, name):
        return name in self._packages

    def __getitem__(self, name):
        return self._packages[name]

    def __iter__(self):
        return iter(self._packages.values())

    def keys(self):
        return self._packages.keys()

    def items(self):
        return self._packages.items()

    # TODO add tests for this method
    def parse_unsupported_plover_version(self, unsupported_plover_version) -> int:
        """
        Handling different formats in case the unsupported_plover_version format changes in future Plover versions.
        """
        if isinstance(unsupported_plover_version, int):
            return unsupported_plover_version
        elif isinstance(unsupported_plover_version, str):
            try:
                return int(unsupported_plover_version.split(".")[0])
            except Exception as e:
                raise ValueError(
                    f'Failed to parse unsupported plover version "{unsupported_plover_version}" from plugin metadata'
                ) from e
        else:
            raise ValueError(
                f'Unknown format for unsupported plover version "{unsupported_plover_version}" from plugin metadata'
            )

    def is_plugin_supported(self, pkg, unsupported_plugins_dict):
        if not unsupported_plugins_dict:
            return True
        if pkg.name in unsupported_plugins_dict:
            unsupported_plover_version = unsupported_plugins_dict[pkg.name]
            try:
                parsed_unsupported_plover_version = (
                    self.parse_unsupported_plover_version(unsupported_plover_version)
                )
            except Exception:
                log.warning(
                    f'Failed to parse unsupported plover version "{pkg.unsupported_plover_version}" for plugin {pkg.name}, assuming plugin is supported',
                    exc_info=True,
                )
                return True
            current_major_plover_version = int(__version__.split(".")[0])
            return current_major_plover_version < parsed_unsupported_plover_version
        else:
            return True

    def update(self):
        try:
            available_plugins = global_registry.list_plugins()
        except Exception:
            log.error(
                "Failed to fetch list of available plugins from PyPI", exc_info=True
            )
            return

        session = CachedFuturesSession()
        try:
            unsupported_plugins_dict = (
                session.get(UNSUPPORTED_PLUGINS_URL).result().json()
            )
        except Exception:
            log.warning(
                "Failed to fetch list of unsupported plugins, assuming all plugins are supported",
                exc_info=True,
            )

        for name, metadata in available_plugins.items():
            pkg = self._packages.get(name)
            if pkg is None:
                pkg = PackageState(name, available=metadata)
                self._packages[name] = pkg
            else:
                pkg.available = metadata
                if (
                    pkg.current
                    and pkg.current.version is not None
                    and pkg.current.parsed_version < pkg.latest.parsed_version
                ):
                    pkg.status = "outdated"
            if pkg.status != "installed" and not self.is_plugin_supported(
                pkg, unsupported_plugins_dict
            ):
                pkg.status = "unsupported"

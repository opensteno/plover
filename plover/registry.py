from collections import namedtuple

from importlib.metadata import entry_points, PackageNotFoundError

from plover.oslayer.config import PLUGINS_PLATFORM
from plover import log


class Plugin:
    def __init__(self, plugin_type, name, obj):
        self.plugin_type = plugin_type
        self.name = name
        self.obj = obj
        self.__doc__ = obj.__doc__ or ""

    def __str__(self):
        return f"{self.plugin_type}:{self.name}"


PluginDistribution = namedtuple("PluginDistribution", "dist plugins")


class Registry:
    PLUGIN_TYPES = (
        "command",
        "dictionary",
        "extension",
        "gui",
        "gui.qt.machine_option",
        "gui.qt.tool",
        "machine",
        "macro",
        "meta",
        "system",
    )

    def __init__(self, suppress_errors=True):
        self._plugins = {}
        self._distributions = {}
        self._suppress_errors = suppress_errors
        for plugin_type in self.PLUGIN_TYPES:
            self._plugins[plugin_type] = {}

    def register_plugin(self, plugin_type, name, obj):
        plugin = Plugin(plugin_type, name, obj)
        self._plugins[plugin_type][name.lower()] = plugin
        return plugin

    def register_plugin_from_entrypoint(self, plugin_type, entrypoint):
        log.info("%s: %s (from %s)", plugin_type, entrypoint.name, entrypoint.group)
        try:
            obj = entrypoint.load()
        except Exception:
            log.error(
                "error loading %s plugin: %s (from %s)",
                plugin_type,
                entrypoint.name,
                entrypoint.value,
                exc_info=True,
            )
            if not self._suppress_errors:
                raise
        else:
            plugin = self.register_plugin(plugin_type, entrypoint.name, obj)
            # Keep track of distributions providing plugins.
            dist_id = entrypoint.group
            dist = self._distributions.get(dist_id)
            if dist is None:
                dist = PluginDistribution(entrypoint.group, set())
                self._distributions[dist_id] = dist
            dist.plugins.add(plugin)

    def get_plugin(self, plugin_type, plugin_name):
        return self._plugins[plugin_type][plugin_name.lower()]

    def list_plugins(self, plugin_type):
        return sorted(self._plugins[plugin_type].values(), key=lambda p: p.name)

    def list_distributions(self):
        return [dist for _, dist in sorted(self._distributions.items())]

    def update(self):
        # Is support for the QT GUI available?
        try:
            qt_entry_points = entry_points(group="plover.gui")
            has_gui_qt = any(ep.name == "qt" for ep in qt_entry_points)
        except PackageNotFoundError:
            has_gui_qt = False
        # Register available plugins.
        for plugin_type in self.PLUGIN_TYPES:
            if plugin_type.startswith("gui.qt.") and not has_gui_qt:
                continue
            entrypoint_type = f"plover.{plugin_type}"
            for entrypoint in entry_points(group=entrypoint_type):
                if "gui_qt" in entrypoint.extras and not has_gui_qt:
                    continue
                self.register_plugin_from_entrypoint(plugin_type, entrypoint)
            if PLUGINS_PLATFORM is None:
                continue
            entrypoint_type = f"plover.{PLUGINS_PLATFORM}.{plugin_type}"
            for entrypoint in entry_points(group=entrypoint_type):
                self.register_plugin_from_entrypoint(plugin_type, entrypoint)


registry = Registry()

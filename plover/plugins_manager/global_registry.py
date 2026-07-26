from collections import defaultdict

from packaging.utils import canonicalize_name

from plover.plugins_manager.package_index import find_plover_plugins_releases
from plover.plugins_manager.plugin_metadata import PluginMetadata


def list_plugins():
    plugins = defaultdict(list)
    for release in find_plover_plugins_releases():
        release_info = release["info"]
        plugin_metadata = PluginMetadata.from_dict(release_info)
        plugins[canonicalize_name(plugin_metadata.name)].append(plugin_metadata)
    plugins = {name: sorted(versions) for name, versions in plugins.items()}
    return plugins

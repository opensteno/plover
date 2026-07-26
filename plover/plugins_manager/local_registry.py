from collections import defaultdict
from importlib.metadata import distributions

from pkginfo.distribution import Distribution as Metadata

from plover import log
from plover.plugins_manager.plugin_metadata import PluginMetadata


def list_plugins():
    plugins = defaultdict(list)

    # Iterate over all installed distributions
    for dist in distributions():
        if dist.metadata["Name"].lower() == "plover":
            continue

        # Check if any entry point group starts with 'plover.'
        if not any(ep.group.startswith("plover.") for ep in dist.entry_points):
            continue

        # Determine the metadata entry type
        metadata_entry = "METADATA" if dist.files else "PKG-INFO"

        # Check if the distribution has metadata
        try:
            metadata = Metadata()
            metadata.parse(dist.read_text(metadata_entry))
        except (KeyError, FileNotFoundError):
            log.warning(
                "ignoring distribution (missing metadata): %s", dist.metadata["Name"]
            )
            continue

        # Create PluginMetadata from the parsed metadata
        plugin_metadata = PluginMetadata.from_dict(
            {attr: getattr(metadata, attr, "") for attr in PluginMetadata._fields}
        )
        plugins[dist.metadata["Name"].lower()].append(plugin_metadata)

    # Sort and return plugins
    return {name: sorted(versions) for name, versions in plugins.items()}

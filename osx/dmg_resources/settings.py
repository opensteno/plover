# -*- coding: utf-8 -*-

import plistlib
import os.path

# `defines` is injected by dmgbuild; default to empty for linters.
defines = globals().get("defines", {})

application = defines.get("app", "./dist/Plover.app")
appname = os.path.basename(application)


def icon_from_app(app_path):
    plist_path = os.path.join(app_path, "Contents", "Info.plist")
    with open(plist_path, "rb") as plist_file:
        plist = plistlib.load(plist_file)
    icon_name = plist["CFBundleIconFile"]
    icon_root, icon_ext = os.path.splitext(icon_name)
    if not icon_ext:
        icon_ext = ".icns"
    icon_name = icon_root + icon_ext
    return os.path.join(app_path, "Contents", "Resources", icon_name)


format = defines.get("format", "UDBZ")

# Files to include
files = [application]

# Symlinks to create
symlinks = {"Applications": "/Applications"}

# Volume icon
badge_icon = icon_from_app(application)

# Where to put the icons
icon_locations = {appname: (114, 244), "Applications": (527, 236)}

background = "osx/dmg_resources/background.png"

show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False

# Window position in ((x, y), (w, h)) format
window_rect = ((100, 100), (640, 380))

default_view = "icon-view"
show_icon_preview = False
include_icon_view_settings = "auto"
include_list_view_settings = "auto"

arrange_by = None
grid_offset = (0, 0)
grid_spacing = 50
scroll_position = (0, 0)
label_pos = "bottom"
text_size = 16
icon_size = 86

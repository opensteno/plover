# v5.2.0 (2026-02-01)


## Features

### Linux

- Support determining keyboard layout from Wayland with the `wayland-auto` layout. (#1807)
- Avoid unnecessary rapid modifier key press/release while typing. (#1810)

### macOS

- Add appearance configuration option. (#1786)

### Windows

- Add appearance configuration option. (#1786)

## Bugfixes

### Core

- Fix a corner case in `plover -s (script)`. (#1803)

### User Interface

- Fix default window sizes and extensions config table. (#1789)
- Update Thea's name and email. (#1792)
- Remove broken use_timeout checkbox in serial options. (#1793)
- Make the plugin manager handle some exceptional cases. (#1802)

### macOS

- Hide the Start Minimized setting on macOS due to bug in macOS 26. (#1788)

## API

### Core

- Migrate HID library to cython-hidapi. (#1812)

# v5.1.0 (2025-11-04)


## Features

### Core

- Add support for Plover HID protocol based on plover-machine-hid plugin by dnaq. (#1777)

### User Interface

- Dynamically update individual status icons while loading dictionaries. (#1400)

### macOS

- Add code signing and notarization for macOS app. (#1769)

## Bugfixes

### Core

- Update frontmatter in GPLv2 license file; no substantive change to the license (#1779)

## API

No significant changes.

# v5.0.0 (2025-09-10)


## Features

No significant changes.

## Bugfixes

No significant changes.

## API

No significant changes.

# v5.0.0rc1 (2025-09-02)


## Features

### Linux

- Refactor Uinput to use pipe instead of select with timeout. (#1760)
- Passthrough keyboard shortcuts. (#1761)
- Uinput: refactor initialization and cleanup. (#1765)

## Bugfixes

No significant changes.

## API

No significant changes.

# v5.0.0.dev3 (2025-07-14)


## Features

### Core

- Allow higher priority dictionaries to delete entries from others. (#1160)
- Improve orthography rules for `^ify` suffixes. (#1680)
- Reduce installer file size. (#1741)

### Linux

- Add dvorak keymap support for uinput users. (#1746)

## Bugfixes

### Core

- Allow uninstall of installed unsupported plugins. (#1739)
- Fix missing font family warnings. (#1740)

### Windows

- Do not consider extended scan codes in Windows keyboard capture. (#1357)

## API

No significant changes.

# v5.0.0.dev2 (2025-06-14)


## Features

### Core

- Integrate BuildResources into BuildUi to simplify UI plugin migration to Plover v5. (#1735)

## Bugfixes

### Core

- Fix installation of plugins via git URL. (#1733)

### Linux

- When inputting Unicode with uinput the code now uses space to finalize the Unicode character instead of enter. (#1731)

## API

No significant changes.

# v5.0.0.dev1 (2025-06-03)


## Features

### Core

- Integrate Plugins Manager and remove distribution plugins to simplify distribution of Plover. (#1601)
- Update integrated Python version to 3.13. (#1720)

### User Interface

- Support dark mode that follows the system settings. (#1601)

### Linux

- On linux wayland, warn if ibus or fcitx5 isn't running. (#1711)

### macOS

- Add universal installer for macOS on Intel and Apple silicon. (#1720)

## Bugfixes

### Linux

- Downgrade CI for building Linux AppImage to Ubuntu 22.04 to build against GLIBC 2.35. (#1718)
- Fixed keyboards with mouse control functionality not able to be detected in the uinput module. (#1724)
- Fix keys getting stuck if keys held when starting Plover and emulating keyboard with Uinput. (#1728)
- When using Uinput, fix devices being disabled upon exceptions. (#1729)

### macOS

- Fix notifications for newer macOS versions. (#1601)

## API

### Breaking Changes

- Update UI from PyQt5 to PySide6. (#1601)

# v4.0.0 (2025-02-18)


## Features

- Same as `v4.0.0rc5`
- See [NEWS.md](https://github.com/openstenoproject/plover/blob/main/NEWS.md) for the features included in the `v4.0.0.dev` and `v4.0.0rc` versions.

# v4.0.0rc5 (2025-02-10)


## Features

### User Interface

- Renamed the 'Scan' button in the serial port configuration window to 'Refresh', to (hopefully) more accurately convey that it simply lists all available serial ports. (#1640)
- Added a button to the Plugins Manager for installing plugins via Git URL. (#1700)

### Linux

- Added keyboard emulation and capture using uinput, compatible with X11, Wayland and anything else on linux and bsd. (#1679)

## Bugfixes

### Windows

- Fixed backspace scancode and swapped page up/down. (#1697)

## API

### New

- Renamed the `=retrospective_*` macros to simply `=retro_*`. The previous names are retained for backwards compatibility, but are now deprecated. (#1639)

# v4.0.0rc4 (2025-02-09)


- *Skipped for technical reasons.*


# v4.0.0rc3 (2025-02-09)


- *Skipped for technical reasons.*


# v4.0.0rc2 (2023-09-28)



## Features

### Core

- Added a configurable delay between key presses, to accommodate applications that can't handle fast keyboard emulation. (#1633)

## Bugfixes

### Core

- Closes serial ports upon disconnection to ensure clean reconnections. (#1636)

### User Interface

- Update the tray icon to "disconnected" when a serial-over-USB machine is unplugged. (#1560)

## API

### Breaking Changes

- Dropped support for Python 3.7. (#1634)

### New

- Introduces the `GenericKeyboardEmulation` interface which automatically handles output delay. (#1633)


# v4.0.0rc1 (2023-09-26)



## Features

### Core

- updated config to use tox4 (#1592)
- Implement first-up chord send for keyboard machine. (#1611)

### User Interface

- Added Traditional Chinese (zh-TW) translation. (#1404)

### Linux

- Update GitHub Actions from Ubuntu 18.04 to 22.04. (#1597)

### macOS

- Update GitHub Actions from macOS 10.15 to 12. (#1598)
- Changes the Plover icon on macOS to match Big Sur-style icons. (#1632)

### Windows

- Update GitHub Actions from Windows 2019 to 2022. (#1598)

## Bugfixes

### User Interface

- Fix "add translation" dialog ignoring the stylesheet's background color for the translation and stroke text. (#1571)

### Windows

- Fixed an issue which caused tests to fail on windows due to case sensitive filepaths. (#1599)

## API

No significant changes.


# v4.0.0.dev12 (2022-08-09)

## Features

### User Interface

- Show detailed information about each available serial port in the machine configuration dialog. (#1510)
- Add support for styling the Qt GUI: automatically load and apply a custom stylesheet from `plover.qss` (in the configuration directory) when present. (#1514)
- Capture and log Qt messages. (#1534)
- Change the paper tape / suggestions widget selection mode to "extended" (allow selecting multiple items, support shift/control), and allow copying the current selection to clipboard using the standard copy shortcut. (#1539)

### Linux

- Use `/dev/serial/by-id/xxxx` links for each available serial port in the machine configuration dialog. (#1510)

## Bugfixes

### Core

- Fix possible exception when calling `Engine.clear_translator_state(undo=True)`. (#1547)

### User Interface

- Fix "add translation" dialog "Ok" button not being enabled when the strokes field is automatically populated from the latest untranslate. (#1527)
- Fix `{PLOVER:ADD_TRANSLATION}` implementation when using the headless GUI (`-g none`). (#1546)

### Linux

- Fix fallback to Qt if the D-Bus log handler cannot be initialized. (#1545)

### Windows

- Fix some key combinations being sent incorrectly. (#1274)

## API

### Breaking Changes

- Drop support for Python 3.6. (#1538)


# v4.0.0.dev11 (2022-05-15)

## Features

### Core

- Switch to `plover_stroke` for better steno handling: faster and stricter. (#1362, #1417, #1452)
- New faster and improved RTF/CRE parser. (#1364, #1365)
- Correctly handle formatting currency with thousands separator(s): `23,000.15{:retro_currency:$c}` => `$23,000.15`. (#1391)
- Improve “English stenotype” system compatibility with RTF/CRE spec: support arbitrary placement of the number sign when parsing steno (e.g. `18#`, `#18`, and `1#8` are all valid and equivalent). (#1491)
- Improve translation stage: cut down on unnecessary / duplicate dictionary lookups. (#1513)

### User Interface

- Improve accessibility:
  - Disable tab-key navigation in tables, so focusing a table does not lock global tab-key navigation to it.
  - Remove some container widgets, tweak focus rules to avoid extra unnecessary steps when using tab-key navigation (like selecting the dictionaries widget outer frame).
  - In form layouts, link each widget to its label (like each option in the configuration dialog).
  - Set the accessible name / description of focusable widgets.
  - Use lists for the dictionaries widget, suggestions widget, and the paper tape. (#1308, #1332, #1434, #1451)
- Show a message when hiding to tray. (#1333)
- Improved steno handling:
  - validate inputs in the "add translation" dialog and dictionary editor
  - sort on steno order in the dictionary editor, and signal invalid steno entries (#1362, #1501)

### Linux

- Improve D-Bus logger implementation. (#1496)
- Add `WM_CLASS` property to windows (`WM_CLASS(STRING) = "plover", "Plover"`). (#1498)

## Bugfixes

### Core

- New reworked RTF/CRE support:
  - correctly handle multi-lines mappings
  - detect syntax errors (with recovery)
  - use `\n\n` for new paragraphs (instead of non-undoable `{#Return}{#Returns}`)
  - similarly, use `\t` and `\n` for `\tab` and `\line`
  - correctly escape `{}\` on save
  - use custom ignored groups for Plover macros and metas
  - use groups to improve round-tripping affixes (so there's no ambiguity when parsing back, e.g. `{^in^}fix` -> `{\cxds in \cxds}fix` instead of `\cxds in\cxds fix`) (#1364, #1365)
- Fixed a memory leak on reloading externally modified dictionaries. (#1375)
- Do not discard existing filters on dictionaries reload. (#1388)
- Fix engine's running state: make sure the translator' state is empty when enabling output for the first time. (#1504)
- Fix exit handlers not getting always executed. (#1507)
- Fix `StenoDictionaryCollection.longest_key` implementation: ignore disabled dictionaries! (#1512)

### Dictionaries

- Fix `KHR*PB` stroke to not be misinterpreted as a command. (#1463)

### User Interface

- Speedup dictionary editor startup (avoid duplicate sort). (#1351)
- Updated Spanish translation. (#1420)
- Updated French translation. (#1422)
- Speedup suggestions widget implementation: should noticeably improve performance when there's a large scrollback. (#1481)

### Windows

- Drop launch option from installer's final page: avoid possible issues (e.g. permission errors with the controller's pipe) because Plover was run as admin. (#1495)
- Fix notifications behavior: no persistent duplicated icons (one for each notification). (#1507, #1508)

## API

### Breaking Changes

- The custom `test` command implementation provided by `plover_build_utils.setup.Test` has been removed:
  - support for it on setuptools' side has been deprecated since version 41.5.0
  - the custom handling of arguments conflicts with the use of some pytest options (e.g. `-m MARKEXPR`)
  - the workaround for pytest cache handling is not necessary anymore (#1332)
- The `steno` helpers (`Stroke` class, `normalize_stroke`, …) now raise a `ValueError` exception in case of invalid steno. (#1362, #1501)
- The support for `StenoDictionary` and `StenoDictionaryCollection` longest key callbacks is gone, use the `longest_key` properties instead. (#1375)


# v4.0.0.dev10 (2021-06-19)

## Features

### Core

- Change behavior when launching Plover and an existing instance is already running: send a `focus` command to the existing instance (to show, raise, and focus the main window). Additionally, a new `plover_send_command` executable/script can be used to send other commands. (#1284)
- Add FreeBSD/OpenBSD support. (#1306)

### Linux

- The oldest Ubuntu LTS release supported by the AppImage is now Ubuntu Bionic (18.04). (#1329)

## Bugfixes

### Core

- Fix 2 corner cases when handling dictionaries:
  - If the class implementation is marked as read-only, then loading from a writable file should still result in a read-only dictionary.
  - Don't allow `clear` on a read-only dictionary. (#1302)
- Don't try to start missing extensions. (#1313)

### User Interface

- Correctly restore a window if it was minimized: fix the `focus` command, and activating a tool window. (#1314)

## API

### Breaking Changes

- The `Engine` constructor now takes an additional parameter: the controller. (#1284)

### New

- Add some new helpers to `plover_build_utils.testing`:
  - `dictionary_test`: torture tests for dictionary implementations.
  - `make_dict`: create a temporary dictionary.
  - `parametrize`: parametrize helper for tracking test data source line numbers. (#1302)


# v4.0.0.dev9 (2021-04-22)

## Features

### Core

- A new `SET_CONFIG` command can be used to change the configuration with a stroke, e.g.:
  ``` json
  "O*EP": "{PLOVER:SET_CONFIG:'translation_frame_opacity':100}",
  "TR*PB": "{PLOVER:SET_CONFIG:'translation_frame_opacity':0}",
  ```
  to change the opacity of the "Add Translation" dialog on the fly. (#989)
- Speed up loading dictionaries. (#1022)
- Be more restrictive with macro names: only accept valid identifier, so for example `==` is not handled like a macro anymore. (#1025)
- Ignore case when processing builtin commands / metas. (#1069)
- Add user friendly names for built-in metas, e.g.: `{:retro_case:cap_first_word}`, `{:retro_currency:$c}`, `{:attach:attach^}`, etc... (#1069)
- Improve orthography rules. (#1092, #1212)
- The configuration is now automatically saved on change, rather than on exit. (#1123)
- Add prefix strokes (syntax `/STROKE`) that will only translate if they are at the beginning of a word. Word endings can be specified with `{:word_end}` or `{$}`. (#1157)
- Add support for conditional formatting (based on the text following a translation): `{=REGEXP/TRANSLATION_IF_FOLLOWING_TEXT_MATCH/TRANSLATION_IF_NOT}` or `{:if_next_matches:REGEXP/TRANSLATION_IF_FOLLOWING_TEXT_MATCH/TRANSLATION_IF_NOT}`. (#1158)

### User Interface

- Add menu entry for opening the configuration directory ("File" =&gt; "Open config folder"). (#981)
- Automatically focus the input field and pre-select the previous input when the lookup window is activated. (#1009)
- Improve the configuration dialog for serial machines: automatically scan available ports and default to the first one. (#1036)
- The "Add translation" stroke lookup now returns entries for all enabled dictionaries and is debounced to improve performance. (#1084)
- Added translation into Spanish. (#1165)
- A new command, `{PLOVER:SUGGESTIONS}`, is available to open the suggestions window with a steno stroke. (#1184)
- Add support for saving dictionaries:
  - save a copy of each selected dictionary
  - merge the selected dictionaries into a new one
  - both operations support converting to another format (#1244)
- Added translation into Dutch. (#1264)
- Added Italian translation. (#1268)

### Linux

- The distribution Python is now built with optimization. (#1068)
- Expand the list of supported key names in key combos to include non-US specific keys (like `ISO_Level3_Shift`). (#1082)
- The default configuration directory on Linux is now `~/.config/plover` (`~/.local/share/plover` is still supported for backward compatibility). (#1123)

### macOS

- The minimum version supported by the macOS bundle is now 10.13 (High Sierra). (#1156)

### Windows

- The distribution is now 64bits. (#1023)

## Bugfixes

### Core

- Fix retrospective insert space macro when the previous translation involved suffix keys. (#995)
- Fix updating a dictionary mapping: ensure reverse lookups data stays consistent. (#1022)
- Fix keymap validation: properly fallback to default keymap when invalid. (#1065)
- Fix lookups by translation: do not ignore lower priority dictionaries when a match is found in a higher priority one. (#1066)
- Fix wordlist support for system plugins: try loading from the system dictionaries root (and not Plover assets directory). (#1116)
- Configuration save operations are now atomic. (#1123)
- Fix forced lowercasing of all engine command arguments. (#1139)
- Fix implicit hyphen handling with numbers only strokes on some theories (e.g. Melani). (#1159)
- Fix unbounded memory use in the lookup functions used by the Suggestions window. (#1188)

### Dictionaries

- Fix a number of invalid entries in the main dictionary. (#1038)
- Tweak orthographic rules so "reduce/{^ability}" result in "reducibility" instead of "reducability". (#1096)

### User Interface

- Fix a possible crash on close when opening a read-only dictionary in the editor. (#897)
- Fix possible crash when changing machine parameters in the configuration dialog. (#1041)
- Fix internationalization of machine types in the configuration dialog. (#1061)
- Fix tools shortcuts. (#1062)
- Fix crashes due to GUI exceptions reaching the event loop. (#1135)
- Fix an exception caused by an incorrect assertion that would prevent enabling and disabling extension plugins if they weren't on the first row. (#1171)
- Fix changes to the list of enabled extension plugins not being saved to the configuration file. (#1230)
- Fix missing translations. (#1248)

### Linux

- Fix output capitalization issue. (#1153)
- Fix a race condition that may freeze Plover while toggling with keyboard input machine. (#1163)

### macOS

- Fix an issue where permissions had to be granted to "env" on macOS Catalina 10.15. (#1152)
- Mac notifications no longer have "Plover" as their title. (#1271)

### Windows

- Fix Unicode characters output. (#991)
- Fix installer's icon. (#1027)

## API

### Breaking Changes

- `StenoDictionaryCollection.casereverse_lookup` now returns a `set` (instead of a `list`). (#1066)
- The API for providing i18n support as been changed: see `doc/i18n.md` for more information. (#1258)

### New

- `plover_build_utils.setup` now provides a new `babel_options` helper for configuring Babel for i18n support. (#1258)


# v4.0.0.dev8+66.g685bd33 (2018-07-02)

## Features

### Dictionaries

- Use `AOE` instead of `E` for prefix "e". (#951)
- Quality of Life changes/additions to the dictionaries. (#959, #960)

### User Interface

- Add tooltips to dictionary status icons. (#962)

## Bugfixes

### Core

- Fix issues when output is set to "Spaces After". (#965)

### macOS

- Fix portable mode. (#932)

### Windows

- Add missing C++ redistributable DLL to the installer. (#957)
- Fix emoji output. (#942)

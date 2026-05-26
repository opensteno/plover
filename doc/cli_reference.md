# Command Line Reference

This page describes all the options available to run Plover from the command
line. The command is available under slightly different names on each platform,
relative to your installation directory:

- Windows: `C:\Program Files (x86)\Open Steno Project\Plover 4.0.0\plover_console.exe`
- macOS: `/Applications/Plover.app/Contents/MacOS/Plover`
- Linux: `plover.AppImage`

All of the above commands will be referred to as `plover` below.

```{program} plover
```

```{option} --help
Display the help text and then exit.
```

```{option} --version
Display the running Plover version and then exit.
```

````{option} -g <gui>
Specify the GUI system to use. The options are as follows:

```{describe} qt
Run the built-in Qt-based GUI. This is the default value.
```

```{describe} none
Run Plover headless, i.e. without a GUI. You'll only be able to control
Plover from the command line or with steno commands.
````

```{option} -l <level>, --log-level <level>
Change the minimum level of logs being shown on standard output. Options
are `debug`, `info`, `warning`, and `error`. By default, no logs
are displayed.
```

```{option} -s <script>, --script <script>
Use another console script as the main entrypoint. This passes the
remainder of the command line arguments to the console script. For example,
to run the plugin installer:

    plover -s plover_plugins

Pass `-s` without an argument to show the list of console scripts.
```

(plugin-installer)=

## Plugin Installer

The plugin installer can be accessed through the `plover_plugins` console
script:

    plover -s plover_plugins

This is essentially a wrapper around `pip`; you can run commands to install
and remove packages just like on a normal Python installation. For example, to
install and uninstall the `plover-treal` plugin:

    plover -s plover_plugins install plover-treal
    plover -s plover_plugins uninstall plover-treal

To list all of the plugins available on your system:

    plover -s plover_plugins list

To install a plugin you are working on locally:

    cd plover_myplugin
    plover -s plover_plugins install -e .

```{note}
Some users have had issues loading the plugin list with the Plugin Manager;
this seems to have something to do with an outdated version of another
package. This can be fixed with the following command:

    plover -s plover_plugins install --disable-pip-version-check --upgrade Pygments
```

(send-command)=

## Sending Commands

The `plover_send_command` console script can be used to send commands to an
existing Plover instance:

    plover -s plover_send_command

It takes the command name and parameters as an argument, written as they would
be in a dictionary definition. For example, to send the command
`{plover:toggle}`, you can invoke this script as follows:

    plover -s plover_send_command toggle

The following built-in commands are available:

```{describe} resume
Enable steno output.
```

```{describe} suspend
Disable steno output.
```

```{describe} toggle
Toggle steno output on or off.
```

```{describe} quit
Quit Plover.
```

```{describe} focus
Bring the Plover window to the foreground.
```

```{describe} configure
Open the configuration dialog.
```

```{describe} add_translation
Open the Add Translation dialog.
```

```{describe} lookup
Open the Lookup dialog.
```

```{describe} suggestions
Open the Suggestions dialog.
```

```{describe} reconnect_machine
Disconnect and reconnect the current machine. Equivalent to pressing the
*Reconnect* button in the main window.
```

```{describe} reload_dictionaries
Reload all dictionaries from disk without resetting the machine connection.
Useful for picking up changes made to dictionary files outside of Plover.
```

````{describe} set_config:<key>:<value>[,<key>:<value>,...]
Set one or more configuration options. Keys and string values should be
quoted with single quotes. For example:

    plover -s plover_send_command "set_config:'translation_frame_opacity':90"
````

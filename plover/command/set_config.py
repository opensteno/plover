import ast


def set_config(engine, cmdline):
    """
    Set one or more Plover config options upon executing a stroke pattern.

    Syntax:
    {PLOVER:SET_CONFIG:option:value}
    {PLOVER:SET_CONFIG:option1:value1,option2:value2,...}

    Example usage:
    "O*EP":   "{PLOVER:SET_CONFIG:'translation_frame_opacity':100}",
    "STA*RT": "{PLOVER:SET_CONFIG:'start_attached':True,'start_capitalized':True}",

    Be careful with nested quotes. Plover's JSON dictionaries use double quotes
    by default, so use single quotes for config option names and other strings.
    """
    # Each config setting can be processed as a key:value pair in a dict.
    # The engine.config property setter will update all settings at once.
    engine.config = _cmdline_to_dict(cmdline)


def _cmdline_to_dict(cmdline):
    """Add braces and parse the entire command line as a Python dict literal."""
    try:
        opt_dict = ast.literal_eval("{" + cmdline + "}")
        assert isinstance(opt_dict, dict)
        return opt_dict
    except (AssertionError, SyntaxError, ValueError) as e:
        raise ValueError(
            f'Bad command string "{cmdline}" for PLOVER:SET_CONFIG.\n'
            + "See for reference:\n\n"
            + set_config.__doc__
        ) from e

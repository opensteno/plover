from plover.formatting import SPACE, Case


def meta_mode(ctx, cmdline):
    """
    cmdline should be:

        caps: UPPERCASE
        lower: lowercase
        title: Title Case
        camel: titlecase, no space, initial lowercase
        snake: underscore_space
        reset_space: Space resets to ' '
        reset_case: Reset to normal case
        set_space:xy: Set space to xy
        reset: Reset to normal case, space resets to ' '
    """
    args = cmdline.split(":", 1)
    mode = args.pop(0).lower()
    action = ctx.copy_last_action()
    if mode == "set_space":
        action.space_char = args[0] if args else ""
        return action
    # No argument allowed for other mode directives.
    if args:
        raise ValueError(f"{cmdline!r} is not a valid mode")
    if mode == "caps":
        action.case = Case.UPPER
    elif mode == "title":
        action.case = Case.TITLE
    elif mode == "lower":
        action.case = Case.LOWER
    elif mode == "snake":
        action.space_char = "_"
    elif mode == "camel":
        action.case = Case.TITLE
        action.space_char = ""
        action.next_case = Case.LOWER_FIRST_CHAR
    elif mode == "reset":
        action.space_char = SPACE
        action.case = None
    elif mode == "reset_space":
        action.space_char = SPACE
    elif mode == "reset_case":
        action.case = None
    else:
        raise ValueError(f"{cmdline!r} is not a valid mode")
    return action

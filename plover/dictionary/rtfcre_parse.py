import re
import sys
from collections import deque

from rtf_tokenize import RtfTokenizer

from plover import log


class RtfParseError(Exception):
    def __init__(self, lnum, cnum, fmt, *fmt_args):
        msg = f"line {lnum + 1}, column {cnum + 1}: {fmt % fmt_args}"
        super().__init__(msg)


class BadRtfError(Exception):
    def __init__(self, fmt, *fmt_args):
        msg = fmt % fmt_args
        super().__init__(msg)


def finalize_translation(text):
    if not text:
        return text
    # caseCATalyst doesn't put punctuation in \cxp: treat any isolated
    # punctuation at the beginning of the translation as special.
    if text[0] in ".?!:;," and text[1:] in ("", " "):
        return "{" + text[0] + "}" + text[1:]
    left_ws = len(text) - len(text.lstrip())
    if left_ws > 1:
        text = "{^" + text[:left_ws] + "^}" + text[left_ws:]
    right_ws = len(text) - len(text.rstrip())
    if right_ws > 1:
        text = text[:-right_ws] + "{^" + text[-right_ws:] + "^}"
    return text


def parse_rtfcre(text, normalize=lambda s: s, skip_errors=True):
    not_text = r"\{}"
    style_rx = re.compile("s[0-9]+")
    unicode_rx = re.compile("u-?[0-9]+")
    uc_rx = re.compile("uc[0-9]+")
    tokenizer = RtfTokenizer(text)
    next_token = tokenizer.next_token
    rewind_token = tokenizer.rewind_token
    # Check header.
    if next_token() != "{" or next_token() != r"\rtf1":
        raise BadRtfError("invalid header")
    # Parse header/document.
    g_destination, g_text = "rtf1", ""
    # Number of fallback characters written after each `\uN` escape,
    # per group. 1 is the RTF default.
    g_uc = 1
    # Number of fallback characters still to be skipped.
    skip_count = 0
    group_stack = deque()
    stylesheet = {}
    steno = None
    while True:
        token = next_token()
        # EOF.
        if token is None:
            err = RtfParseError(
                tokenizer.lnum, tokenizer.cnum, "unexpected end of file"
            )
            if not skip_errors:
                raise err
            log.error("%s", err)
            break
        # Group start.
        if token == "{":
            # Always rewind the last token?
            rewind = False
            # Is it an ignored group?
            is_ignored = False
            destination = None
            token = next_token()
            # Ignored?
            if token == r"\*":
                token = next_token()
                is_ignored = True
            # Destination?
            if token[0] == "\\":
                destination = token[1:]
                # Steno.
                if destination == "cxs":
                    if group_stack:
                        err = RtfParseError(
                            tokenizer.lnum,
                            tokenizer.cnum,
                            "starting new mapping, but previous is unfinished",
                        )
                        if not skip_errors:
                            raise err
                        log.error("%s", err)
                        # Simulate missing group end(s).
                        assert group_stack[0][0] == "rtf1"
                        rewind_token(token)
                        if is_ignored:
                            rewind_token(r"\*")
                        rewind_token("{")
                        for __ in range(len(group_stack)):
                            rewind_token("}")
                        continue
                    if steno is not None:
                        yield normalize(steno), finalize_translation(g_text)
                        steno = None
                    is_ignored = False
                    # Reset text.
                    g_text = ""
                elif destination in {
                    # Fingerspelling.
                    "cxfing",
                    # Stenovations extensions...
                    "cxsvatdictflags",
                    # Plover macro.
                    "cxplovermacro",
                    # Plover meta.
                    "cxplovermeta",
                }:
                    is_ignored = False
                elif style_rx.fullmatch(destination):
                    pass
                else:
                    # In the case of e.g. `{\par...`,
                    # `\par` must be handled as a
                    # control word.
                    rewind = True
            else:
                rewind = True
            if is_ignored:
                # Skip ignored content.
                stack_depth = 1
                while True:
                    token = next_token()
                    if token is None:
                        err = RtfParseError(
                            tokenizer.lnum, tokenizer.cnum, "unexpected end of file"
                        )
                        if not skip_errors:
                            raise err
                        log.error("%s", err)
                        break
                    if token == "{":
                        stack_depth += 1
                    elif token == "}":
                        stack_depth -= 1
                        if not stack_depth:
                            break
                if stack_depth:
                    break
                continue
            group_stack.append((g_destination, g_text, g_uc))
            g_destination, g_text = destination, ""
            skip_count = 0
            if rewind:
                rewind_token(token)
            continue
        # Group end.
        if token == "}":
            if not group_stack:
                token = next_token()
                if token is None:
                    # The end...
                    break
                err = RtfParseError(
                    tokenizer.lnum,
                    tokenizer.cnum,
                    "expected end of file, got: %r",
                    token[0],
                )
                if not skip_errors:
                    raise err
                log.error("%s", err)
                rewind_token(token)
                continue
            # Steno.
            if g_destination == "cxs":
                steno = g_text
                text = ""
            # Punctuation.
            elif g_destination == "cxp":
                text = g_text.strip()
                if text in {".", "!", "?", ",", ";", ":"}:
                    text = "{" + text + "}"
                elif text == "'":
                    text = "{^'}"
                elif text in ("-", "/"):
                    text = "{^" + text + "^}"
                else:
                    # Show unknown punctuation as given.
                    text = "{^" + g_text + "^}"
            # Stenovations extensions...
            elif g_destination == "cxsvatdictflags":
                if "N" in g_text:
                    text = "{-|}"
                else:
                    text = ""
            # Fingerspelling.
            elif g_destination == "cxfing":
                text = "{&" + g_text + "}"
            # Plover macro.
            elif g_destination == "cxplovermacro":
                text = "=" + g_text
            # Plover meta.
            elif g_destination == "cxplovermeta":
                text = "{" + g_text + "}"
            # Style declaration.
            elif (
                g_destination is not None
                and style_rx.fullmatch(g_destination)
                and group_stack[-1][0] == "stylesheet"
            ):
                stylesheet[g_destination] = g_text
            else:
                text = g_text
            g_destination, g_text, g_uc = group_stack.pop()
            skip_count = 0
            g_text += text
            continue
        # Control char/word.
        if token[0] == "\\":
            ctrl = token[1:]
            text = {
                # Ignore.
                "*": "",
                # Hard space.
                "~": "{^ ^}",
                # Non-breaking hyphen.
                "_": "{^-^}",
                # Escaped newline: \par.
                "": "\n\n",
                "\n": "\n\n",
                "\r": "\n\n",
                # Escaped characters.
                "\\": "\\",
                "{": "{",
                "}": "}",
                "-": "-",
                # Line break.
                "line": "\n",
                # Paragraph break.
                "par": "\n\n",
                # Tab.
                "tab": "\t",
                # Force Cap.
                "cxfc": "{-|}",
                # Force Lower Case.
                "cxfl": "{>}",
            }.get(ctrl)
            if text is not None:
                if skip_count:
                    skip_count -= 1
                else:
                    g_text += text
            # Unicode escape.
            elif unicode_rx.fullmatch(ctrl):
                code_unit = int(ctrl[1:]) & 0xFFFF
                if (
                    0xDC00 <= code_unit < 0xE000
                    and g_text
                    and 0xD800 <= ord(g_text[-1]) < 0xDC00
                ):
                    # Low surrogate: combine with the preceding high one.
                    high = ord(g_text[-1]) - 0xD800
                    g_text = g_text[:-1] + chr(
                        0x10000 + (high << 10) + (code_unit - 0xDC00)
                    )
                else:
                    g_text += chr(code_unit)
                skip_count = g_uc
            # Number of fallback characters following a unicode escape.
            elif uc_rx.fullmatch(ctrl):
                g_uc = int(ctrl[2:])
            # Delete Spaces.
            elif ctrl == "cxds":
                token = next_token()
                if token is None or token[0] in not_text:
                    g_text += "{^}"
                    rewind_token(token)
                else:
                    text = token
                    token = next_token()
                    if token == r"\cxds":
                        # Infix
                        g_text += "{^" + text + "^}"
                    else:
                        # Prefix.
                        g_text += "{^" + text + "}"
                        rewind_token(token)
            # Delete Last Stroke.
            elif ctrl == "cxdstroke":
                g_text = "=undo"
            # Fingerspelling.
            elif ctrl == "cxfing":
                token = next_token()
                if token is None or token[0] in not_text:
                    err = RtfParseError(
                        tokenizer.lnum, tokenizer.cnum, "expected text, got: %r", token
                    )
                    if not skip_errors:
                        raise err
                    log.error("%s", err)
                    rewind_token(token)
                else:
                    g_text += "{&" + token + "}"
            elif style_rx.fullmatch(ctrl):
                # Workaround for caseCATalyst declaring
                # new styles without a preceding \par.
                if not g_text.endswith("\n\n"):
                    g_text += "\n\n"
                # Indent continuation styles.
                if stylesheet.get(ctrl, "").startswith("Contin"):
                    g_text += "    "
            continue
        # Text.
        text = token
        if skip_count:
            skipped = min(skip_count, len(text))
            skip_count -= skipped
            text = text[skipped:]
            if not text:
                continue
        token = next_token()
        if token == r"\cxds":
            # Suffix.
            text = "{" + text + "^}"
        else:
            rewind_token(token)
        g_text += text
    if steno is not None:
        yield normalize(steno), finalize_translation(g_text)


def main(todo, filename):
    with open(filename, "rb") as fp:
        text = fp.read().decode("cp1252")
    if todo == "tokenize":
        next_token = RtfTokenizer(text).next_token
        while next_token() is not None:
            pass
    elif todo == "parse":
        for __ in parse_rtfcre(text):
            pass
    elif todo == "dump_tokenize":
        tokenizer = RtfTokenizer(text)
        while True:
            token = tokenizer.next_token()
            if token is None:
                break
            print(f"{tokenizer.lnum + 1:3}:{tokenizer.cnum + 1:<3} {token!r}")
    elif todo == "dump_parse":
        for mapping in parse_rtfcre(text):
            print(mapping)
    else:
        raise ValueError(todo)


if __name__ == "__main__":
    assert len(sys.argv) == 3
    main(sys.argv[1], sys.argv[2])

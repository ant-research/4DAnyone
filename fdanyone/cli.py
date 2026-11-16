"""Validate public Fire command arguments before invoking application code."""

import inspect


def check_arguments(function, args):
    """Reject unused CLI tokens before Fire can start work."""

    def is_flag(arg):
        return arg.startswith("--") or (arg.startswith("-") and arg[1:2].isalpha())

    parameters = inspect.signature(function).parameters
    positional = {name for name, value in parameters.items() if value.kind == value.POSITIONAL_OR_KEYWORD}
    named, words = set(), []
    index = 0
    while index < len(args):
        arg = args[index]
        if is_flag(arg):
            name = arg.lstrip("-").split("=", 1)[0].replace("-", "_")
            matches = (
                [name] if name in parameters else [key for key in parameters if len(name) == 1 and key.startswith(name)]
            )
            if len(matches) != 1:
                raise SystemExit(f"Unknown or ambiguous option: {arg.split('=', 1)[0]}. See --help.")
            named.add(matches[0])
            if "=" not in arg:
                index += 1
                if index == len(args) or is_flag(args[index]):
                    raise SystemExit(f"Option {arg} needs a value. See --help.")
        else:
            words.append(arg)
        index += 1
    if len(words) > len(positional - named):
        raise SystemExit("Unexpected positional arguments. Quote paths containing spaces; see --help.")

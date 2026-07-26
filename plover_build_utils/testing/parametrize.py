import inspect

import pytest


def parametrize(tests, arity=None):
    """Helper for parametrizing pytest tests.

    Expects a list of lambdas, one per test. Each lambda must return
    the parameters for its respective test.

    Test identifiers will be automatically generated, from the test
    number and its lambda definition line (1.10, 2.12, 3.20, ...).

    If arity is None, the arguments being parametrized will be automatically
    set from the function's last arguments, according to the numbers of
    parameters for each test.

    """
    ids = []
    argvalues = []
    for n, t in enumerate(tests):
        line = inspect.getsourcelines(t)[1]
        ids.append(f"{n + 1}:{line}")
        argvalues.append(t())
    if arity is None:
        arity = len(argvalues[0])
    assert arity > 0

    def decorator(fn):
        argnames = [
            parameter.name
            for parameter in inspect.signature(fn).parameters.values()
            if parameter.default is inspect.Parameter.empty
        ][-arity:]
        if arity == 1:
            argnames = argnames[0]
        return pytest.mark.parametrize(argnames, argvalues, ids=ids)(fn)

    return decorator

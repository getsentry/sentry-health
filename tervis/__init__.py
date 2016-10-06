def __init():
    """Make sure we import everything to avoid stupid issues later on."""
    from .utils import iter_modules
    for module in iter_modules(__name__):
        try:
            __import__(module)
        except SyntaxError:
            # Since we have some python 3 exclusive modules, we just make
            # sure we silently don't import them
            pass

__init()
del __init

def __init():
    """Make sure we import everything to avoid stupid issues later on."""
    from tervis.utils import iter_modules
    for module in iter_modules(__name__):
        __import__(module)

__init()
del __init

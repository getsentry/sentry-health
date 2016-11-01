from tervis.operation import Operation
from tervis.dependencies import DependencyMount
from tervis.db import Database


class State(DependencyMount):
    db = Database('apiserver.auth_db')

    def __init__(self, op):
        DependencyMount.__init__(self, parent=op)


def test_basic(env):
    with Operation(env) as op:
        with State(op) as state:
            pass

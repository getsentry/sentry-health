import pickle
import base64
import binascii
from tervis.db import Database, meta
from tervis.dependencies import DependencyMount, DependencyDescriptor
from tervis.operation import CurrentOperation


metadata = meta.MetaData()
project_options = meta.Table('sentry_projectoptions', metadata,
    meta.Column('id', meta.BigInteger, primary_key=True),
    meta.Column('project_id', meta.BigInteger),
    meta.Column('key', meta.String(64)),
    meta.Column('value', meta.String)
)


def load_value(value):
    try:
        bytes = base64.b64decode(value)
    except binascii.Error:
        return None
    return pickle.loads(bytes, encoding='utf-8', errors='replace')


def dump_value(value):
    return base64.b64encode(pickle.dumps(value)).decode('ascii')


class ProjectOptions(DependencyDescriptor):
    scope = 'operation'

    def instanciate(self, op):
        return ProjectOptionsManager(op)


class ProjectOptionsManager(DependencyMount):
    db = Database(config='apiserver.project_db')
    op = CurrentOperation()

    def __init__(self, op):
        DependencyMount.__init__(self, parent=op)
        self.cache = {}

    async def get(self, name, project_id=None):
        key = (project_id, name)
        if key in self.cache:
            return self.cache[key]

        if project_id is None:
            project_id = self.op.project_id
            if project_id is None:
                self.cache[key] = None
                return None

        rv = await self.db.conn.execute(project_options.select()
            .where(
                (project_options.c.project_id == project_id) &
                (project_options.c.key == name)))
        row = await rv.fetchone()
        if row is not None:
            value = load_value(row.value)
        else:
            value = None
        self.cache[key] = value
        return value

    async def set_unsafe(self, name, value, project_id=None):
        key = (project_id, name)

        if project_id is None:
            project_id = self.op.project_id
            if project_id is None:
                raise RuntimeError('No project id available')

        serialized_value = dump_value(value)

        rv = await self.db.conn.execute(project_options.update()
            .where(
                (project_options.c.project_id == project_id) &
                (project_options.c.key == name)
            )
            .values(value=serialized_value))
        if rv.rowcount == 0:
            await self.db.conn.execute(project_options.insert()
                .values(value=serialized_value,
                        key=name,
                        project_id=project_id))
        self.cache[key] = value

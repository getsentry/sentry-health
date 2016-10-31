import sqlalchemy as _sa
from sqlalchemy import *


metadata = MetaData()


def Table(name, *args, **kwargs):
    return _sa.Table(name, metadata, *args, **kwargs)

"""Construct database connections at application entry points."""

from bmdynip.interface.DatabaseEnvironment import DatabaseEnvironment
from bmdynip.interface.DbMgr import DbMgr


def open_database() -> DbMgr:
    return DbMgr(DatabaseEnvironment.read())

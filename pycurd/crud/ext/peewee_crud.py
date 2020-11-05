import inspect
from dataclasses import dataclass
from typing import Any, Union, Dict, Type

import pypika
import typing

from pycurd.types import RecordMapping
from pycurd.crud.sql_crud import SQLCrud, PlaceHolderGenerator, SQLExecuteResult
from pycurd.error import DBException

if typing.TYPE_CHECKING:
    import peewee


@dataclass
class PeeweeCrud(SQLCrud):
    mapping2model: Dict[Type[RecordMapping], Union[str, Type['peewee.Model']]]
    db: Any

    def __post_init__(self):
        import peewee
        from playhouse.postgres_ext import ArrayField
        from playhouse.postgres_ext import BinaryJSONField
        from playhouse.mysql_ext import JSONField as MySQL_JSONField
        from playhouse.sqlite_ext import JSONField as SQLite_JSONField

        super().__post_init__()

        self._primary_keys = {}
        for k, v in self.mapping2model.items():
            if inspect.isclass(v) and issubclass(v, peewee.Model):
                self._primary_keys[k] = v._meta.primary_key.name

                for name, f in v._meta.fields.items():
                    if isinstance(f, ArrayField):
                        self._table_cache[k]['array_fields'].add(f.name)
                    elif isinstance(f, (BinaryJSONField, MySQL_JSONField, SQLite_JSONField)):
                        self._table_cache[k]['json_fields'].add(f.name)

        for k, v in self.mapping2model.items():
            if inspect.isclass(v) and issubclass(v, peewee.Model):
                self.mapping2model[k] = pypika.Table(v._meta.table_name)

    def get_placeholder_generator(self) -> PlaceHolderGenerator:
        import peewee

        if isinstance(self.db, peewee.SqliteDatabase):
            return PlaceHolderGenerator('?')
        elif isinstance(self.db, peewee.PostgresqlDatabase):
            return PlaceHolderGenerator('%s')
        elif isinstance(self.db, peewee.MySQLDatabase):
            return PlaceHolderGenerator('%s')
        else:
            raise Exception('unknown database: %s', self.db)

    async def execute_sql(self, sql: str, phg: PlaceHolderGenerator):
        import peewee
        try:
            if sql.startswith('INSERT INTO'):
                if isinstance(self.db, peewee.PostgresqlDatabase):
                    sql += ' RETURNING id'
                    r = self.db.execute_sql(sql, phg.values)
                    return SQLExecuteResult(r.fetchone()[0])
            return self.db.execute_sql(sql, phg.values)
        except Exception as e:
            self.db.rollback()
            raise DBException(*e.args)

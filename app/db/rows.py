from psycopg.rows import RowMaker


class Row(tuple):
    __slots__ = ()
    _cols: tuple = ()

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                return tuple.__getitem__(self, self._cols.index(key))
            except ValueError:
                raise IndexError(f"No item with that key: {key}") from None
        return tuple.__getitem__(self, key)

    def keys(self):
        return list(self._cols)


def _row_factory(cursor) -> RowMaker:
    cols = tuple((d.name for d in cursor.description)) if cursor.description else ()
    cls = type("Row", (Row,), {"_cols": cols, "__slots__": ()})
    return lambda values: cls(values)

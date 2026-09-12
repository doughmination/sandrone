import asyncio
from collections.abc import Iterator, Mapping, MutableMapping
from pathlib import Path
from typing import Any

from jpml import SUFFIX, JPConfig, JPError

from sandrone import config
from utils import cf

flushInterval = 30.0
versionKey = "version"

_databases: dict[Path, "DataBase"] = {}


def _asIds(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    ids: list[int] = []
    for item in value:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return ids


def _ordered(items: list[Any]) -> list[Any]:
    if all(isinstance(item, int) and not isinstance(item, bool) for item in items):
        return sorted(items)
    return items


class Field:
    def __init__(self, scope: "Scope", name: str) -> None:
        self.scope = scope
        self.name = name

    def __repr__(self) -> str:
        return f"<Field {self.scope.db.name}:{self.scope.label}.{self.name}>"

    # -- reads -----------------------------------------------------------

    def read(self, default: Any = None) -> Any:
        value = self.scope.data().get(self.name)
        return default if value is None else value

    def list(self) -> list[Any]:
        value = self.scope.data().get(self.name)
        return list(value) if isinstance(value, list) else []

    def ids(self) -> list[int]:
        return _asIds(self.scope.data().get(self.name))

    def int(self, default: int | None = None) -> int | None:
        try:
            return int(self.scope.data().get(self.name))
        except (TypeError, ValueError):
            return default

    def has(self, item: Any) -> bool:
        return item in self.list()

    def exists(self) -> bool:
        return self.name in self.scope.data()

    # -- writes ----------------------------------------------------------

    def write(self, value: Any) -> "Field":
        self.scope.data(create=True)[self.name] = value
        self.scope.db.touch()
        return self

    def delete(self) -> "Field":
        data = self.scope.data()
        if self.name in data:
            del data[self.name]
            self.scope.db.touch()
        return self

    def add(self, *items: Any) -> "Field":
        current = self.list()
        new = [item for item in items if item not in current]
        return self.write(_ordered(current + new)) if new else self

    def remove(self, *items: Any, prune: bool = True) -> "Field":
        current = self.list()
        kept = [item for item in current if item not in items]
        if len(kept) == len(current):
            return self
        return self.delete() if not kept and prune else self.write(kept)

    def toggle(self, item: Any) -> "Field":
        return self.remove(item) if self.has(item) else self.add(item)

    # -- persistence -----------------------------------------------------

    def save(self) -> "Field":
        self.scope.db.save()
        return self


class Scope:
    def __init__(self, db: "DataBase", name: str | None) -> None:
        self.db = db
        self.name = name

    def __repr__(self) -> str:
        return f"<Scope {self.db.name}:{self.label}>"

    @property
    def label(self) -> str:
        return self.name if self.name is not None else "<root>"

    def key(self, name: str) -> Field:
        return Field(self, name)

    def data(self, *, create: bool = False) -> MutableMapping[str, Any]:
        cfg = self.db.open()
        if self.name is None:
            return cfg
        if create:
            return cfg.section(self.name, create=True)
        existing = cfg.get(self.name)
        return existing if isinstance(existing, MutableMapping) else {}

    def exists(self) -> bool:
        return self.name is None or self.name in self.db.open()

    def keys(self) -> list[str]:
        return list(self.data())

    def toDict(self) -> dict:
        return dict(self.data())

    def merge(self, values: Mapping) -> "Scope":
        self.data(create=True).update(values)
        self.db.touch()
        return self

    def clear(self) -> "Scope":
        cfg = self.db.open()
        if self.name is not None and self.name in cfg:
            del cfg[self.name]
            self.db.touch()
        return self

    def save(self) -> "Scope":
        self.db.save()
        return self


class DataBase:
    def __init__(self, name: str, *, version: int | None = None) -> None:
        self.name = name
        self.path = config.dataDir / f"{name}{SUFFIX}"
        self.version = version
        self._config: JPConfig | None = None
        self._dirty = False

    def __repr__(self) -> str:
        return f"<DataBase {self.name} ({'dirty' if self._dirty else 'clean'})>"

    def __contains__(self, name: object) -> bool:
        return str(name) in self.open()

    def __iter__(self) -> Iterator[str]:
        return iter(self.open())

    # -- access ----------------------------------------------------------

    def open(self) -> JPConfig:
        if self._config is None:
            try:
                self._config = JPConfig.load(self.path, missing_ok=True)
            except (JPError, OSError) as e:
                print(cf.red(f"[database] could not read {self.path}: {e}"))
                self._config = JPConfig(None, path=self.path)
        return self._config

    def guild(self, guildId: int | str) -> Scope:
        return Scope(self, str(guildId))

    def section(self, name: int | str) -> Scope:
        return Scope(self, str(name))

    def root(self) -> Scope:
        return Scope(self, None)

    def key(self, name: str) -> Field:
        return self.root().key(name)

    def sections(self) -> list[str]:
        return [name for name in self.open() if name != versionKey]

    def toDict(self) -> dict:
        return self.open().to_dict()

    # -- persistence -----------------------------------------------------

    @property
    def dirty(self) -> bool:
        return self._dirty

    def touch(self) -> "DataBase":
        self._dirty = True
        return self

    def save(self, *, force: bool = False) -> "DataBase":
        if self._config is None or not (self._dirty or force):
            return self

        cfg = self._config
        if self.version is not None and cfg.get(versionKey) != self.version:
            cfg[versionKey] = self.version

        self._dirty = False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            cfg.save()
        except (JPError, OSError) as e:
            self._dirty = True
            print(cf.red(f"[database] could not write {self.path}: {e}"))
        return self

    def reload(self) -> "DataBase":
        self._config = None
        self._dirty = False
        self.open()
        return self


def database(name: str, *, version: int | None = None) -> DataBase:
    path = config.dataDir / f"{name}{SUFFIX}"
    existing = _databases.get(path)
    if existing is None:
        existing = _databases[path] = DataBase(name, version=version)
    return existing


def databases() -> list[DataBase]:
    return list(_databases.values())


def saveAll() -> list[str]:
    saved = []
    for db in _databases.values():
        if db.dirty:
            db.save()
            saved.append(db.name)
    return saved


async def flushForever(interval: float = flushInterval) -> None:
    while True:
        await asyncio.sleep(interval)
        await asyncio.to_thread(saveAll)

from __future__ import annotations

from abc import ABC, abstractmethod


class DatabaseAdapter(ABC):
    @abstractmethod
    def open_readonly(self, database_path: str) -> None: ...

    @abstractmethod
    def execute_select(self, sql: str) -> list[dict]: ...

    @abstractmethod
    def read_schema(self) -> list[dict]: ...

    @abstractmethod
    def close(self) -> None: ...

"""Read-only SQL inspection and query helpers used by the chat agent."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Engine, inspect, text


MAX_QUERY_ROWS = 200
_WRITE_KEYWORDS = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|"
    r"GRANT|REVOKE|MERGE|UPSERT|COPY|CALL|DO|EXECUTE|VACUUM|INTO)\b",
    flags=re.IGNORECASE,
)
_LEADING_READ_STATEMENT = re.compile(
    r"^\s*(?:SELECT|WITH|EXPLAIN)\b",
    flags=re.IGNORECASE,
)
_SQL_COMMENTS = re.compile(r"/\*.*?\*/|--[^\r\n]*", flags=re.DOTALL)


class ReadOnlySQLDatabase:
    """Expose schema inspection and guarded SELECT execution to an agent."""

    def __init__(self, engine: Engine, schema: str | None = None) -> None:
        self.engine = engine
        self.schema = schema
        self.dialect = engine.dialect.name
        self._inspector = inspect(engine)

    def get_usable_table_names(self) -> list[str]:
        """Return tables, views, and materialized views in the selected schema."""
        names = set(self._inspector.get_table_names(schema=self.schema))
        names.update(self._inspector.get_view_names(schema=self.schema))

        get_materialized_views = getattr(
            self._inspector,
            "get_materialized_view_names",
            None,
        )
        if get_materialized_views is not None:
            try:
                names.update(get_materialized_views(schema=self.schema))
            except NotImplementedError:
                pass

        return sorted(names)

    def describe_tables(self, requested_names: Sequence[str] | None = None) -> str:
        """Return columns, keys, and relationships for selected tables."""
        available_names = self.get_usable_table_names()
        selected_names = list(requested_names or available_names)
        unknown_names = sorted(set(selected_names) - set(available_names))
        if unknown_names:
            return (
                "Unknown tables: "
                + ", ".join(unknown_names)
                + ". Available tables: "
                + ", ".join(available_names)
            )

        descriptions: list[str] = []
        for table_name in selected_names:
            columns = self._inspector.get_columns(table_name, schema=self.schema)
            column_lines = []
            for column in columns:
                nullable = "NULL" if column.get("nullable", True) else "NOT NULL"
                column_lines.append(
                    f"- {column['name']}: {column['type']} {nullable}"
                )

            primary_key = self._inspector.get_pk_constraint(
                table_name,
                schema=self.schema,
            ).get("constrained_columns") or []
            foreign_keys = self._inspector.get_foreign_keys(
                table_name,
                schema=self.schema,
            )

            table_lines = [f"Table {table_name}", "Columns:", *column_lines]
            if primary_key:
                table_lines.append("Primary key: " + ", ".join(primary_key))
            for foreign_key in foreign_keys:
                source = ", ".join(foreign_key.get("constrained_columns") or [])
                target_table = foreign_key.get("referred_table") or "unknown"
                target_columns = ", ".join(
                    foreign_key.get("referred_columns") or []
                )
                table_lines.append(
                    f"Foreign key: {source} -> {target_table}({target_columns})"
                )
            descriptions.append("\n".join(table_lines))

        return "\n\n".join(descriptions) or "No tables are available."

    def run_query(self, query: str, max_rows: int = MAX_QUERY_ROWS) -> str:
        """Execute one guarded read-only statement and return structured JSON."""
        statement = self._validate_read_only_query(query)

        try:
            with self.engine.begin() as connection:
                if self.schema and self.dialect == "postgresql":
                    connection.execute(
                        text("SELECT set_config('search_path', :schema, true)"),
                        {"schema": self.schema},
                    )

                result = connection.execute(text(statement))
                if not result.returns_rows:
                    return json.dumps({"columns": [], "rows": [], "truncated": False})

                columns = list(result.keys())
                rows = result.fetchmany(max_rows + 1)
        except Exception as error:
            return f"Database error ({error.__class__.__name__}): {error}"

        truncated = len(rows) > max_rows
        visible_rows = rows[:max_rows]
        serializable_rows = [
            dict(zip(columns, row, strict=True)) for row in visible_rows
        ]
        return json.dumps(
            {
                "columns": columns,
                "rows": serializable_rows,
                "truncated": truncated,
                "row_limit": max_rows,
            },
            default=self._json_default,
        )

    @staticmethod
    def _validate_read_only_query(query: str) -> str:
        statement = query.strip()
        normalized = _SQL_COMMENTS.sub(" ", statement).strip()
        normalized_without_trailing_semicolon = normalized.rstrip(";").rstrip()

        if not normalized_without_trailing_semicolon:
            raise ValueError("The SQL query is empty.")
        if ";" in normalized_without_trailing_semicolon:
            raise ValueError("Only one SQL statement is allowed.")
        if not _LEADING_READ_STATEMENT.match(normalized_without_trailing_semicolon):
            raise ValueError("Only SELECT, WITH, or EXPLAIN statements are allowed.")
        if _WRITE_KEYWORDS.search(normalized_without_trailing_semicolon):
            raise ValueError("The query contains a data-changing SQL keyword.")

        return statement

    @staticmethod
    def _json_default(value: Any) -> str:
        return str(value)

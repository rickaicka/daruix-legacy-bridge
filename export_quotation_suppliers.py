"""Exporta metadados ou tabelas selecionadas do Access em modo somente leitura."""
import argparse
import base64
import json
import os
import re
from pathlib import Path

from app.config import get_settings
from app.legacy.connection import AccessConnectionFactory


CANDIDATE = re.compile(r"fornec|supplier|vend(?:edor|a)|compr|cota[çc]|concorr|contato|pagamento", re.I)


def table_schema(table):
    return dict(
        columns=[dict(name=str(col.getName()), type=str(col.getType())) for col in table.getColumns()],
        primary_key=next(([str(col.getName()) for col in index.getColumns()]
                          for index in table.getIndexes() if index.isPrimaryKey()), []),
        count=int(table.getRowCount()),
    )


def encode(value, access_type):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if access_type in {"BINARY", "OLE"}:
        return {"base64": base64.b64encode(bytes(value)).decode("ascii")}
    return str(value)


def export(database, selected):
    names = sorted(map(str, database.getTableNames()))
    if missing := set(selected).difference(names):
        raise ValueError(f"Tabelas ausentes no Access: {', '.join(sorted(missing))}")
    tables = {}
    for name in dict.fromkeys(selected or names):
        try:
            table = database.getTable(name)
            info = table_schema(table)
        except Exception as error:
            if selected:
                raise
            tables[name] = {"error": type(error).__name__}
            continue
        info["candidate"] = bool(CANDIDATE.search(name) or any(CANDIDATE.search(c["name"]) for c in info["columns"]))
        if selected:
            info["rows"] = [
                {col["name"]: encode(row.get(col["name"]), col["type"]) for col in info["columns"]}
                for row in table
            ]
        tables[name] = info
    relationships = [
        dict(name=str(rel.getName()), source=str(rel.getFromTable().getName()),
             target=str(rel.getToTable().getName()),
             from_columns=[str(col.getName()) for col in rel.getFromColumns()],
             to_columns=[str(col.getName()) for col in rel.getToColumns()])
        for rel in database.getRelationships()
    ]
    return dict(tables=tables, relationships=relationships)


def private_file(path, flags):
    return os.open(path, flags, 0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", action="append", default=[], help="Nome exato. Repita para tabelas relacionadas.")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with AccessConnectionFactory(get_settings()).connect() as database:
        result = export(database, args.table)
    with open(args.output, "x", encoding="utf-8", opener=private_file) as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()

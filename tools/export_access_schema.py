#!/usr/bin/env python3
"""Executar no container do bridge. Apenas metadados; nunca lê registros."""
import argparse
import json
import re
import sys
from datetime import datetime, timezone

# Propriedades estruturais e de lookup do Access; não exportar conexões/senhas.
PROPERTIES = {
    'required', 'allowzerolength', 'defaultvalue', 'validationrule',
    'validationtext', 'caption', 'description', 'format', 'decimalplaces',
    'inputmask', 'displaycontrol', 'rowsourcetype', 'rowsource',
    'boundcolumn', 'columncount', 'columnwidths', 'limittolist',
}


def redact(value):
    return re.sub(r'(?i)((?:password|pwd|jet oledb:database password)\s*=\s*)[^;\r\n]*',
                  r'\1<omitido>', str(value))


def value(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return redact(v) if isinstance(v, str) else v
    return redact(v)


def call(obj, name, warnings, label, *args):
    try:
        return getattr(obj, name)(*args)
    except Exception as error:
        # Não registrar corpos de erro que possam conter caminhos ou credenciais.
        warnings.append({'object': label, 'method': name,
                         'error_type': type(error).__name__})
        return None


def props(obj, warnings, label):
    properties = call(obj, 'getProperties', warnings, label)
    result = {}
    if properties is not None:
        for prop in properties:
            key = str(prop.getName())
            if key.casefold() in PROPERTIES:
                result[key] = value(prop.getValue())
    return result


def export(database, *, pattern='requis|material|servi|insumo|etapa|orcamento|orçamento|rm'):
    warnings = []
    names = sorted(map(str, database.getTableNames()), key=str.casefold)
    candidate = re.compile(pattern, re.I)
    result = {'format_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
              'contains_records': False, 'table_names': names,
              'rm_candidates_by_name_only': [n for n in names if candidate.search(n)],
              'tables': [], 'relationships': [], 'queries': [], 'warnings': warnings}
    # Exportar TODAS as tabelas de usuário preserva referências de nomes não óbvios.
    for name in names:
        table = database.getTable(name)
        item = {'name': name, 'row_count': int(table.getRowCount()),
                'properties': props(table, warnings, name), 'columns': [], 'indexes': []}
        for column in table.getColumns():
            label = name + '.' + str(column.getName())
            c = {'name': str(column.getName()), 'type': str(column.getType()),
                 'properties': props(column, warnings, label)}
            for method, key in [('getLength', 'length_bytes'), ('getPrecision', 'precision'),
                                ('getScale', 'scale'), ('isAutoNumber', 'auto_number')]:
                c[key] = value(call(column, method, warnings, label))
            item['columns'].append(c)
        for index in table.getIndexes():
            item['indexes'].append({
                'name': str(index.getName()), 'primary_key': bool(index.isPrimaryKey()),
                'unique': bool(index.isUnique()),
                'columns': [{'name': str(c.getName()),
                             'ascending': value(call(c, 'isAscending', warnings, name))}
                            for c in index.getColumns()]})
        result['tables'].append(item)
    relationships = call(database, 'getRelationships', warnings, 'database')
    if relationships is not None:
        for relation in relationships:
            r = {'name': str(relation.getName()),
                 'from_table': str(relation.getFromTable().getName()),
                 'to_table': str(relation.getToTable().getName()),
                 'from_columns': [str(c.getName()) for c in relation.getFromColumns()],
                 'to_columns': [str(c.getName()) for c in relation.getToColumns()]}
            for method in ['hasReferentialIntegrity', 'cascadeUpdates', 'cascadeDeletes']:
                r[method] = value(call(relation, method, warnings, r['name']))
            result['relationships'].append(r)
    queries = call(database, 'getQueries', warnings, 'database')
    if queries is not None:
        for query in queries:
            result['queries'].append({'name': str(query.getName()),
                                     'type': str(query.getType()),
                                     'sql': value(call(query, 'toSQLString', warnings,
                                                       str(query.getName())))})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pattern', default='requis|material|servi|insumo|etapa|orcamento|orçamento|rm')
    args = parser.parse_args()
    from app.config import get_settings
    from app.legacy.connection import AccessConnectionFactory
    factory = AccessConnectionFactory(get_settings())
    # Mesmo ANTES de aplicar o patch, forçar abertura explícita somente leitura.
    def read_only_open(path):
        factory._start_jvm()
        import jpype
        builder = jpype.JClass('com.healthmarketscience.jackcess.DatabaseBuilder')
        file = jpype.JClass('java.io.File')
        return builder(file(str(path))).setReadOnly(True).open()
    factory._open_database = read_only_open
    with factory.connect() as database:
        result = export(database, pattern=args.pattern)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write('\n')
    if result['warnings']:
        print('Metadados exportados com avisos; ver warnings no JSON.', file=sys.stderr)


if __name__ == '__main__':
    main()

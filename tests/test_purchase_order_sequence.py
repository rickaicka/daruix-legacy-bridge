from unittest.mock import MagicMock
import pytest
from app.legacy.repository import LegacyRepository


class FakeTable:
    def __init__(self, rows):
        self.rows = rows
    def getColumns(self):
        return [type('Col', (), {'getName': lambda self, n=n: n})()
                for n in ('ordemDeCompraPC', 'ordemDeCompraNumero')]
    def __iter__(self):
        return iter(self.rows)


class FakeDatabase:
    def __init__(self, rows):
        self.table = FakeTable(rows)
    def getTableNames(self):
        return ['tblOrdemDeCompra']
    def getTable(self, name):
        return self.table


def repository(rows):
    from contextlib import contextmanager
    @contextmanager
    def connect():
        yield FakeDatabase(rows)
    return LegacyRepository(type('Factory', (), {'connect': staticmethod(connect)})())


def test_last_suffix_from_legacy_table():
    rows = [{'ordemDeCompraPC':'PC26105', 'ordemDeCompraNumero':1},
            {'ordemDeCompraPC':'PC26105', 'ordemDeCompraNumero':26105003},
            {'ordemDeCompraPC':'PC27000', 'ordemDeCompraNumero':22}]
    result = repository(rows).last_purchase_order_sequence('PC26105')
    assert result['last_suffix'] == 3
    assert result['matched_orders'] == 2


def test_absent_pc_is_confirmed_zero():
    assert repository([]).last_purchase_order_sequence('PC26105')['last_suffix'] == 0


def test_malformed_legacy_number_blocks():
    with pytest.raises(ValueError):
        repository([{'ordemDeCompraPC':'PC26105', 'ordemDeCompraNumero':'X'}]).last_purchase_order_sequence('PC26105')

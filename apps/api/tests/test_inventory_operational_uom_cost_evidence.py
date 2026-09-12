from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from test_inventory_recipe_stock_foundation import _headers, _item, _scope
from test_inventory_warehouse_ledger_compatibility import _movement


@pytest.fixture
def client(integration_settings):
    with TestClient(create_app(settings=integration_settings)) as value:
        yield value


def test_item_uom_revisions_snapshot_movement_evidence_and_reversal(
    client, sql_connection,
) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, ('inventory.manage', 'inventory.read'))
    headers = _headers(client, scope)
    item = _item(
        client, headers, scope.location_id, 'SYRUP-BOX', uom='UNIT', cost='2.000000',
    )

    conversion_url = f"/inventory-items/{item['id']}/uom-conversions"
    first_conversion_response = client.post(
        conversion_url,
        headers=headers,
        json={
            'operational_uom': 'box',
            'factor_to_base': '12.500000000000',
            'reference': '12.5 units per box',
        },
    )
    assert first_conversion_response.status_code == 201, first_conversion_response.text
    first_conversion = first_conversion_response.json()
    assert first_conversion['revision'] == 1
    assert first_conversion['factor_to_base'] == '12.500000000000'

    movement = _movement(
        client, headers, 'b2-box-1', item['id'], 'MANUAL_IN',
        quantity='2.000000', uom='BOX', reason='receive boxes',
    )
    assert movement.status_code == 201, movement.text
    evidence = movement.json()
    assert evidence['quantity'] == '25.000000'
    assert evidence['source_quantity'] == '2.000000'
    assert evidence['source_uom'] == 'BOX'
    assert evidence['conversion_revision_id'] == first_conversion['id']
    assert evidence['conversion_factor'] == '12.500000000000'
    assert evidence['base_uom_evidence'] == 'UNIT'
    assert evidence['standard_cost_revision_id'] is not None
    assert evidence['standard_unit_cost_evidence'] == '2.000000'
    assert evidence['cost_currency_evidence'] == 'MXN'
    assert evidence['extended_standard_cost'] == '50.000000000000'
    assert evidence['evidence_status'] == 'RESOLVED'

    replay = _movement(
        client, headers, 'b2-box-1', item['id'], 'MANUAL_IN',
        quantity='2.000000', uom='BOX', reason='receive boxes',
    )
    assert replay.status_code == 200
    assert replay.json()['id'] == evidence['id']
    assert _movement(
        client, headers, 'b2-box-1', item['id'], 'MANUAL_IN',
        quantity='2.000000', uom='CASE', reason='receive boxes',
    ).status_code == 409

    second_conversion_response = client.post(
        conversion_url,
        headers=headers,
        json={'operational_uom': 'BOX', 'factor_to_base': '10.000000000000'},
    )
    assert second_conversion_response.status_code == 201, second_conversion_response.text
    second_conversion = second_conversion_response.json()
    assert second_conversion['revision'] == 2
    second = _movement(
        client, headers, 'b2-box-2', item['id'], 'MANUAL_IN',
        quantity='1.000000', uom='BOX', reason='second receipt',
    )
    assert second.status_code == 201, second.text
    assert second.json()['quantity'] == '10.000000'
    assert second.json()['conversion_revision_id'] == second_conversion['id']

    listed = client.get(conversion_url, headers=headers)
    assert listed.status_code == 200
    assert [row['id'] for row in listed.json()['items']] == [
        first_conversion['id'], second_conversion['id'],
    ]
    movements = client.get(
        '/inventory/stock-movements', headers=headers,
        params={'location_id': scope.location_id, 'inventory_item_id': item['id']},
    )
    original = next(row for row in movements.json()['items'] if row['id'] == evidence['id'])
    assert original['conversion_revision_id'] == first_conversion['id']
    assert original['quantity'] == '25.000000'

    reversal = _movement(
        client, headers, 'b2-box-reversal', item['id'], 'REVERSAL',
        reversal_of_movement_id=evidence['id'], reason='reverse receipt',
    )
    assert reversal.status_code == 201, reversal.text
    reversed_evidence = reversal.json()
    assert reversed_evidence['quantity'] == '-25.000000'
    assert reversed_evidence['source_quantity'] == '-2.000000'
    assert reversed_evidence['conversion_revision_id'] == first_conversion['id']
    assert reversed_evidence['standard_cost_revision_id'] == evidence[
        'standard_cost_revision_id'
    ]
    assert reversed_evidence['extended_standard_cost'] == '-50.000000000000'

    assert client.post(
        conversion_url, headers=headers,
        json={'operational_uom': 'KG', 'factor_to_base': '2'},
    ).status_code == 422
    assert client.post(
        conversion_url, headers=headers,
        json={'operational_uom': 'CASE', 'factor_to_base': '0'},
    ).status_code == 422
    assert _movement(
        client, headers, 'b2-unknown-uom', item['id'], 'MANUAL_IN',
        quantity='1.000000', uom='CASE', reason='unknown package',
    ).status_code == 404

    other_item = _item(
        client, headers, scope.location_id, 'OTHER-BOX', uom='UNIT', cost='1.000000',
    )
    assert _movement(
        client, headers, 'b2-item-scope', other_item['id'], 'MANUAL_IN',
        quantity='1.000000', uom='BOX', reason='wrong item conversion',
    ).status_code == 404


def test_cost_revision_history_as_of_and_scope(client, sql_connection) -> None:
    connection, prefix = sql_connection
    scope = _scope(connection, prefix, ('inventory.manage', 'inventory.read'))
    headers = _headers(client, scope)
    item = _item(
        client, headers, scope.location_id, 'COSTED-ITEM',
        uom='G', cost='1.250000', currency='MXN',
    )
    revisions_url = f"/inventory-items/{item['id']}/cost-revisions"

    initial_response = client.get(revisions_url, headers=headers)
    assert initial_response.status_code == 200, initial_response.text
    initial = initial_response.json()['items']
    assert len(initial) == 1
    assert initial[0]['source'] == 'ITEM_CREATION'
    assert initial[0]['revision'] == 1
    assert initial[0]['standard_unit_cost'] == '1.250000'

    before = client.get(
        f"/inventory-items/{item['id']}/standard-cost",
        headers=headers,
        params={'as_of': '2000-01-01T00:00:00Z'},
    )
    assert before.status_code == 409
    assert before.json()['error']['code'] == 'INVENTORY_COST_NOT_DERIVABLE'

    revised_response = client.post(
        revisions_url,
        headers=headers,
        json={
            'expected_version': 1,
            'standard_unit_cost': '3.500000',
            'currency': 'mxn',
            'reference': 'supplier review',
        },
    )
    assert revised_response.status_code == 201, revised_response.text
    revised = revised_response.json()
    assert revised['revision'] == 2
    assert revised['standard_unit_cost'] == '3.500000'
    assert revised['currency'] == 'MXN'
    assert revised['source'] == 'STANDARD_COST_UPDATE'

    history = client.get(revisions_url, headers=headers).json()['items']
    assert [row['revision'] for row in history] == [1, 2]
    assert history[0]['standard_unit_cost'] == '1.250000'
    current = client.get(
        f"/inventory-items/{item['id']}/standard-cost",
        headers=headers,
        params={'as_of': revised['effective_at']},
    )
    assert current.status_code == 200, current.text
    assert current.json()['id'] == revised['id']

    movement = _movement(
        client, headers, 'b2-cost-snapshot', item['id'], 'MANUAL_IN',
        quantity='2.000000', uom='G', reason='cost evidence',
    )
    assert movement.status_code == 201, movement.text
    assert movement.json()['standard_cost_revision_id'] == revised['id']
    assert movement.json()['extended_standard_cost'] == '7.000000000000'

    assert client.post(
        revisions_url,
        headers=headers,
        json={
            'expected_version': 2,
            'standard_unit_cost': '4.000000',
            'currency': 'MXN',
            'effective_at': '2000-01-01T00:00:00Z',
        },
    ).status_code == 422
    assert client.patch(
        f"/inventory-items/{item['id']}", headers=headers,
        json={'expected_version': 2, 'base_uom': 'KG'},
    ).status_code == 422

    other_scope = _scope(
        connection, f'{prefix}-other', ('inventory.manage', 'inventory.read'),
    )
    other_headers = _headers(client, other_scope)
    assert client.get(revisions_url, headers=other_headers).status_code == 404
    assert client.post(
        revisions_url,
        headers=other_headers,
        json={
            'expected_version': 2,
            'standard_unit_cost': '9.000000',
            'currency': 'MXN',
        },
    ).status_code == 404

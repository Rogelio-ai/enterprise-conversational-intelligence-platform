from __future__ import annotations

import json
import re
import textwrap
import unicodedata


RENDERER_VERSION = 'preparation-ticket-v1'


def sanitize(value: object) -> str:
    text = str(value or '')
    # Drop control/format/surrogate/private-use characters. Newlines are converted
    # to spaces so payload data cannot inject printer structure or commands.
    return re.sub(r'\s+', ' ', ''.join(
        char for char in text if unicodedata.category(char)[0] not in {'C'}
    )).strip()


def _lines(value: str, width: int, *, prefix: str = '') -> list[str]:
    available = max(1, width - len(prefix))
    wrapped = textwrap.wrap(
        sanitize(value), width=available, break_long_words=True,
        break_on_hyphens=False, replace_whitespace=True, drop_whitespace=True,
    ) or ['']
    return [prefix + wrapped[0], *[(' ' * len(prefix)) + item for item in wrapped[1:]]]


def render_preparation_ticket(payload_text: str, *, columns: int = 42) -> str:
    if columns not in {32, 42, 48}:
        raise ValueError('ticket columns must be 32, 42, or 48')
    payload = json.loads(payload_text)
    if payload.get('schema') != 'preparation-delivery-v1':
        raise ValueError('unsupported frozen payload schema')
    work = payload.get('preparation_work', {})
    order = payload.get('restaurant_order', {})
    output = [
        'PREPARACIÓN'.center(columns),
        '=' * columns,
    ]
    area = work.get('area_name') or work.get('area_code')
    if area:
        output.extend(_lines(f'Área: {area}', columns))
    output.extend(_lines(f'Orden: {order.get("id")}', columns))
    if order.get('accepted_at'):
        output.extend(_lines(f'Aceptada: {order["accepted_at"]}', columns))
    if work.get('routed_at'):
        output.extend(_lines(f'Enrutada: {work["routed_at"]}', columns))
    resource = order.get('resource_name_at_dispatch') or order.get('resource_code_at_dispatch')
    if resource:
        output.extend(_lines(f'Recurso: {resource}', columns))
    if order.get('source_channel'):
        output.extend(_lines(f'Canal: {order["source_channel"]}', columns))
    output.append('-' * columns)
    for item in payload.get('items', []):
        quantity = sanitize(item.get('required_quantity'))
        name = sanitize(item.get('product_name'))
        output.extend(_lines(name, columns, prefix=f'{quantity} x '))
        parent = item.get('parent_product_name')
        if parent:
            output.extend(_lines(f'de {parent}', columns, prefix='  '))
        for component in item.get('accepted_components', []):
            component_name = component.get('product_name')
            if component_name and sanitize(component_name) != name:
                component_qty = sanitize(component.get('quantity'))
                group = sanitize(component.get('choice_group_name'))
                detail = f'{component_qty} x {component_name}'
                if group:
                    detail = f'{group}: {detail}'
                output.extend(_lines(detail, columns, prefix='  + '))
    output.extend(['=' * columns, ''])
    return '\n'.join(line[:columns] for line in output)

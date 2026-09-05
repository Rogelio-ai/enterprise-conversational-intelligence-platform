from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Protocol
from xml.etree import ElementTree as ET

import httpx


SOAP_NAMESPACE = 'http://schemas.xmlsoap.org/soap/envelope/'
STAMP_NAMESPACE = 'http://facturacion.finkok.com/stamp'


class FinkokTransportError(RuntimeError):
    pass


class FinkokDefiniteTransportError(FinkokTransportError):
    pass


class FinkokAmbiguousTransportError(FinkokTransportError):
    pass


@dataclass(frozen=True, slots=True)
class FinkokIncidence:
    code: str | None
    message: str | None
    work_process_id: str | None = None


@dataclass(frozen=True, slots=True)
class FinkokStampResponse:
    xml: str | None = None
    uuid: str | None = None
    fecha: str | None = None
    status: str | None = None
    fault_code: str | None = None
    fault_message: str | None = None
    incidences: tuple[FinkokIncidence, ...] = ()


class FinkokSoapTransport(Protocol):
    async def sign_stamp(
        self, *, xml: bytes, username: str, password: str
    ) -> FinkokStampResponse: ...

    async def stamped(
        self, *, xml: bytes, username: str, password: str
    ) -> FinkokStampResponse: ...


def _local(element: ET.Element, name: str) -> ET.Element | None:
    return next(
        (item for item in element.iter() if item.tag.rsplit('}', 1)[-1] == name),
        None,
    )


def _text(element: ET.Element, name: str) -> str | None:
    found = _local(element, name)
    if found is None or found.text is None or not found.text.strip():
        return None
    return found.text.strip()


class HttpxFinkokSoapTransport:
    """Small SOAP 1.1 transport with no retries and bounded timeouts."""

    def __init__(
        self,
        *,
        endpoint: str,
        connect_timeout_seconds: float,
        read_timeout_seconds: float,
    ) -> None:
        self._endpoint = endpoint
        self._timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=read_timeout_seconds,
            pool=connect_timeout_seconds,
        )

    async def sign_stamp(
        self, *, xml: bytes, username: str, password: str
    ) -> FinkokStampResponse:
        return await self._call(
            operation='sign_stamp', xml=xml, username=username, password=password
        )

    async def stamped(
        self, *, xml: bytes, username: str, password: str
    ) -> FinkokStampResponse:
        return await self._call(
            operation='stamped', xml=xml, username=username, password=password
        )

    async def _call(
        self, *, operation: str, xml: bytes, username: str, password: str
    ) -> FinkokStampResponse:
        envelope = ET.Element(f'{{{SOAP_NAMESPACE}}}Envelope')
        ET.SubElement(envelope, f'{{{SOAP_NAMESPACE}}}Header')
        body = ET.SubElement(envelope, f'{{{SOAP_NAMESPACE}}}Body')
        call = ET.SubElement(body, f'{{{STAMP_NAMESPACE}}}{operation}')
        ET.SubElement(call, f'{{{STAMP_NAMESPACE}}}xml').text = (
            base64.b64encode(xml).decode('ascii')
        )
        ET.SubElement(call, f'{{{STAMP_NAMESPACE}}}username').text = username
        ET.SubElement(call, f'{{{STAMP_NAMESPACE}}}password').text = password
        payload = ET.tostring(envelope, encoding='utf-8', xml_declaration=True)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self._endpoint,
                    content=payload,
                    headers={
                        'Content-Type': 'text/xml; charset=utf-8',
                        'SOAPAction': operation,
                    },
                )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise FinkokDefiniteTransportError(
                'Could not connect to FINKOK'
            ) from exc
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.RemoteProtocolError) as exc:
            raise FinkokAmbiguousTransportError(
                'FINKOK outcome is unknown after transport interruption'
            ) from exc
        except httpx.HTTPError as exc:
            raise FinkokAmbiguousTransportError(
                'FINKOK transport outcome is unknown'
            ) from exc
        if response.status_code >= 500:
            raise FinkokAmbiguousTransportError(
                'FINKOK server response did not establish an outcome'
            )
        if response.status_code >= 400:
            raise FinkokDefiniteTransportError('FINKOK rejected the HTTP request')
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise FinkokAmbiguousTransportError(
                'FINKOK returned an unreadable response'
            ) from exc
        fault = _local(root, 'Fault')
        if fault is not None:
            return FinkokStampResponse(
                fault_code=_text(fault, 'faultcode'),
                fault_message=_text(fault, 'faultstring'),
            )
        result = _local(root, f'{operation}Result')
        if result is None:
            raise FinkokAmbiguousTransportError(
                'FINKOK response omitted its operation result'
            )
        incidences = tuple(
            FinkokIncidence(
                code=_text(item, 'CodigoError'),
                message=_text(item, 'MensajeIncidencia'),
                work_process_id=_text(item, 'WorkProcessId'),
            )
            for item in result.iter()
            if item.tag.rsplit('}', 1)[-1] == 'Incidencia'
        )
        return FinkokStampResponse(
            xml=_text(result, 'xml'),
            uuid=_text(result, 'UUID'),
            fecha=_text(result, 'Fecha'),
            status=_text(result, 'CodEstatus'),
            fault_code=_text(result, 'faultcode'),
            fault_message=_text(result, 'faultstring'),
            incidences=incidences,
        )

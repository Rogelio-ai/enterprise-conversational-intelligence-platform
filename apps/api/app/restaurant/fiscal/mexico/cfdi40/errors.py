class MexicoCfdi40Error(ValueError):
    """Controlled, safe Mexico CFDI semantic-boundary failure."""

    code = 'MEXICO_CFDI_40_ERROR'


class MexicoCfdi40MappingError(MexicoCfdi40Error):
    code = 'MEXICO_CFDI_40_MAPPING_INVALID'


class MexicoCfdi40ValidationError(MexicoCfdi40Error):
    code = 'MEXICO_CFDI_40_VALIDATION_INVALID'

from app.core.logging import JsonFormatter, configure_logging


def test_uvicorn_loggers_use_structured_json_handler() -> None:
    import logging

    configure_logging(service='ECIP Test API', level='INFO')

    for logger_name in ('uvicorn', 'uvicorn.error', 'uvicorn.access'):
        runtime_logger = logging.getLogger(logger_name)
        assert runtime_logger.propagate is False
        assert len(runtime_logger.handlers) == 1
        assert isinstance(runtime_logger.handlers[0].formatter, JsonFormatter)

FROM python:3.12-slim AS build

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip wheel --no-cache-dir --wheel-dir /wheels .

FROM build AS test

COPY tests ./tests
RUN pip install --no-cache-dir /wheels/*.whl "pytest>=8,<9" "pytest-asyncio>=0.24,<1" \
    && pytest -q

FROM python:3.12-slim

RUN groupadd --system connector && useradd --system --gid connector connector \
    && mkdir -p /var/lib/pryecip-local-connector /etc/pryecip-local-connector \
    && chown connector:connector /var/lib/pryecip-local-connector
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
USER connector
ENTRYPOINT ["pryecip-local-connector"]
CMD ["--config", "/etc/pryecip-local-connector/config.toml", "run"]

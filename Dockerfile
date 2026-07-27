FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install --no-cache-dir .


FROM base AS test

COPY tests ./tests

USER app

CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]


FROM base AS runtime

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health', timeout=2)"]

ENTRYPOINT ["secret-santa"]
CMD ["--host", "0.0.0.0", "--port", "8000"]

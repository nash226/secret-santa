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

ENTRYPOINT ["secret-santa"]
CMD ["--help"]

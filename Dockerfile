FROM maven:3.9-eclipse-temurin-17 AS drivers
WORKDIR /build
COPY pom.xml .
RUN mvn -q dependency:copy-dependencies -DoutputDirectory=/drivers

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends default-jre-headless curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=drivers /drivers /opt/ucanaccess
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY app ./app
RUN useradd --system --uid 10001 bridge && chown -R bridge:bridge /app
USER bridge
EXPOSE 8100
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100", "--no-access-log"]


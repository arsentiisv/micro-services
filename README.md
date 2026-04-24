# Online Cinema Analytics Pipeline (HW5)

Full event pipeline for online cinema analytics:

- Producer API -> Kafka topic `movie-events`
- Kafka -> ClickHouse raw storage via `Kafka Engine + Materialized View`
- Aggregation service computes business metrics
- Metrics are stored in PostgreSQL and ClickHouse aggregate tables
- Daily export to S3-compatible storage (MinIO)
- Grafana dashboard reads aggregate tables
- Kafka UI and Adminer are available for visual checks

## Start

```bash
docker-compose up -d --build
docker-compose ps
```

## Main URLs

- Producer API: `http://localhost:8000`
- Aggregator API: `http://localhost:8002`
- Schema Registry: `http://localhost:8081`
- ClickHouse HTTP: `http://localhost:8123`
- Grafana: `http://localhost:3000` (`admin/admin`)
- MinIO Console: `http://localhost:9001` (`admin/password`)
- MinIO S3 API: `http://localhost:9002`
- Kafka UI: `http://localhost:8085`
- Adminer (PostgreSQL UI): `http://localhost:8088`

## Test

```bash
.\.venv\bin\python.exe -m pip install -r tests/requirements.txt
.\.venv\bin\python.exe -m pytest tests/test_pipeline.py -v
```

## Project map

- Infra: `docker-compose.yml`
- Event schema: `schemas/movie_event.avsc`
- Producer: `producer/main.py`
- ClickHouse DDL: `clickhouse/init.sql`
- Aggregator: `aggregator/main.py`
- PostgreSQL DDL: `postgres/init.sql`
- Grafana dashboard: `grafana/dashboards/analytics.json`
- Integration test: `tests/test_pipeline.py`

## Docs for defense and checking

- Detailed implementation: `IMPLEMENTATION_DETAILS.md`
- Full manual check procedure: `CHECK_INSTRUCTIONS.md`
- Hard defense guide: `DEFENSE_HARDCORE.md`

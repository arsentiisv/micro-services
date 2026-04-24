import json
import logging
import os
import time
from datetime import date, datetime, timedelta
from typing import Any, Callable

import boto3
import psycopg2
from apscheduler.schedulers.background import BackgroundScheduler
from clickhouse_driver import Client as CHClient
from fastapi import FastAPI, HTTPException
from psycopg2.extras import execute_values

app = FastAPI()
logger = logging.getLogger("aggregator")
logging.basicConfig(level=logging.INFO)

CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "localhost")
POSTGRES_DSN = os.environ.get("POSTGRES_DSN", "postgresql://user:password@localhost:5432/analytics")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://localhost:9000")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "admin")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "password")
S3_BUCKET = os.environ.get("S3_BUCKET", "movie-analytics")
AGGREGATION_CRON_HOUR = int(os.environ.get("AGGREGATION_CRON_HOUR", "1"))
AGGREGATION_CRON_MINUTE = int(os.environ.get("AGGREGATION_CRON_MINUTE", "0"))
RETRY_ATTEMPTS = int(os.environ.get("RETRY_ATTEMPTS", "5"))
RETRY_BASE_SECONDS = float(os.environ.get("RETRY_BASE_SECONDS", "0.5"))


def execute_with_retry(name: str, fn: Callable[[], Any], attempts: int = RETRY_ATTEMPTS):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            backoff = RETRY_BASE_SECONDS * (2 ** (attempt - 1))
            logger.warning("%s failed (%s/%s): %s. Retry in %.2fs", name, attempt, attempts, exc, backoff)
            if attempt < attempts:
                time.sleep(backoff)
    raise RuntimeError(f"{name} failed after {attempts} attempts: {last_error}")


def get_ch_client():
    return CHClient(host=CLICKHOUSE_HOST, database="online_cinema")


def get_pg_conn():
    return psycopg2.connect(POSTGRES_DSN)


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
    )


def run_postgres_migrations():
    pg = execute_with_retry("connect_postgres_migrations", get_pg_conn)
    try:
        with pg.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_metrics (
                    date DATE NOT NULL,
                    metric_name VARCHAR(50) NOT NULL,
                    metric_value NUMERIC NOT NULL,
                    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, metric_name)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS top_movies (
                    date DATE NOT NULL,
                    movie_id VARCHAR(50) NOT NULL,
                    views_count INT NOT NULL,
                    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (date, movie_id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS retention_metrics (
                    report_date DATE NOT NULL,
                    cohort_date DATE NOT NULL,
                    day_number INT NOT NULL,
                    retention_percent NUMERIC NOT NULL,
                    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (report_date, cohort_date, day_number)
                )
                """
            )

            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'retention_metrics'
                  AND column_name = 'report_date'
                """
            )
            has_report_date = cur.fetchone() is not None
            if not has_report_date:
                logger.info("Applying migration: add report_date to retention_metrics")
                cur.execute("ALTER TABLE retention_metrics ADD COLUMN report_date DATE")
                cur.execute(
                    """
                    UPDATE retention_metrics
                    SET report_date = cohort_date + day_number
                    """
                )
                cur.execute("ALTER TABLE retention_metrics ALTER COLUMN report_date SET NOT NULL")
                cur.execute("ALTER TABLE retention_metrics DROP CONSTRAINT IF EXISTS retention_metrics_pkey")
                cur.execute(
                    """
                    ALTER TABLE retention_metrics
                    ADD CONSTRAINT retention_metrics_pkey
                    PRIMARY KEY (report_date, cohort_date, day_number)
                    """
                )
        pg.commit()
    finally:
        pg.close()


def _calculate_retention(ch: CHClient, cohort_date: date, target_date: date):
    result = ch.execute(
        f"""
        WITH
            first_visits AS (
                SELECT user_id, min(date) AS first_date
                FROM movie_events
                GROUP BY user_id
            ),
            cohort_users AS (
                SELECT user_id
                FROM first_visits
                WHERE first_date = '{cohort_date}'
            ),
            return_users AS (
                SELECT uniq(user_id) AS ret_users
                FROM movie_events
                WHERE date = '{target_date}'
                  AND user_id IN (SELECT user_id FROM cohort_users)
            )
        SELECT
            (SELECT count() FROM cohort_users) AS total_cohort,
            (SELECT ret_users FROM return_users) AS returned
    """
    )
    total, returned = result[0] if result else (0, 0)
    retention_percent = (returned / total * 100) if total > 0 else 0
    return total, returned, retention_percent


def calculate_metrics_for_date(target_date: date):
    logger.info("Starting metrics calculation for %s", target_date)
    started_at = time.time()

    ch = execute_with_retry("connect_clickhouse", get_ch_client)
    pg = execute_with_retry("connect_postgres", get_pg_conn)

    try:
        dau_res = ch.execute(f"SELECT uniq(user_id) FROM movie_events WHERE date = '{target_date}'")
        dau = dau_res[0][0] if dau_res else 0

        avg_time_res = ch.execute(
            f"""
            SELECT avg(progress_seconds)
            FROM movie_events
            WHERE date = '{target_date}'
              AND event_type = 'VIEW_FINISHED'
        """
        )
        avg_time = avg_time_res[0][0] if avg_time_res and avg_time_res[0][0] else 0

        conv_res = ch.execute(
            f"""
            SELECT
                countIf(event_type = 'VIEW_STARTED') AS starts,
                countIf(event_type = 'VIEW_FINISHED') AS finishes
            FROM movie_events
            WHERE date = '{target_date}'
        """
        )
        starts, finishes = conv_res[0] if conv_res else (0, 0)
        conversion = (finishes / starts * 100) if starts > 0 else 0
        processed_events_res = ch.execute(f"SELECT count() FROM movie_events WHERE date = '{target_date}'")
        processed_events = processed_events_res[0][0] if processed_events_res else 0

        top_movies = ch.execute(
            f"""
            SELECT movie_id, count() AS views
            FROM movie_events
            WHERE date = '{target_date}' AND event_type = 'VIEW_STARTED'
            GROUP BY movie_id
            ORDER BY views DESC
            LIMIT 10
        """
        )

        retention_rows = []
        for day_num in range(0, 8):
            cohort_date = target_date - timedelta(days=day_num)
            _, _, ret_percent = _calculate_retention(ch, cohort_date=cohort_date, target_date=target_date)
            retention_rows.append((target_date, cohort_date, day_num, ret_percent))

        with pg.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO daily_metrics (date, metric_name, metric_value)
                VALUES %s
                ON CONFLICT (date, metric_name) DO UPDATE
                SET metric_value = EXCLUDED.metric_value, calculated_at = CURRENT_TIMESTAMP
                """,
                [
                    (target_date, "DAU", dau),
                    (target_date, "AVG_VIEW_TIME", avg_time),
                    (target_date, "CONVERSION", conversion),
                ],
            )

            if top_movies:
                execute_values(
                    cur,
                    """
                    INSERT INTO top_movies (date, movie_id, views_count)
                    VALUES %s
                    ON CONFLICT (date, movie_id) DO UPDATE
                    SET views_count = EXCLUDED.views_count, calculated_at = CURRENT_TIMESTAMP
                    """,
                    [(target_date, row[0], row[1]) for row in top_movies],
                )

            execute_values(
                cur,
                """
                INSERT INTO retention_metrics (report_date, cohort_date, day_number, retention_percent)
                VALUES %s
                ON CONFLICT (report_date, cohort_date, day_number) DO UPDATE
                SET retention_percent = EXCLUDED.retention_percent, calculated_at = CURRENT_TIMESTAMP
                """,
                retention_rows,
            )

        pg.commit()

        ch.execute(
            """
            INSERT INTO daily_metrics_agg (date, dau, avg_view_time, conversion_percent, calculated_at)
            VALUES
        """,
            [(target_date, int(dau), float(avg_time), float(conversion), datetime.utcnow())],
        )
        if top_movies:
            ch.execute(
                """
                INSERT INTO top_movies_agg (date, movie_id, views_count, calculated_at)
                VALUES
            """,
                [(target_date, row[0], int(row[1]), datetime.utcnow()) for row in top_movies],
            )
        ch.execute(
            """
            INSERT INTO retention_agg (report_date, cohort_date, day_number, retention_percent, calculated_at)
            VALUES
        """,
            [(row[0], row[1], row[2], float(row[3]), datetime.utcnow()) for row in retention_rows],
        )

        elapsed = time.time() - started_at
        logger.info(
            "Finished metrics calculation for %s: processed_events=%s elapsed=%.2fs",
            target_date,
            processed_events,
            elapsed,
        )

        export_to_s3(target_date)
    except Exception:
        pg.rollback()
        logger.exception("Metrics calculation failed for %s", target_date)
        raise
    finally:
        try:
            ch.disconnect()
        except Exception:
            pass
        pg.close()


def export_to_s3(target_date: date):
    logger.info("Starting S3 export for %s", target_date)
    pg = execute_with_retry("connect_postgres_export", get_pg_conn)
    s3 = execute_with_retry("connect_s3", get_s3_client)

    try:
        metrics = {}
        with pg.cursor() as cur:
            cur.execute("SELECT metric_name, metric_value FROM daily_metrics WHERE date = %s", (target_date,))
            for name, value in cur.fetchall():
                metrics[name] = float(value)

            cur.execute("SELECT movie_id, views_count FROM top_movies WHERE date = %s", (target_date,))
            metrics["top_movies"] = [{"movie_id": movie_id, "views": views} for movie_id, views in cur.fetchall()]

            cur.execute(
                """
                SELECT cohort_date, day_number, retention_percent
                FROM retention_metrics
                WHERE report_date = %s
            """,
                (target_date,),
            )
            retention_rows = cur.fetchall()
            metrics["retention"] = {
                f"D{day_number}": float(retention_percent) for _, day_number, retention_percent in retention_rows
            }
            metrics["retention_details"] = [
                {"cohort_date": str(cohort_date), "day_number": day_number, "retention_percent": float(retention_percent)}
                for cohort_date, day_number, retention_percent in retention_rows
            ]

        metrics["date"] = str(target_date)
        metrics["exported_at"] = datetime.utcnow().isoformat()

        s3_key = f"daily/{target_date.strftime('%Y-%m-%d')}/aggregates.json"

        execute_with_retry(
            "s3_put_object",
            lambda: s3.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=json.dumps(metrics, indent=2),
                ContentType="application/json",
            ),
        )
        logger.info("Exported to s3://%s/%s", S3_BUCKET, s3_key)
    finally:
        pg.close()


scheduler = BackgroundScheduler()


def daily_job():
    target_date = date.today() - timedelta(days=1)
    calculate_metrics_for_date(target_date)


@app.on_event("startup")
def startup():
    run_postgres_migrations()
    scheduler.add_job(daily_job, "cron", hour=AGGREGATION_CRON_HOUR, minute=AGGREGATION_CRON_MINUTE)
    scheduler.start()
    logger.info("Scheduler started at %02d:%02d", AGGREGATION_CRON_HOUR, AGGREGATION_CRON_MINUTE)


@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/calculate/{target_date}")
def manual_calculate(target_date: str):
    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d").date()
        calculate_metrics_for_date(dt)
        return {"status": "success", "date": target_date}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)

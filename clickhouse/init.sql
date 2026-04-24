CREATE DATABASE IF NOT EXISTS online_cinema;

USE online_cinema;

DROP VIEW IF EXISTS movie_events_mv;
DROP TABLE IF EXISTS movie_events_queue;

CREATE TABLE IF NOT EXISTS movie_events_queue (
    event_id String,
    user_id String,
    movie_id String,
    event_type Enum8('VIEW_STARTED' = 1, 'VIEW_FINISHED' = 2, 'VIEW_PAUSED' = 3, 'VIEW_RESUMED' = 4, 'LIKED' = 5, 'SEARCHED' = 6),
    timestamp Int64,
    device_type Enum8('MOBILE' = 1, 'DESKTOP' = 2, 'TV' = 3, 'TABLET' = 4),
    session_id String,
    progress_seconds Int32
) ENGINE = Kafka('kafka-1:9092,kafka-2:9092', 'movie-events', 'clickhouse_group1', 'AvroConfluent')
SETTINGS format_avro_schema_registry_url = 'http://schema-registry:8081';

CREATE TABLE IF NOT EXISTS movie_events (
    event_id String,
    user_id String,
    movie_id String,
    event_type Enum8('VIEW_STARTED' = 1, 'VIEW_FINISHED' = 2, 'VIEW_PAUSED' = 3, 'VIEW_RESUMED' = 4, 'LIKED' = 5, 'SEARCHED' = 6),
    timestamp DateTime64(3, 'UTC'),
    device_type Enum8('MOBILE' = 1, 'DESKTOP' = 2, 'TV' = 3, 'TABLET' = 4),
    session_id String,
    progress_seconds Int32,
    date Date MATERIALIZED toDate(timestamp)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (user_id, timestamp);

CREATE MATERIALIZED VIEW IF NOT EXISTS movie_events_mv TO movie_events AS
SELECT
    event_id,
    user_id,
    movie_id,
    event_type,
    fromUnixTimestamp64Milli(toInt64(timestamp)) AS timestamp,
    device_type,
    session_id,
    progress_seconds
FROM movie_events_queue;

CREATE TABLE IF NOT EXISTS daily_metrics_agg (
    date Date,
    dau UInt64,
    avg_view_time Float64,
    conversion_percent Float64,
    calculated_at DateTime
) ENGINE = ReplacingMergeTree(calculated_at)
ORDER BY date;

CREATE TABLE IF NOT EXISTS top_movies_agg (
    date Date,
    movie_id String,
    views_count UInt64,
    calculated_at DateTime
) ENGINE = ReplacingMergeTree(calculated_at)
ORDER BY (date, movie_id);

CREATE TABLE IF NOT EXISTS retention_agg (
    report_date Date,
    cohort_date Date,
    day_number UInt8,
    retention_percent Float64,
    calculated_at DateTime
) ENGINE = ReplacingMergeTree(calculated_at)
ORDER BY (report_date, cohort_date, day_number);

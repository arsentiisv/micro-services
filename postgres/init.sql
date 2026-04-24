CREATE TABLE IF NOT EXISTS daily_metrics (
    date DATE NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    metric_value NUMERIC NOT NULL,
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, metric_name)
);

CREATE TABLE IF NOT EXISTS top_movies (
    date DATE NOT NULL,
    movie_id VARCHAR(50) NOT NULL,
    views_count INT NOT NULL,
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date, movie_id)
);

CREATE TABLE IF NOT EXISTS retention_metrics (
    report_date DATE NOT NULL,
    cohort_date DATE NOT NULL,
    day_number INT NOT NULL,
    retention_percent NUMERIC NOT NULL,
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (report_date, cohort_date, day_number)
);

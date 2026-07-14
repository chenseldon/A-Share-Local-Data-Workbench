CREATE TABLE IF NOT EXISTS securities (
  symbol VARCHAR PRIMARY KEY,
  name VARCHAR NOT NULL,
  exchange VARCHAR NOT NULL,
  asset_type VARCHAR NOT NULL DEFAULT 'stock',
  listing_date DATE,
  sector VARCHAR,
  is_active BOOLEAN NOT NULL DEFAULT true,
  source VARCHAR NOT NULL,
  fetched_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS trading_calendar (
  exchange VARCHAR NOT NULL,
  trade_date DATE NOT NULL,
  is_open BOOLEAN NOT NULL,
  source VARCHAR NOT NULL,
  fetched_at TIMESTAMP NOT NULL,
  PRIMARY KEY (exchange, trade_date)
);

CREATE TABLE IF NOT EXISTS market_bars (
  symbol VARCHAR NOT NULL,
  trade_date DATE NOT NULL,
  open DOUBLE,
  high DOUBLE,
  low DOUBLE,
  close DOUBLE,
  volume DOUBLE,
  amount DOUBLE,
  adjustment VARCHAR NOT NULL DEFAULT 'none',
  source VARCHAR NOT NULL,
  fetched_at TIMESTAMP NOT NULL,
  raw_payload_hash VARCHAR NOT NULL,
  PRIMARY KEY (symbol, trade_date, adjustment, source)
);

CREATE TABLE IF NOT EXISTS fundamentals (
  symbol VARCHAR NOT NULL,
  report_period DATE NOT NULL,
  eps DOUBLE,
  roe DOUBLE,
  net_profit DOUBLE,
  revenue DOUBLE,
  total_market_cap DOUBLE,
  pe_ttm DOUBLE,
  pb DOUBLE,
  source VARCHAR NOT NULL,
  fetched_at TIMESTAMP NOT NULL,
  raw_payload_hash VARCHAR NOT NULL,
  PRIMARY KEY (symbol, report_period, source)
);

CREATE TABLE IF NOT EXISTS announcements (
  id VARCHAR PRIMARY KEY,
  symbol VARCHAR NOT NULL,
  title VARCHAR NOT NULL,
  published_at TIMESTAMP NOT NULL,
  url VARCHAR,
  source VARCHAR NOT NULL,
  fetched_at TIMESTAMP NOT NULL,
  raw_payload_hash VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
  id VARCHAR PRIMARY KEY,
  symbol VARCHAR NOT NULL,
  title VARCHAR NOT NULL,
  institution VARCHAR,
  analyst VARCHAR,
  rating VARCHAR,
  report_date DATE NOT NULL,
  eps_forecast VARCHAR,
  url VARCHAR,
  source VARCHAR NOT NULL,
  fetched_at TIMESTAMP NOT NULL,
  raw_payload_hash VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS money_flow (
  symbol VARCHAR NOT NULL,
  trade_date DATE NOT NULL,
  main_net_inflow DOUBLE,
  retail_net_inflow DOUBLE,
  turnover_rate DOUBLE,
  source VARCHAR NOT NULL,
  fetched_at TIMESTAMP NOT NULL,
  raw_payload_hash VARCHAR NOT NULL,
  PRIMARY KEY (symbol, trade_date, source)
);

CREATE TABLE IF NOT EXISTS limit_up_pool (
  trade_date DATE NOT NULL,
  symbol VARCHAR NOT NULL,
  name VARCHAR NOT NULL,
  reason VARCHAR,
  board_count INTEGER,
  status VARCHAR NOT NULL,
  source VARCHAR NOT NULL,
  fetched_at TIMESTAMP NOT NULL,
  raw_payload_hash VARCHAR NOT NULL,
  PRIMARY KEY (trade_date, symbol, source)
);

CREATE TABLE IF NOT EXISTS data_jobs (
  id VARCHAR PRIMARY KEY,
  job_type VARCHAR NOT NULL,
  module VARCHAR NOT NULL,
  source VARCHAR NOT NULL,
  status VARCHAR NOT NULL,
  started_at TIMESTAMP NOT NULL,
  finished_at TIMESTAMP,
  records_written INTEGER NOT NULL DEFAULT 0,
  error_message VARCHAR
);

CREATE TABLE IF NOT EXISTS source_health (
  source VARCHAR PRIMARY KEY,
  module VARCHAR NOT NULL,
  status VARCHAR NOT NULL,
  last_success_at TIMESTAMP,
  last_failure_at TIMESTAMP,
  last_error VARCHAR,
  updated_at TIMESTAMP NOT NULL
);

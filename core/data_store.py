"""Lightweight SQLite time-series store for sensor readings.

Records every numeric sensor value that flows through the event bus.
Provides history queries with automatic resolution selection:
  - Last hour: raw readings (~1 per 5 seconds)
  - Last 24 hours: 5-minute averages
  - Beyond 24 hours: hourly averages

Uses WAL mode for concurrent reads/writes from Flask threads.
Runs periodic cleanup to keep raw data under 7 days.
"""

import logging
import os
import sqlite3
import threading
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DataStore:
    """SQLite-backed sensor data store with automatic downsampling."""

    def __init__(self, db_path: str = "sensor_data.db"):
        self._db_path = db_path
        self._local = threading.local()
        self._write_lock = threading.Lock()
        self._write_buffer: List[Tuple[float, str, float]] = []
        self._buffer_lock = threading.Lock()
        self._flush_interval = 10.0  # seconds
        self._stop = threading.Event()
        self._flush_thread: Optional[threading.Thread] = None

        # Initialize schema on main connection
        conn = self._get_conn()
        self._init_tables(conn)

    def _get_conn(self) -> sqlite3.Connection:
        """Get a thread-local connection (SQLite isn't thread-safe)."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA cache_size=-8000")  # 8MB
        return self._local.conn

    def _init_tables(self, conn: sqlite3.Connection):
        """Create tables and indices if they don't exist."""
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS readings (
                timestamp REAL NOT NULL,
                field TEXT NOT NULL,
                value REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_readings_field_time
                ON readings(field, timestamp);

            CREATE TABLE IF NOT EXISTS hourly_avg (
                hour INTEGER NOT NULL,
                field TEXT NOT NULL,
                avg_value REAL,
                min_value REAL,
                max_value REAL,
                count INTEGER,
                PRIMARY KEY (hour, field)
            );
        """)
        conn.commit()

    def start(self):
        """Start the background flush thread."""
        if self._flush_thread and self._flush_thread.is_alive():
            return
        self._stop.clear()
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True, name="datastore-flush"
        )
        self._flush_thread.start()
        logger.info("DataStore started (db=%s)", self._db_path)

    def stop(self):
        """Stop the flush thread and write remaining buffer."""
        self._stop.set()
        self._flush_buffer()

    def record(self, field: str, value: float):
        """Buffer a reading for batch insert. Thread-safe."""
        with self._buffer_lock:
            self._write_buffer.append((time.time(), field, value))

    def _flush_loop(self):
        """Periodically flush buffered readings to disk."""
        while not self._stop.is_set():
            self._stop.wait(self._flush_interval)
            self._flush_buffer()
            # Hourly downsampling check
            self._maybe_downsample()

    def _flush_buffer(self):
        """Write buffered readings to SQLite."""
        with self._buffer_lock:
            if not self._write_buffer:
                return
            batch = self._write_buffer[:]
            self._write_buffer.clear()

        try:
            conn = self._get_conn()
            with self._write_lock:
                conn.executemany(
                    "INSERT INTO readings (timestamp, field, value) VALUES (?, ?, ?)",
                    batch,
                )
                conn.commit()
        except Exception as exc:
            logger.error("DataStore flush error: %s", exc)

    def _maybe_downsample(self):
        """Roll up completed hours into hourly_avg table."""
        try:
            conn = self._get_conn()
            # Find hours that have data but no hourly_avg yet
            # Only process hours that are complete (at least 1 hour old)
            cutoff_hour = int(time.time() / 3600) - 1  # previous complete hour

            rows = conn.execute("""
                SELECT DISTINCT CAST(timestamp / 3600 AS INTEGER) as hour, field
                FROM readings
                WHERE CAST(timestamp / 3600 AS INTEGER) <= ?
                AND NOT EXISTS (
                    SELECT 1 FROM hourly_avg
                    WHERE hourly_avg.hour = CAST(readings.timestamp / 3600 AS INTEGER)
                    AND hourly_avg.field = readings.field
                )
                LIMIT 100
            """, (cutoff_hour,)).fetchall()

            if not rows:
                return

            with self._write_lock:
                for hour, field in rows:
                    start_ts = hour * 3600
                    end_ts = start_ts + 3600
                    result = conn.execute("""
                        SELECT AVG(value), MIN(value), MAX(value), COUNT(*)
                        FROM readings
                        WHERE field = ? AND timestamp >= ? AND timestamp < ?
                    """, (field, start_ts, end_ts)).fetchone()

                    if result and result[3] > 0:
                        conn.execute("""
                            INSERT OR REPLACE INTO hourly_avg
                                (hour, field, avg_value, min_value, max_value, count)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (hour, field, result[0], result[1], result[2], result[3]))

                conn.commit()
                logger.debug("Downsampled %d hour/field pairs", len(rows))

        except Exception as exc:
            logger.error("DataStore downsample error: %s", exc)

    def get_history(
        self, field: str, hours: float = 24, max_points: int = 300
    ) -> List[Dict]:
        """Get historical data with auto-resolution.

        Returns list of {timestamp, value} dicts, sorted by time.
        Resolution adapts to time range for consistent point count.
        """
        conn = self._get_conn()
        cutoff = time.time() - (hours * 3600)

        if hours <= 1:
            # Raw data for last hour
            return self._raw_query(conn, field, cutoff, max_points)
        elif hours <= 24:
            # 5-minute averages for last day
            return self._averaged_query(conn, field, cutoff, 300, max_points)
        else:
            # Hourly averages for longer ranges
            return self._hourly_query(conn, field, cutoff, max_points)

    def _raw_query(
        self, conn: sqlite3.Connection, field: str, cutoff: float, limit: int
    ) -> List[Dict]:
        """Return raw readings since cutoff."""
        rows = conn.execute("""
            SELECT timestamp, value FROM readings
            WHERE field = ? AND timestamp >= ?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (field, cutoff, limit)).fetchall()
        return [{"t": r[0], "v": r[1]} for r in rows]

    def _averaged_query(
        self,
        conn: sqlite3.Connection,
        field: str,
        cutoff: float,
        bucket_secs: int,
        limit: int,
    ) -> List[Dict]:
        """Return bucket-averaged readings since cutoff."""
        rows = conn.execute("""
            SELECT
                CAST(timestamp / ? AS INTEGER) * ? as bucket_start,
                AVG(value), MIN(value), MAX(value)
            FROM readings
            WHERE field = ? AND timestamp >= ?
            GROUP BY bucket_start
            ORDER BY bucket_start ASC
            LIMIT ?
        """, (bucket_secs, bucket_secs, field, cutoff, limit)).fetchall()
        return [
            {"t": r[0] + bucket_secs / 2, "v": round(r[1], 2), "min": round(r[2], 2), "max": round(r[3], 2)}
            for r in rows
        ]

    def _hourly_query(
        self, conn: sqlite3.Connection, field: str, cutoff: float, limit: int
    ) -> List[Dict]:
        """Return hourly averages from pre-computed table."""
        cutoff_hour = int(cutoff / 3600)
        rows = conn.execute("""
            SELECT hour * 3600 + 1800, avg_value, min_value, max_value
            FROM hourly_avg
            WHERE field = ? AND hour >= ?
            ORDER BY hour ASC
            LIMIT ?
        """, (field, cutoff_hour, limit)).fetchall()
        return [
            {"t": r[0], "v": round(r[1], 2), "min": round(r[2], 2), "max": round(r[3], 2)}
            for r in rows
        ]

    def get_summary(self, hours: float = 24) -> Dict:
        """Get min/max/avg/current for all fields over time range."""
        conn = self._get_conn()
        cutoff = time.time() - (hours * 3600)

        rows = conn.execute("""
            SELECT field, AVG(value), MIN(value), MAX(value), COUNT(*)
            FROM readings
            WHERE timestamp >= ?
            GROUP BY field
        """, (cutoff,)).fetchall()

        summary = {}
        for field, avg, mn, mx, count in rows:
            # Get most recent value
            latest = conn.execute("""
                SELECT value FROM readings
                WHERE field = ? ORDER BY timestamp DESC LIMIT 1
            """, (field,)).fetchone()

            summary[field] = {
                "avg": round(avg, 2),
                "min": round(mn, 2),
                "max": round(mx, 2),
                "count": count,
                "current": round(latest[0], 2) if latest else None,
            }

        return summary

    def get_fields(self) -> List[str]:
        """Return list of all fields that have data."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT DISTINCT field FROM readings ORDER BY field"
        ).fetchall()
        return [r[0] for r in rows]

    def cleanup(self, max_days: int = 7):
        """Delete raw readings older than max_days. Hourly averages kept forever."""
        try:
            conn = self._get_conn()
            cutoff = time.time() - (max_days * 86400)
            with self._write_lock:
                result = conn.execute(
                    "DELETE FROM readings WHERE timestamp < ?", (cutoff,)
                )
                conn.commit()
                if result.rowcount > 0:
                    logger.info(
                        "DataStore cleanup: deleted %d readings older than %d days",
                        result.rowcount,
                        max_days,
                    )
        except Exception as exc:
            logger.error("DataStore cleanup error: %s", exc)

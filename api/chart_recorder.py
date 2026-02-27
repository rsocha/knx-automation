"""
Chart History Recorder
Records bound KO values periodically into SQLite for time-series charts.
"""

import asyncio
import json
import sqlite3
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("chart_recorder")

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "chart_history.db"
BINDINGS_PATH = DATA_DIR / "chart_bindings.json"

# Recording interval in seconds (default: 5 minutes)
RECORD_INTERVAL = 300
# Maximum age of data points (default: 90 days)
MAX_AGE_DAYS = 90


class ChartRecorder:
    """Records KO values into SQLite for historical chart display."""

    def __init__(self):
        self._db: Optional[sqlite3.Connection] = None
        self._task: Optional[asyncio.Task] = None
        self._db_manager = None
        self._bindings: dict = {}
        self._running = False

    def _ensure_db(self):
        """Initialize SQLite database and create table if needed."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                metric TEXT NOT NULL,
                value REAL NOT NULL
            )
        """)
        self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_metric_ts ON history(metric, ts)
        """)
        self._db.commit()
        logger.info(f"Chart history DB ready: {DB_PATH}")

    def load_bindings(self) -> dict:
        """Load chart bindings from file."""
        try:
            if BINDINGS_PATH.exists():
                with open(BINDINGS_PATH) as f:
                    data = json.load(f)
                self._bindings = data
                return data
        except Exception as e:
            logger.warning(f"Could not load chart bindings: {e}")
        return {}

    def save_bindings(self, bindings: dict):
        """Save chart bindings to file."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._bindings = bindings
        try:
            with open(BINDINGS_PATH, "w") as f:
                json.dump(bindings, f, ensure_ascii=False, indent=2)
            logger.info(f"Chart bindings saved: {len(bindings)} entries")
        except Exception as e:
            logger.error(f"Could not save chart bindings: {e}")

    async def record_once(self):
        """Record current values of all bound KOs."""
        if not self._db_manager or not self._bindings:
            return 0

        now = time.time()
        recorded = 0

        for metric_key, cfg in self._bindings.items():
            address = ""
            factor = 1.0
            if isinstance(cfg, str):
                address = cfg
            elif isinstance(cfg, dict):
                address = cfg.get("address", "")
                factor = cfg.get("factor", 1.0) or 1.0

            if not address:
                continue

            try:
                ga = await self._db_manager.get_group_address(address)
                if ga and ga.last_value is not None:
                    try:
                        raw = float(ga.last_value)
                        value = raw * factor
                        self._db.execute(
                            "INSERT INTO history (ts, metric, value) VALUES (?, ?, ?)",
                            (now, metric_key, value)
                        )
                        recorded += 1
                    except (ValueError, TypeError):
                        pass  # Non-numeric value, skip
            except Exception as e:
                logger.debug(f"Could not record {metric_key} ({address}): {e}")

        if recorded > 0:
            self._db.commit()
            logger.debug(f"Recorded {recorded} chart data points")

        return recorded

    def get_history(self, metrics: list[str], hours: int = 24) -> dict:
        """Get historical data for given metrics.
        
        Returns: {metric: [{ts: epoch, value: float}, ...]}
        """
        if not self._db:
            return {}

        cutoff = time.time() - (hours * 3600)
        result = {}

        for metric in metrics:
            try:
                cursor = self._db.execute(
                    "SELECT ts, value FROM history WHERE metric = ? AND ts >= ? ORDER BY ts ASC",
                    (metric, cutoff)
                )
                rows = cursor.fetchall()
                result[metric] = [{"ts": row[0], "value": row[1]} for row in rows]
            except Exception as e:
                logger.error(f"Error fetching history for {metric}: {e}")
                result[metric] = []

        return result

    def get_aggregated_history(self, metrics: list[str], hours: int = 24, bucket_minutes: int = 15) -> dict:
        """Get aggregated (averaged per bucket) historical data.
        
        Returns: {metric: [{ts: epoch, value: float, min: float, max: float}, ...]}
        """
        if not self._db:
            return {}

        cutoff = time.time() - (hours * 3600)
        bucket_seconds = bucket_minutes * 60
        result = {}

        for metric in metrics:
            try:
                cursor = self._db.execute(
                    """SELECT 
                        CAST((ts / ?) AS INTEGER) * ? as bucket_ts,
                        AVG(value) as avg_val,
                        MIN(value) as min_val,
                        MAX(value) as max_val,
                        COUNT(*) as cnt
                    FROM history 
                    WHERE metric = ? AND ts >= ?
                    GROUP BY bucket_ts
                    ORDER BY bucket_ts ASC""",
                    (bucket_seconds, bucket_seconds, metric, cutoff)
                )
                rows = cursor.fetchall()
                result[metric] = [
                    {"ts": row[0], "value": round(row[1], 2), "min": round(row[2], 2), "max": round(row[3], 2)}
                    for row in rows
                ]
            except Exception as e:
                logger.error(f"Error fetching aggregated history for {metric}: {e}")
                result[metric] = []

        return result

    def get_daily_totals(self, metrics: list[str], days: int = 7) -> dict:
        """Get daily totals (sum of avg per hour ≈ energy in Wh if input is W).
        
        Returns: {metric: [{date: "2026-02-27", total: float, avg: float, min: float, max: float}, ...]}
        """
        if not self._db:
            return {}

        cutoff = time.time() - (days * 86400)
        result = {}

        for metric in metrics:
            try:
                cursor = self._db.execute(
                    """SELECT 
                        date(ts, 'unixepoch', 'localtime') as day,
                        AVG(value) as avg_val,
                        MIN(value) as min_val,
                        MAX(value) as max_val,
                        COUNT(*) as cnt
                    FROM history 
                    WHERE metric = ? AND ts >= ?
                    GROUP BY day
                    ORDER BY day ASC""",
                    (metric, cutoff)
                )
                rows = cursor.fetchall()
                result[metric] = [
                    {
                        "date": row[0],
                        "avg": round(row[1], 2),
                        "min": round(row[2], 2),
                        "max": round(row[3], 2),
                        "count": row[4],
                        # Approximate energy: avg power * hours_recorded
                        # With 5min intervals, each sample represents 5min = 1/12 hour
                        "total_wh": round(row[1] * row[4] / 12, 0) if row[4] > 0 else 0,
                    }
                    for row in rows
                ]
            except Exception as e:
                logger.error(f"Error fetching daily totals for {metric}: {e}")
                result[metric] = []

        return result

    def cleanup_old_data(self):
        """Remove data points older than MAX_AGE_DAYS."""
        if not self._db:
            return
        cutoff = time.time() - (MAX_AGE_DAYS * 86400)
        try:
            cursor = self._db.execute("DELETE FROM history WHERE ts < ?", (cutoff,))
            deleted = cursor.rowcount
            if deleted > 0:
                self._db.commit()
                logger.info(f"Cleaned up {deleted} old chart data points")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def get_stats(self) -> dict:
        """Get recording stats."""
        if not self._db:
            return {"status": "not initialized"}
        try:
            count = self._db.execute("SELECT COUNT(*) FROM history").fetchone()[0]
            oldest = self._db.execute("SELECT MIN(ts) FROM history").fetchone()[0]
            newest = self._db.execute("SELECT MAX(ts) FROM history").fetchone()[0]
            metrics = [r[0] for r in self._db.execute("SELECT DISTINCT metric FROM history").fetchall()]
            return {
                "status": "running" if self._running else "stopped",
                "total_points": count,
                "oldest": datetime.fromtimestamp(oldest).isoformat() if oldest else None,
                "newest": datetime.fromtimestamp(newest).isoformat() if newest else None,
                "metrics": metrics,
                "bindings": {k: v.get("address", v) if isinstance(v, dict) else v for k, v in self._bindings.items()},
                "interval_seconds": RECORD_INTERVAL,
                "db_path": str(DB_PATH),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _recording_loop(self):
        """Background loop that records values periodically."""
        self._running = True
        logger.info(f"Chart recorder started (interval: {RECORD_INTERVAL}s)")
        
        # Initial recording after 30s startup delay
        await asyncio.sleep(30)
        
        while self._running:
            try:
                self.load_bindings()
                recorded = await self.record_once()
                
                # Cleanup once a day (check every cycle, cleanup based on modulo)
                if int(time.time()) % 86400 < RECORD_INTERVAL:
                    self.cleanup_old_data()
                    
            except Exception as e:
                logger.error(f"Chart recording error: {e}")

            await asyncio.sleep(RECORD_INTERVAL)

    async def start(self, db_manager):
        """Start the recording background task."""
        self._db_manager = db_manager
        self._ensure_db()
        self.load_bindings()
        self._task = asyncio.create_task(self._recording_loop())

    async def stop(self):
        """Stop the recording background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._db:
            self._db.close()
        logger.info("Chart recorder stopped")


# Singleton
chart_recorder = ChartRecorder()

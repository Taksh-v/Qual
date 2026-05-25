import time
import logging
import subprocess
import sys
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("data/ingestion.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def run_script(script_name: str, args: list = None):
    cmd = [sys.executable, script_name] + (args or [])
    logger.info(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"Finished {script_name} successfully.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running {script_name}: {e.stderr}")
        return False

def run_module(module_name: str, args: list = None):
    """Run a Python module via -m flag."""
    cmd = [sys.executable, "-m", module_name] + (args or [])
    logger.info(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"Finished {module_name} successfully.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running {module_name}: {e.stderr}")
        return False

def main_loop():
    logger.info("=== Starting Continuous Ingestion Wrapper (V3 Quantum) ===")
    
    # ── Timing Configuration ──
    PULSE_INTERVAL = 60           # Quantum Pulse: every 60 seconds
    PRIORITY_INTERVAL = 5 * 60    # Priority RSS: every 5 minutes
    FULL_INTERVAL = 15 * 60       # Full ingestion: every 15 minutes
    MACRO_INTERVAL = 3600         # Macro/Earnings: every hour
    WATCHDOG_INTERVAL = 3600      # Watchdog planning: every hour

    last_pulse = 0
    last_priority = 0
    last_full = 0
    last_macro = 0
    last_watchdog = 0

    while True:
        now = time.time()
        
        # Phase 0: Quantum Pulse (60s) — SEC Filings & Breaking News
        if now - last_pulse > PULSE_INTERVAL:
            logger.info(">>> Phase 0: Quantum Pulse (SEC & Breaking News)")
            run_module("ingestion.pulse_monitor", ["--once"])
            last_pulse = now

        # Phase 1: Priority RSS (5 min)
        if now - last_priority > PRIORITY_INTERVAL:
            logger.info(">>> Phase 1: Priority RSS Ingestion")
            run_script("run_rss_ingest.py", ["--priority-only"])
            last_priority = now
        
        # Phase 2: Full RSS (15 min)
        if now - last_full > FULL_INTERVAL:
            logger.info(">>> Phase 2: Full RSS Ingestion")
            run_script("run_rss_ingest.py")
            last_full = now

        # Phase 3: Macro, Market Data & Fundamentals (1 hour)
        if now - last_macro > MACRO_INTERVAL:
            logger.info(">>> Phase 3: Macro, Market Data & Fundamentals Refresh")
            run_module("ingestion.macro_feed")
            run_module("ingestion.earnings_calendar")
            run_module("ingestion.market_data_feed")
            run_module("ingestion.fundamentals_feed")
            last_macro = now

        # Phase 4: Watchdog Planning (1 hour)
        if now - last_watchdog > WATCHDOG_INTERVAL:
            logger.info(">>> Phase 4: Watchdog Planning (Mission Update)")
            run_script("intelligence/watchdog_planner.py")
            last_watchdog = now

        logger.info(f"Sleeping for 30s...")
        time.sleep(30)

if __name__ == "__main__":
    main_loop()

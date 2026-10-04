"""
src/orchestration/scheduler.py: Automated Pipeline Scheduler

Executes the SEC Financial Pipeline DAG on a configurable schedule (interval
or daily cron), logs execution heartbeats, and supports graceful termination.
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.common.logger import get_logger
from src.orchestration.dag import build_sec_pipeline_dag

logger = get_logger("scheduler_daemon")


class PipelineScheduler:
    """Interval and recurring time daemon for triggering the SEC DAG."""

    def __init__(self, interval_seconds: int = 7200):
        self.interval_seconds = interval_seconds
        self.running = False

    def start(self, run_immediately: bool = True) -> None:
        """Starts the scheduling loop until interrupted."""
        self.running = True
        logger.info(
            f"Scheduler da khoi dong. Chu ky lap: {self.interval_seconds} giay "
            f"({self.interval_seconds / 3600:.1f} gio). Bam Ctrl+C de dung."
        )

        dag = build_sec_pipeline_dag()

        if run_immediately:
            logger.info("-> Chay phien pipeline khoi dong ngay lap tuc...")
            dag.execute()

        try:
            while self.running:
                next_run = datetime.now() + timedelta(seconds=self.interval_seconds)
                logger.info(f"-> Dang ngu. Phien chay tiep theo du kien luc: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")

                # Sleep in short increments to respond promptly to Ctrl+C
                slept = 0
                while slept < self.interval_seconds and self.running:
                    time.sleep(1)
                    slept += 1

                if self.running:
                    logger.info(f"=== [SCHEDULER TRIGGER] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
                    dag.execute()

        except KeyboardInterrupt:
            logger.info("Nhan tin hieu dung tu nguoi dung (Ctrl+C). Dang tat scheduler...")
            self.stop()

    def stop(self) -> None:
        """Gracefully halts the scheduler daemon."""
        self.running = False
        logger.info("Scheduler da dung an toan.")


if __name__ == "__main__":
    print("--- Khoi dong Scheduler thu nghiem (chu ky 10 giay, chay 1 lan roi dung) ---")
    scheduler = PipelineScheduler(interval_seconds=10)
    scheduler.start(run_immediately=False)

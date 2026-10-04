"""
src/orchestration/task.py: Resilient Task Execution Engine

Encapsulates individual pipeline steps with state transitions, exponential
backoff retry with jitter, and pre/post-execution quality validation gates.
"""

import time
import random
import sys
from pathlib import Path

# Dam bao project root nam trong sys.path khi chay truc tiep file nay
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from datetime import datetime
from typing import Callable, Any

from src.common.logger import get_logger
from src.orchestration.state import TaskStatus, TaskResult
from src.orchestration.quality_gate import QualityGateFailure

logger = get_logger("task_executor")


class Task:
    """A resilient, executable unit of work in the orchestration pipeline."""

    def __init__(
        self,
        task_id: str,
        name: str,
        fn: Callable[..., Any],
        max_retries: int = 3,
        base_delay: float = 2.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
        pre_gate: Callable[[], None] | None = None,
        post_gate: Callable[[], None] | None = None,
    ):
        self.task_id = task_id
        self.name = name
        self.fn = fn
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter
        self.pre_gate = pre_gate
        self.post_gate = post_gate

    def run(self, *args: Any, **kwargs: Any) -> TaskResult:
        """Executes the task with pre-gate, retry with exponential backoff, and post-gate."""
        result = TaskResult(
            task_id=self.task_id,
            status=TaskStatus.RUNNING,
            start_time=datetime.now(),
        )

        logger.info(f"[{self.task_id}] Bat dau: {self.name}...")

        # 1. Pre-execution quality gate
        if self.pre_gate:
            try:
                self.pre_gate()
            except QualityGateFailure as qe:
                logger.error(f"[{self.task_id}] Pre-gate that bai: {qe}")
                result.mark_completed(TaskStatus.FAILED, error=f"Pre-gate failure: {qe}")
                return result

        # 2. Execution loop with exponential backoff retry
        attempt = 0
        last_error: Exception | None = None

        while attempt <= self.max_retries:
            try:
                if attempt > 0:
                    result.status = TaskStatus.RETRYING
                    result.retry_count = attempt
                    delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
                    if self.jitter:
                        delay += random.uniform(0.1, 1.0)
                    logger.warning(
                        f"[{self.task_id}] Thu lai lan {attempt}/{self.max_retries} "
                        f"sau {delay:.2f}s (Loi truoc do: {last_error})..."
                    )
                    time.sleep(delay)

                # Execute core function
                fn_output = self.fn(*args, **kwargs)
                if isinstance(fn_output, dict):
                    for k, v in fn_output.items():
                        result.metadata[k] = str(v) if isinstance(v, Path) else v
                elif isinstance(fn_output, Path):
                    result.metadata["output"] = str(fn_output)
                elif fn_output is not None:
                    result.metadata["output"] = fn_output

                # 3. Post-execution quality gate
                if self.post_gate:
                    self.post_gate()

                result.mark_completed(TaskStatus.SUCCESS)
                logger.info(
                    f"[{self.task_id}] Thanh cong ({result.duration_ms:,.1f}ms, "
                    f"retries={result.retry_count})"
                )
                return result

            except Exception as e:
                attempt += 1
                last_error = e
                logger.error(f"[{self.task_id}] Loi thuc thi (lan {attempt}): {e}")

        # If exhausted all retries
        error_msg = f"Exhausted {self.max_retries} retries. Final error: {last_error}"
        result.mark_completed(TaskStatus.FAILED, error=error_msg)
        logger.critical(f"[{self.task_id}] That bai hoan toan sau {self.max_retries} lan thu lai.")
        return result


if __name__ == "__main__":
    # Test nhanh don le khi chay truc tiep: python src/orchestration/task.py
    print("--- Test Task Resilience & Retry ---")
    counter = 0

    def unreliable_operation():
        global counter
        counter += 1
        if counter < 3:
            raise ConnectionError(f"Simulated network dropout (attempt {counter})")
        print("  -> Ket noi thanh cong!")

    test_task = Task(
        task_id="test_unreliable",
        name="Thu nghiem tu phuc hoi mang",
        fn=unreliable_operation,
        max_retries=3,
        base_delay=0.5,
        backoff_factor=1.5,
    )
    res = test_task.run()
    print("Ket qua Task:", res.to_dict())

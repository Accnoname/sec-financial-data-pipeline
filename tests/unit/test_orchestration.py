"""
tests/unit/test_orchestration.py: Unit Tests for DAG Orchestration Engine
"""

import pytest
from pathlib import Path

from src.orchestration.state import TaskStatus, TaskResult
from src.orchestration.task import Task
from src.orchestration.dag import PipelineDAG
from src.orchestration.quality_gate import QualityGate, QualityGateFailure


def test_task_success():
    """Verify that a healthy task executes and reports SUCCESS with duration."""
    t = Task(task_id="success_task", name="Healthy Task", fn=lambda: 42)
    res = t.run()
    assert res.status == TaskStatus.SUCCESS
    assert res.retry_count == 0
    assert res.duration_ms >= 0


def test_task_retry_mechanism():
    """Verify exponential backoff retry recovers from transient failures."""
    attempts = 0

    def flaky_func():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise ConnectionResetError(f"Flaky error {attempts}")
        return "Recovered"

    t = Task(
        task_id="flaky_task",
        name="Flaky Task",
        fn=flaky_func,
        max_retries=3,
        base_delay=0.05,
        backoff_factor=1.2,
        jitter=False,
    )
    res = t.run()
    assert res.status == TaskStatus.SUCCESS
    assert res.retry_count == 2
    assert attempts == 3


def test_task_exhausted_retries():
    """Verify task marks FAILED after exhausting all retry attempts."""
    def always_fails():
        raise RuntimeError("Permanent failure")

    t = Task(
        task_id="doomed_task",
        name="Doomed Task",
        fn=always_fails,
        max_retries=2,
        base_delay=0.02,
        jitter=False,
    )
    res = t.run()
    assert res.status == TaskStatus.FAILED
    assert "Permanent failure" in (res.error_message or "")
    assert res.retry_count == 2


def test_quality_gate_assert_file(tmp_path: Path):
    """Verify QualityGate raises QualityGateFailure on missing or undersized files."""
    test_file = tmp_path / "sample.txt"

    # Missing file
    with pytest.raises(QualityGateFailure):
        QualityGate.assert_file_exists(test_file, min_bytes=50)

    # Undersized file
    test_file.write_text("tiny", encoding="utf-8")
    with pytest.raises(QualityGateFailure):
        QualityGate.assert_file_exists(test_file, min_bytes=50)

    # Sufficient file
    test_file.write_text("a" * 100, encoding="utf-8")
    QualityGate.assert_file_exists(test_file, min_bytes=50)


def test_dag_dependency_skipping():
    """Verify downstream tasks are SKIPPED if their upstream dependency fails."""
    dag = PipelineDAG("test_dag")

    def failing_step():
        raise ValueError("Fatal upstream failure")

    t1 = Task("step_root", "Root Step", fn=failing_step, max_retries=1, base_delay=0.01)
    t2 = Task("step_child", "Child Step", fn=lambda: "Should not run")

    dag.add_task(t1)
    dag.add_task(t2, upstream_ids=["step_root"])

    results = dag.execute()
    assert results["step_root"].status == TaskStatus.FAILED
    assert results["step_child"].status == TaskStatus.SKIPPED

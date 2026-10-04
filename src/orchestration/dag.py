"""
src/orchestration/dag.py: Directed Acyclic Graph (DAG) Pipeline Orchestrator

Defines task dependencies, executes tasks topologically, enforces quality gates
between layers, and maintains structured audit logs in JSONL format.
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Dam bao project root nam trong sys.path khi chay truc tiep file nay
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.common.config import RAW_DIR, STAGING_DIR, PRIMARY_DIR, CURATED_DIR, PROJECT_ROOT
from src.common.logger import get_logger
from src.orchestration.state import TaskStatus, TaskResult
from src.orchestration.task import Task
from src.orchestration.quality_gate import QualityGate

logger = get_logger("dag_orchestrator")
AUDIT_LOG_PATH = PROJECT_ROOT / "logs" / "orchestration_audit.jsonl"
AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


class PipelineDAG:
    """Manages DAG task registration, dependency tracking, and execution."""

    def __init__(self, dag_id: str = "sec_financial_pipeline", force: bool = False):
        self.dag_id = dag_id
        self.force = force
        self.tasks: dict[str, Task] = {}
        self.dependencies: dict[str, list[str]] = {}

    def add_task(self, task: Task, upstream_ids: list[str] | None = None) -> None:
        """Registers a task with its upstream prerequisite task IDs."""
        self.tasks[task.task_id] = task
        self.dependencies[task.task_id] = upstream_ids or []

    def execute(self) -> dict[str, TaskResult]:
        """
        Executes registered tasks in topological dependency order.
        Aborts downstream tasks if an upstream dependency fails.
        Short-circuits redundant tasks if no data changes are detected.
        """
        run_id = datetime.now().strftime("run_%Y%m%d_%H%M%S")
        mode = "FORCE RECOMPUTE" if self.force else "INCREMENTAL / SENSOR"
        logger.info(f"=== KHOI DONG PIPELINE DAG [{self.dag_id}] ({mode}, Run ID: {run_id}) ===")

        results: dict[str, TaskResult] = {}

        for task_id, task in self.tasks.items():
            # Check upstreams for critical failures
            upstreams = self.dependencies.get(task_id, [])
            failed_upstreams = [
                u for u in upstreams
                if results.get(u, None) and results[u].status == TaskStatus.FAILED
            ]

            if failed_upstreams:
                logger.warning(
                    f"[{task_id}] Bo qua (SKIPPED) do task nguon that bai: {failed_upstreams}"
                )
                skipped_res = TaskResult(
                    task_id=task_id,
                    status=TaskStatus.SKIPPED,
                    start_time=datetime.now(),
                    error_message=f"Upstream task(s) failed: {failed_upstreams}",
                )
                skipped_res.mark_completed(TaskStatus.SKIPPED)
                results[task_id] = skipped_res
                continue

            # Short-circuit downstream tasks if step 3 detected no delta and cache exists
            if not self.force and task_id in (
                "step_4_extract_risk_factors",
                "step_5_chunk_risk_factors",
                "step_6_build_vector_index",
            ):
                ingest_res = results.get("step_3_ingest_filings")
                if ingest_res and not ingest_res.metadata.get("has_changes", True):
                    can_skip = False
                    if task_id == "step_4_extract_risk_factors":
                        can_skip = (STAGING_DIR / "sec_filings").exists()
                    elif task_id == "step_5_chunk_risk_factors":
                        can_skip = (PRIMARY_DIR / "chunks" / "all_chunks.parquet").exists()
                    elif task_id == "step_6_build_vector_index":
                        can_skip = (CURATED_DIR / "vector_db").exists()

                    if can_skip:
                        logger.info(
                            f"[{task_id}] Bo qua (SKIPPED): Khong phat hien ban 10-K moi tu SEC EDGAR va du lieu da san sang."
                        )
                        skipped_res = TaskResult(
                            task_id=task_id,
                            status=TaskStatus.SKIPPED,
                            start_time=datetime.now(),
                            error_message="Skipped: No new filings detected from SEC (cache valid).",
                        )
                        skipped_res.mark_completed(TaskStatus.SKIPPED)
                        results[task_id] = skipped_res
                        self._write_audit_log(run_id, skipped_res)
                        continue

            # Execute task
            result = task.run()
            results[task_id] = result

            # Append to audit log
            self._write_audit_log(run_id, result)

            # Log on failure
            if result.status == TaskStatus.FAILED:
                logger.error(f"[{task_id}] Task that bai. Cac task phu thuoc phia sau se bi SKIPPED.")

        # Summary report
        success_or_skipped = sum(
            1 for r in results.values() if r.status in (TaskStatus.SUCCESS, TaskStatus.SKIPPED)
        )
        logger.info(
            f"=== KET THUC DAG [{self.dag_id}] - Hoan tat: {success_or_skipped}/{len(self.tasks)} tasks ==="
        )
        return results

    def _write_audit_log(self, run_id: str, result: TaskResult) -> None:
        """Appends structured audit record to JSONL file."""
        record = {
            "run_id": run_id,
            "dag_id": self.dag_id,
            "timestamp": datetime.now().isoformat(),
            **result.to_dict(),
        }
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def build_sec_pipeline_dag(force: bool = False) -> PipelineDAG:
    """Factory function constructing the full 6-step SEC Financial Pipeline DAG."""
    from src.ingestion.extract_companies import fetch_and_save_companies
    from src.transformation.clean_companies import clean_companies
    from src.ingestion.ingest_10k_filings import ingest_filings
    from src.transformation.clean_10k_to_text import extract_all_risk_factors
    from src.rag.chunking import chunk_all_risk_factors
    from src.rag.embedder import build_vector_index

    dag = PipelineDAG(dag_id="sec_financial_data_and_rag_pipeline", force=force)

    # Step 1: Bronze Ingestion
    t1 = Task(
        task_id="step_1_extract_companies",
        name="Thu thap danh muc cong ty tu SEC EDGAR",
        fn=lambda: fetch_and_save_companies(force=force),
        max_retries=3,
        post_gate=lambda: QualityGate.assert_file_exists(
            RAW_DIR / "companies" / "all_companies.json", min_bytes=100_000
        ),
    )
    dag.add_task(t1)

    # Step 2: Silver Cleaning
    t2 = Task(
        task_id="step_2_clean_companies",
        name="Chuan hoa CIK 10 so va xuat Parquet Silver",
        fn=clean_companies,
        max_retries=2,
        pre_gate=lambda: QualityGate.assert_file_exists(
            RAW_DIR / "companies" / "all_companies.json"
        ),
        post_gate=lambda: QualityGate.assert_parquet_schema(
            STAGING_DIR / "companies_clean.parquet",
            expected_columns={"cik", "ticker", "name"},
            min_rows=10_000,
        ),
    )
    dag.add_task(t2, upstream_ids=["step_1_extract_companies"])

    # Step 3: Bronze 10-K Filings Download
    t3 = Task(
        task_id="step_3_ingest_filings",
        name="Tai Form 10-K goc cua 7 tap doan cong nghe",
        fn=lambda: ingest_filings(force=force),
        max_retries=3,
        base_delay=3.0,
    )
    dag.add_task(t3, upstream_ids=["step_2_clean_companies"])

    # Step 4: Silver Item 1A Risk Factors Extraction
    t4 = Task(
        task_id="step_4_extract_risk_factors",
        name="Boc tach Markdown Item 1A Risk Factors",
        fn=extract_all_risk_factors,
        max_retries=2,
    )
    dag.add_task(t4, upstream_ids=["step_3_ingest_filings"])

    # Step 5: Gold Semantic Chunking
    t5 = Task(
        task_id="step_5_chunk_risk_factors",
        name="Cat doan semantic chunking nạp Tang Gold",
        fn=chunk_all_risk_factors,
        max_retries=2,
        post_gate=lambda: QualityGate.assert_parquet_schema(
            PRIMARY_DIR / "chunks" / "all_chunks.parquet",
            expected_columns={"chunk_id", "ticker", "year", "text", "word_count"},
            min_rows=200,
        ),
    )
    dag.add_task(t5, upstream_ids=["step_4_extract_risk_factors"])

    # Step 6: Curated Vector Indexing
    t6 = Task(
        task_id="step_6_build_vector_index",
        name="Tao vector embedding va luu vao ChromaDB",
        fn=build_vector_index,
        max_retries=2,
        post_gate=lambda: QualityGate.assert_vector_collection(
            CURATED_DIR / "vector_db",
            collection_name="sec_risk_factors",
            min_vectors=200,
        ),
    )
    dag.add_task(t6, upstream_ids=["step_5_chunk_risk_factors"])

    return dag



if __name__ == "__main__":
    print("--- Chay thu nghiem DAG Pipeline ---")
    pipeline = build_sec_pipeline_dag()
    results = pipeline.execute()
    print("\nTong ket trang thai cac task:")
    for tid, r in results.items():
        print(f"  {tid:30}: {r.status.value:10} ({r.duration_ms:,.1f}ms)")

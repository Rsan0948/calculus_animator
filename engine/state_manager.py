"""State persistence using SQLite."""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from engine.state import (
    Constraint,
    FormalizedProblem,
    GeneratedFile,
    GuardrailReport,
    MVPAttempt,
    MVPOutput,
    MathResult,
    MathStep,
    RUN_STAGE_ORDER,
    RunArtifactRef,
    RunRecord,
    RunStageName,
    RunStageRecord,
    SourceDocument,
    Variable,
    utc_now,
)

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".research_engine" / "state.db"


class StateManager:
    """Manages persistence of pipeline state."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS problems (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    title TEXT,
                    domain_tags TEXT,
                    objective TEXT,
                    variables TEXT,
                    constraints TEXT,
                    source_document TEXT,
                    status TEXT DEFAULT 'pending'
                );

                CREATE TABLE IF NOT EXISTS math_results (
                    id TEXT PRIMARY KEY,
                    problem_id TEXT REFERENCES problems(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    plugin_used TEXT,
                    success BOOLEAN,
                    final_answer TEXT,
                    steps TEXT,
                    metadata TEXT,
                    failure_reason TEXT
                );

                CREATE TABLE IF NOT EXISTS mvp_outputs (
                    id TEXT PRIMARY KEY,
                    problem_id TEXT REFERENCES problems(id),
                    math_result_id TEXT REFERENCES math_results(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    root_directory TEXT,
                    guardrail_pass BOOLEAN,
                    files TEXT,
                    guardrail_report TEXT,
                    attempt_history TEXT,
                    install_command TEXT,
                    run_command TEXT
                );

                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    problem_id TEXT,
                    source_path TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_fingerprint TEXT NOT NULL,
                    command_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_stage TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_error TEXT,
                    config TEXT
                );

                CREATE TABLE IF NOT EXISTS run_stages (
                    run_id TEXT NOT NULL REFERENCES runs(id),
                    stage_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    error TEXT,
                    metadata TEXT,
                    PRIMARY KEY (run_id, stage_name)
                );

                CREATE TABLE IF NOT EXISTS run_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL REFERENCES runs(id),
                    stage_name TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    path TEXT NOT NULL,
                    summary TEXT,
                    metadata TEXT,
                    content_hash TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_problems_status ON problems(status);
                CREATE INDEX IF NOT EXISTS idx_math_results_problem ON math_results(problem_id);
                CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
                CREATE INDEX IF NOT EXISTS idx_run_artifacts_run_stage ON run_artifacts(run_id, stage_name);
                """
            )
            self._ensure_column(conn, "mvp_outputs", "guardrail_report", "TEXT")
            self._ensure_column(conn, "mvp_outputs", "attempt_history", "TEXT")
            self._ensure_column(conn, "mvp_outputs", "install_command", "TEXT")
            self._ensure_column(conn, "mvp_outputs", "run_command", "TEXT")

    def save_problem(self, problem: FormalizedProblem) -> None:
        """Save or update a formalized problem."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO problems
                   (id, title, domain_tags, objective, variables, constraints,
                    source_document, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    problem.id,
                    problem.title,
                    json.dumps(problem.domain_tags),
                    problem.objective,
                    json.dumps([variable.model_dump(mode="json") for variable in problem.variables]),
                    json.dumps([constraint.model_dump(mode="json") for constraint in problem.constraints]),
                    json.dumps(problem.source_document.model_dump(mode="json")),
                    "pending",
                ),
            )
        logger.info("Saved problem %s", problem.id)

    def update_problem_status(self, problem_id: str, status: str) -> None:
        """Update problem status."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE problems SET status = ? WHERE id = ?", (status, problem_id))

    def save_math_result(self, problem_id: str, result: MathResult) -> None:
        """Save a math result."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO math_results
                   (id, problem_id, plugin_used, success, final_answer,
                    steps, metadata, failure_reason)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.problem_id + "_math",
                    problem_id,
                    result.plugin_used,
                    result.success,
                    result.final_answer,
                    json.dumps([step.model_dump(mode="json") for step in result.steps]),
                    json.dumps(result.metadata),
                    json.dumps(result.failure_reason) if result.failure_reason else None,
                ),
            )
        self.update_problem_status(problem_id, "solved" if result.success else "failed")
        logger.info("Saved math result for %s", problem_id)

    def save_mvp(self, problem_id: str, math_result_id: str, mvp: MVPOutput) -> None:
        """Save an MVP output."""
        guardrail_pass = mvp.guardrail_report.overall_pass if mvp.guardrail_report else False
        serialized_files = json.dumps([generated_file.model_dump(mode="json") for generated_file in mvp.files])
        serialized_report = (
            json.dumps(mvp.guardrail_report.model_dump(mode="json"))
            if mvp.guardrail_report
            else None
        )
        serialized_attempts = json.dumps([attempt.model_dump(mode="json") for attempt in mvp.attempt_history])
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO mvp_outputs
                   (id, problem_id, math_result_id, root_directory,
                    guardrail_pass, files, guardrail_report, attempt_history,
                    install_command, run_command)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    mvp.problem_id + "_mvp",
                    problem_id,
                    math_result_id,
                    mvp.root_directory,
                    guardrail_pass,
                    serialized_files,
                    serialized_report,
                    serialized_attempts,
                    mvp.install_command,
                    mvp.run_command,
                ),
            )
        logger.info("Saved MVP for %s", problem_id)

    def create_run(self, run: RunRecord) -> None:
        """Persist a new run record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO runs
                   (id, problem_id, source_path, source_type, source_fingerprint,
                    command_name, status, current_stage, created_at, updated_at,
                    last_error, config)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run.id,
                    run.problem_id,
                    run.source_path,
                    run.source_type,
                    run.source_fingerprint,
                    run.command_name,
                    run.status,
                    run.current_stage,
                    self._serialize_datetime(run.created_at),
                    self._serialize_datetime(run.updated_at),
                    json.dumps(run.last_error) if run.last_error is not None else None,
                    json.dumps(run.config),
                ),
            )

    def start_stage(
        self,
        run_id: str,
        stage_name: RunStageName,
        metadata: Optional[dict[str, Any]] = None,
        problem_id: Optional[str] = None,
    ) -> None:
        """Mark a stage as running."""
        timestamp = self._now_string()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO run_stages (run_id, stage_name, status, started_at, completed_at, error, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, stage_name) DO UPDATE SET
                    status = excluded.status,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    error = excluded.error,
                    metadata = excluded.metadata
                """,
                (run_id, stage_name, "running", timestamp, None, None, json.dumps(metadata or {})),
            )
            conn.execute(
                """
                UPDATE runs
                SET status = ?, current_stage = ?, updated_at = ?, last_error = ?,
                    problem_id = COALESCE(?, problem_id)
                WHERE id = ?
                """,
                ("running", stage_name, timestamp, None, problem_id, run_id),
            )

    def complete_stage(
        self,
        run_id: str,
        stage_name: RunStageName,
        metadata: Optional[dict[str, Any]] = None,
        artifacts: Optional[list[RunArtifactRef]] = None,
        problem_id: Optional[str] = None,
    ) -> None:
        """Mark a stage as completed and persist its artifacts."""
        timestamp = self._now_string()
        with sqlite3.connect(self.db_path) as conn:
            started_at = self._get_stage_started_at(conn, run_id, stage_name) or timestamp
            conn.execute(
                """
                INSERT INTO run_stages (run_id, stage_name, status, started_at, completed_at, error, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, stage_name) DO UPDATE SET
                    status = excluded.status,
                    started_at = COALESCE(run_stages.started_at, excluded.started_at),
                    completed_at = excluded.completed_at,
                    error = excluded.error,
                    metadata = excluded.metadata
                """,
                (run_id, stage_name, "completed", started_at, timestamp, None, json.dumps(metadata or {})),
            )
            self._replace_run_artifacts(conn, run_id, stage_name, artifacts or [])
            conn.execute(
                """
                UPDATE runs
                SET status = ?, current_stage = ?, updated_at = ?, last_error = ?,
                    problem_id = COALESCE(?, problem_id)
                WHERE id = ?
                """,
                ("running", stage_name, timestamp, None, problem_id, run_id),
            )

    def fail_stage(
        self,
        run_id: str,
        stage_name: RunStageName,
        error: dict[str, Any] | str,
        metadata: Optional[dict[str, Any]] = None,
        artifacts: Optional[list[RunArtifactRef]] = None,
        problem_id: Optional[str] = None,
    ) -> None:
        """Mark a stage as failed and persist diagnostic artifacts."""
        timestamp = self._now_string()
        serialized_error = json.dumps(error)
        with sqlite3.connect(self.db_path) as conn:
            started_at = self._get_stage_started_at(conn, run_id, stage_name) or timestamp
            conn.execute(
                """
                INSERT INTO run_stages (run_id, stage_name, status, started_at, completed_at, error, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, stage_name) DO UPDATE SET
                    status = excluded.status,
                    started_at = COALESCE(run_stages.started_at, excluded.started_at),
                    completed_at = excluded.completed_at,
                    error = excluded.error,
                    metadata = excluded.metadata
                """,
                (
                    run_id,
                    stage_name,
                    "failed",
                    started_at,
                    timestamp,
                    serialized_error,
                    json.dumps(metadata or {}),
                ),
            )
            self._replace_run_artifacts(conn, run_id, stage_name, artifacts or [])
            conn.execute(
                """
                UPDATE runs
                SET status = ?, current_stage = ?, updated_at = ?, last_error = ?,
                    problem_id = COALESCE(?, problem_id)
                WHERE id = ?
                """,
                ("failed", stage_name, timestamp, serialized_error, problem_id, run_id),
            )

    def complete_run(self, run_id: str, current_stage: Optional[RunStageName] = None) -> None:
        """Mark a run as completed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE runs SET status = ?, current_stage = ?, updated_at = ?, last_error = ? WHERE id = ?",
                ("completed", current_stage, self._now_string(), None, run_id),
            )

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        """Return one persisted run, if it exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return self._row_to_run(dict(row))

    def list_runs(self) -> list[RunRecord]:
        """List persisted runs in reverse chronological order."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        return [self._row_to_run(dict(row)) for row in rows]

    def get_run_stages(self, run_id: str) -> list[RunStageRecord]:
        """Return stage records for a run in execution order."""
        artifacts_by_stage: dict[str, list[RunArtifactRef]] = {}
        for artifact in self.get_run_artifacts(run_id):
            artifacts_by_stage.setdefault(artifact.stage_name, []).append(artifact)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM run_stages WHERE run_id = ?",
                (run_id,),
            ).fetchall()

        records = [self._row_to_run_stage(dict(row), artifacts_by_stage.get(row["stage_name"], [])) for row in rows]
        return sorted(records, key=lambda record: RUN_STAGE_ORDER.get(record.stage_name, 999))

    def get_run_artifacts(
        self,
        run_id: str,
        stage_name: Optional[RunStageName] = None,
    ) -> list[RunArtifactRef]:
        """Return persisted artifact references for a run."""
        query = "SELECT * FROM run_artifacts WHERE run_id = ?"
        params: tuple[Any, ...] = (run_id,)
        if stage_name is not None:
            query += " AND stage_name = ?"
            params = (run_id, stage_name)
        query += " ORDER BY id ASC"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_artifact(dict(row)) for row in rows]

    def invalidate_stage_and_downstream(self, run_id: str, stage_name: RunStageName) -> None:
        """Mark one stage and all downstream stages invalidated, clearing their artifacts."""
        start_index = RUN_STAGE_ORDER[stage_name]
        timestamp = self._now_string()
        downstream_stages = [
            candidate
            for candidate, index in RUN_STAGE_ORDER.items()
            if index >= start_index
        ]

        with sqlite3.connect(self.db_path) as conn:
            for candidate in downstream_stages:
                conn.execute(
                    "DELETE FROM run_artifacts WHERE run_id = ? AND stage_name = ?",
                    (run_id, candidate),
                )
                conn.execute(
                    """
                    INSERT INTO run_stages (run_id, stage_name, status, started_at, completed_at, error, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id, stage_name) DO UPDATE SET
                        status = excluded.status,
                        started_at = excluded.started_at,
                        completed_at = excluded.completed_at,
                        error = excluded.error,
                        metadata = excluded.metadata
                    """,
                    (run_id, candidate, "invalidated", None, None, None, json.dumps({})),
                )
            conn.execute(
                "UPDATE runs SET status = ?, current_stage = ?, updated_at = ?, last_error = ? WHERE id = ?",
                ("pending", stage_name, timestamp, None, run_id),
            )

    def list_problems(self, status: Optional[str] = None) -> list[dict[str, Any]]:
        """List all problems, optionally filtered by status."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if status:
                rows = conn.execute(
                    "SELECT * FROM problems WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM problems ORDER BY created_at DESC").fetchall()
            return [dict(row) for row in rows]

    def get_problem(self, problem_id: str) -> Optional[FormalizedProblem]:
        """Retrieve a problem by ID."""
        row = self.get_problem_record(problem_id)
        if not row:
            return None

        variables = self._load_models(row.get("variables"), Variable)
        constraints = self._load_models(row.get("constraints"), Constraint)
        source_doc = self._load_model(row.get("source_document"), SourceDocument, SourceDocument())

        return FormalizedProblem(
            id=row["id"],
            title=row.get("title") or "",
            domain_tags=self._load_json(row.get("domain_tags"), []),
            objective=row.get("objective") or "",
            variables=variables,
            constraints=constraints,
            source_document=source_doc,
        )

    def get_problem_record(self, problem_id: str) -> Optional[dict[str, Any]]:
        """Return the raw stored problem row, including persistence metadata."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()
        return dict(row) if row else None

    def get_math_result(self, problem_id: str) -> Optional[MathResult]:
        """Return the latest math result for a problem, if one exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT *
                FROM math_results
                WHERE problem_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (problem_id,),
            ).fetchone()

        if not row:
            return None

        failure_reason = self._load_json(row["failure_reason"], None)
        steps = self._load_models(row["steps"], MathStep)
        metadata = self._load_json(row["metadata"], {})

        return MathResult(
            problem_id=row["problem_id"],
            plugin_used=row["plugin_used"],
            success=bool(row["success"]),
            final_answer=row["final_answer"],
            steps=steps,
            metadata=metadata,
            failure_reason=failure_reason,
        )

    def get_mvp(self, problem_id: str) -> Optional[MVPOutput]:
        """Return the latest MVP output for a problem, if one exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT *
                FROM mvp_outputs
                WHERE problem_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (problem_id,),
            ).fetchone()

        if not row:
            return None

        file_entries = self._load_json(row["files"], [])
        generated_files = []
        for entry in file_entries:
            try:
                generated_files.append(GeneratedFile(**entry))
            except TypeError:
                generated_files.append(
                    GeneratedFile(
                        relative_path=entry.get("path", ""),
                        content=entry.get("content", ""),
                        purpose=entry.get("purpose", ""),
                    )
                )

        guardrail_payload = self._load_json(row["guardrail_report"], None)
        guardrail_report: GuardrailReport | None = None
        if guardrail_payload:
            try:
                guardrail_report = GuardrailReport.model_validate(guardrail_payload)
            except Exception:
                guardrail_report = None
        if guardrail_report is None:
            guardrail_report = GuardrailReport(
                target_path=row["root_directory"],
                overall_pass=bool(row["guardrail_pass"]),
            )

        attempt_entries = self._load_json(row["attempt_history"], [])
        attempt_history: list[MVPAttempt] = []
        for entry in attempt_entries:
            try:
                attempt_history.append(MVPAttempt(**entry))
            except TypeError:
                logger.warning("Skipping malformed MVPAttempt entry in persisted state")

        return MVPOutput(
            problem_id=problem_id,
            root_directory=row["root_directory"],
            files=generated_files,
            guardrail_report=guardrail_report,
            attempt_history=attempt_history,
            install_command=row["install_command"] or "pip install -e .",
            run_command=row["run_command"] or "python main.py",
        )

    def delete_problem(self, problem_id: str) -> None:
        """Delete a problem and all associated data."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM mvp_outputs WHERE problem_id = ?", (problem_id,))
            conn.execute("DELETE FROM math_results WHERE problem_id = ?", (problem_id,))
            conn.execute("DELETE FROM problems WHERE id = ?", (problem_id,))
        logger.info("Deleted problem %s", problem_id)

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
        """Ensure a column exists for forward-compatible SQLite migrations."""
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing_columns = {row[1] for row in rows}
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

    def _replace_run_artifacts(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        stage_name: RunStageName,
        artifacts: list[RunArtifactRef],
    ) -> None:
        conn.execute("DELETE FROM run_artifacts WHERE run_id = ? AND stage_name = ?", (run_id, stage_name))
        created_at = self._now_string()
        for artifact in artifacts:
            conn.execute(
                """
                INSERT INTO run_artifacts
                (run_id, stage_name, artifact_type, path, summary, metadata, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    artifact.stage_name,
                    artifact.artifact_type,
                    artifact.path,
                    artifact.summary,
                    json.dumps(artifact.metadata),
                    artifact.content_hash,
                    created_at,
                ),
            )

    def _get_stage_started_at(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        stage_name: RunStageName,
    ) -> Optional[str]:
        row = conn.execute(
            "SELECT started_at FROM run_stages WHERE run_id = ? AND stage_name = ?",
            (run_id, stage_name),
        ).fetchone()
        return row[0] if row else None

    def _row_to_run(self, row: dict[str, Any]) -> RunRecord:
        return RunRecord(
            id=row["id"],
            problem_id=row.get("problem_id"),
            source_path=row["source_path"],
            source_type=row["source_type"],
            source_fingerprint=row["source_fingerprint"],
            command_name=row["command_name"],
            status=row["status"],
            current_stage=row.get("current_stage"),
            created_at=self._parse_datetime(row.get("created_at")) or utc_now(),
            updated_at=self._parse_datetime(row.get("updated_at")) or utc_now(),
            last_error=self._load_json(row.get("last_error"), row.get("last_error")),
            config=self._load_json(row.get("config"), {}),
        )

    def _row_to_run_stage(
        self,
        row: dict[str, Any],
        artifacts: list[RunArtifactRef],
    ) -> RunStageRecord:
        return RunStageRecord(
            run_id=row["run_id"],
            stage_name=row["stage_name"],
            status=row["status"],
            started_at=self._parse_datetime(row.get("started_at")),
            completed_at=self._parse_datetime(row.get("completed_at")),
            error=self._load_json(row.get("error"), row.get("error")),
            metadata=self._load_json(row.get("metadata"), {}),
            artifacts=artifacts,
        )

    def _row_to_artifact(self, row: dict[str, Any]) -> RunArtifactRef:
        return RunArtifactRef(
            artifact_type=row["artifact_type"],
            path=row["path"],
            stage_name=row["stage_name"],
            summary=row.get("summary") or "",
            metadata=self._load_json(row.get("metadata"), {}),
            content_hash=row.get("content_hash"),
        )

    def _load_json(self, raw_value: Optional[str], default: Any) -> Any:
        """Safely decode stored JSON payloads."""
        if not raw_value:
            return default
        try:
            return json.loads(raw_value)
        except (TypeError, json.JSONDecodeError):
            return default

    def _load_model(self, raw_value: Optional[str], model_type: type[Any], default: Any) -> Any:
        payload = self._load_json(raw_value, None)
        if payload is None:
            return default
        try:
            return model_type.model_validate(payload)
        except Exception:
            return default

    def _load_models(self, raw_value: Optional[str], model_type: type[Any]) -> list[Any]:
        payload = self._load_json(raw_value, [])
        models: list[Any] = []
        for entry in payload:
            try:
                models.append(model_type.model_validate(entry))
            except Exception:
                logger.warning("Skipping malformed %s entry in persisted state", model_type.__name__)
        return models

    def _parse_datetime(self, raw_value: Any) -> Optional[datetime]:
        if not raw_value:
            return None
        try:
            return datetime.fromisoformat(str(raw_value))
        except ValueError:
            return None

    def _serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()

    def _now_string(self) -> str:
        return self._serialize_datetime(utc_now())

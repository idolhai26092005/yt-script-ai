import json
from datetime import datetime, timezone
from typing import Protocol, Any
from app.core.database import SessionLocal
from app.models.project import Project
from app.models.api_key import APIKey
from app.crud.project import update_project_script, update_project_status
from app.crud.api_key import increment_quota

class ScreenplayRepository(Protocol):
    def save_script(
        self,
        project_id: int,
        suggestion_idx: int,
        script_json: str,
        status: str,
        topic_type: str | None = None,
        post_suggestions: Any = None
    ) -> None:
        """Cập nhật kịch bản đầy đủ kèm index gợi ý đã chọn và lưu debug/post-suggestions."""
        ...

    def set_status(self, project_id: int, status: str) -> None:
        """Cập nhật nhanh trạng thái của dự án."""
        ...

    def load_cached_script(self, project_id: int) -> dict | None:
        """Tải dữ liệu kịch bản đã sinh trước đó từ cache nếu có."""
        ...

    def increment_api_key_quota(self, api_key_id: int) -> None:
        """Tăng số lượng API key quota đã sử dụng."""
        ...

    def reset_phase_log(self, project_id: int) -> None:
        """Reset danh sách phase log về mảng rỗng."""
        ...

    def append_phase_log(
        self,
        project_id: int,
        stage_role: str,
        schema_version: str,
        validation_errors: list[str],
        latency_ms: float
    ) -> None:
        """Thêm kết quả chạy của 1 phase vào phase log."""
        ...



class SQLAlchemyScreenplayRepository:
    def __init__(self, db_session = None):
        self.db_session = db_session

    def _get_db(self):
        return self.db_session if self.db_session is not None else SessionLocal()

    def _close_db(self, db):
        if self.db_session is None:
            db.close()

    def save_script(
        self,
        project_id: int,
        suggestion_idx: int,
        script_json: str,
        status: str,
        topic_type: str | None = None,
        post_suggestions: Any = None
    ) -> None:
        db = self._get_db()
        try:
            db_proj = update_project_script(
                db,
                project_id,
                suggestion_idx,
                script_json,
                status,
                topic_type=topic_type
            )
            if db_proj and post_suggestions is not None:
                db_proj.post_suggestions = post_suggestions
                db.commit()
        finally:
            self._close_db(db)

    def set_status(self, project_id: int, status: str) -> None:
        db = self._get_db()
        try:
            update_project_status(db, project_id, status)
        finally:
            self._close_db(db)

    def load_cached_script(self, project_id: int) -> dict | None:
        db = self._get_db()
        try:
            db_project = db.query(Project).filter(Project.id == project_id).first()
            if db_project and db_project.script_output:
                try:
                    return json.loads(db_project.script_output)
                except Exception:
                    pass
            return None
        finally:
            self._close_db(db)

    def increment_api_key_quota(self, api_key_id: int) -> None:
        db = self._get_db()
        try:
            api_key_obj = db.query(APIKey).filter(APIKey.id == api_key_id).first()
            if api_key_obj:
                increment_quota(db, api_key_obj)
        except Exception:
            pass
        finally:
            self._close_db(db)

    def reset_phase_log(self, project_id: int) -> None:
        db = self._get_db()
        try:

            db_project = db.query(Project).filter(Project.id == project_id).first()
            if db_project:
                db_project.phase_log = []
                db.commit()
        finally:
            self._close_db(db)

    def append_phase_log(
        self,
        project_id: int,
        stage_role: str,
        schema_version: str,
        validation_errors: list[str],
        latency_ms: float
    ) -> None:
        db = self._get_db()
        try:
            db_project = db.query(Project).filter(Project.id == project_id).first()
            if db_project:
                log_entry = {
                    "stage_role": stage_role,
                    "schema_version": schema_version,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "validation_errors": validation_errors,
                    "latency_ms": latency_ms
                }
                current_log = db_project.phase_log
                if current_log is None or not isinstance(current_log, list):
                    current_log = []
                new_log = list(current_log)
                new_log.append(log_entry)
                db_project.phase_log = new_log
                db.commit()
        finally:
            self._close_db(db)



class StubScreenplayRepository:
    def __init__(self, projects: dict = None, api_keys: dict = None):
        self.projects = projects if projects is not None else {}
        self.api_keys = api_keys if api_keys is not None else {}

    def save_script(
        self,
        project_id: int,
        suggestion_idx: int,
        script_json: str,
        status: str,
        topic_type: str | None = None,
        post_suggestions: Any = None
    ) -> None:
        if project_id not in self.projects:
            self.projects[project_id] = {}
        proj = self.projects[project_id]
        proj["selected_suggestion_idx"] = suggestion_idx
        proj["script_output"] = script_json
        proj["status"] = status
        if topic_type:
            proj["topic_type"] = topic_type
        if post_suggestions is not None:
            proj["post_suggestions"] = post_suggestions

    def set_status(self, project_id: int, status: str) -> None:
        if project_id not in self.projects:
            self.projects[project_id] = {}
        self.projects[project_id]["status"] = status

    def load_cached_script(self, project_id: int) -> dict | None:
        proj = self.projects.get(project_id)
        if proj and "script_output" in proj:
            try:
                return json.loads(proj["script_output"])
            except Exception:
                pass
        return None

    def increment_api_key_quota(self, api_key_id: int) -> None:
        self.api_keys[api_key_id] = self.api_keys.get(api_key_id, 0) + 1

    def reset_phase_log(self, project_id: int) -> None:
        if project_id not in self.projects:
            self.projects[project_id] = {}
        self.projects[project_id]["phase_log"] = []

    def append_phase_log(
        self,
        project_id: int,
        stage_role: str,
        schema_version: str,
        validation_errors: list[str],
        latency_ms: float
    ) -> None:
        if project_id not in self.projects:
            self.projects[project_id] = {}
        proj = self.projects[project_id]
        if "phase_log" not in proj or not isinstance(proj["phase_log"], list):
            proj["phase_log"] = []
        proj["phase_log"].append({
            "stage_role": stage_role,
            "schema_version": schema_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "validation_errors": validation_errors,
            "latency_ms": latency_ms
        })

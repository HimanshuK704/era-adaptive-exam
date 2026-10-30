"""Local web application for the ERA adaptive examination research prototype."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from era.adaptive.engine import AdaptiveEngine
from era.data.sample_questions import SAMPLE_QUESTIONS
from era.models.entities import Question
from era.trace.events import render_events

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = Path(os.getenv("ERA_DB_PATH", str(Path.cwd() / "era.sqlite3")))
app = FastAPI(title="ERA Adaptive Examination System", version="0.1.0")

_allowed_origins = [
    origin.strip()
    for origin in os.getenv("ERA_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
_lock = RLock()
_sessions: dict[str, AdaptiveEngine] = {}
_auth_tokens: dict[str, tuple[str, float]] = {}
_AUTH_TTL_SECONDS = 3600


def _load_questions() -> list[Question]:
    """Load supported single-answer MCQs from data/jeebench_mcq.json if present."""
    path = Path(os.getenv("ERA_QUESTION_BANK", str(Path.cwd() / "data" / "jeebench_mcq.json")))
    if not path.exists():
        return list(SAMPLE_QUESTIONS)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw.get("questions", raw) if isinstance(raw, dict) else raw
        questions = []
        for item in items:
            options = tuple(str(x) for x in item["options"])
            questions.append(Question(
                question_id=str(item["question_id"]), subject=str(item["subject"]),
                topic=str(item.get("topic", "General")), text=str(item["text"]),
                options=options, correct_index=int(item["correct_index"]),
                difficulty=float(item.get("difficulty", 0.0)), synthetic=bool(item.get("synthetic", False)),
            ))
        if not questions:
            raise ValueError("question bank is empty")
        return questions
    except Exception as exc:
        raise RuntimeError(f"Could not load question bank {path}: {exc}") from exc


_questions = _load_questions()


def _db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, completed_at TEXT,
        response_count INTEGER NOT NULL DEFAULT 0, complete INTEGER NOT NULL DEFAULT 0,
        theta REAL NOT NULL DEFAULT 0, posterior_sd REAL NOT NULL DEFAULT 1,
        student_id TEXT
    )""")
    session_columns = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)")}
    if "student_id" not in session_columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN student_id TEXT")
    conn.execute("""CREATE TABLE IF NOT EXISTS students (
        student_id TEXT PRIMARY KEY, salt TEXT NOT NULL, password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
        question_id TEXT NOT NULL, selected_index INTEGER NOT NULL, correct INTEGER NOT NULL,
        created_at TEXT NOT NULL, UNIQUE(session_id, question_id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS decision_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
        event_type TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL
    )""")
    conn.commit()
    return conn




@app.on_event("startup")
def initialize_demo_student() -> None:
    """Create or reset the configured demo student once per application startup."""
    demo_id = os.getenv("ERA_DEMO_STUDENT_ID", "").strip()
    demo_password = os.getenv("ERA_DEMO_STUDENT_PASSWORD", "")
    print(
        "[ERA AUTH DIAGNOSTIC] startup initializer reached; "
        f"student_id_configured={bool(demo_id)}; "
        f"password_configured={bool(demo_password)}; "
        f"database_path={DB_PATH}"
    )
    if not demo_id or not demo_password:
        print("[ERA AUTH DIAGNOSTIC] initialization skipped: missing configuration")
        return

    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", demo_password.encode("utf-8"), salt, 310_000
    ).hex()

    with closing(_db()) as conn:
        existing = conn.execute(
            "SELECT 1 FROM students WHERE student_id = ?", (demo_id,)
        ).fetchone()

        if existing is None:
            conn.execute(
                """INSERT INTO students(student_id, salt, password_hash, created_at)
                   VALUES (?, ?, ?, ?)""",
                (demo_id, salt.hex(), password_hash,
                 datetime.now(timezone.utc).isoformat()),
            )
        else:
            conn.execute(
                "UPDATE students SET salt = ?, password_hash = ? WHERE student_id = ?",
                (salt.hex(), password_hash, demo_id),
            )
        conn.commit()

def _persist_new_session(session_id: str, student_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with closing(_db()) as conn:
        conn.execute(
            "INSERT INTO sessions(session_id, started_at, student_id) VALUES (?, ?, ?)",
            (session_id, now, student_id),
        )
        conn.commit()


def _require_student(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please log in to continue.")
    token = authorization[7:].strip()
    record = _auth_tokens.get(token)
    if not record:
        raise HTTPException(401, "Login expired or invalid. Please sign in again.")
    student_id, expires_at = record
    if time.time() >= expires_at:
        _auth_tokens.pop(token, None)
        raise HTTPException(401, "Login expired. Please sign in again.")
    return student_id


def _assert_session_owner(session_id: str, student_id: str) -> None:
    with closing(_db()) as conn:
        row = conn.execute("SELECT student_id FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Session not found.")
    if row["student_id"] != student_id:
        raise HTTPException(403, "This exam session does not belong to the logged-in student.")


def _persist_events(session_id: str, engine: AdaptiveEngine, start: int = 0) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with closing(_db()) as conn:
        conn.executemany(
            "INSERT INTO decision_events(session_id, event_type, details_json, created_at) VALUES (?, ?, ?, ?)",
            [(session_id, e.event_type, json.dumps(e.details, sort_keys=True), now) for e in engine.events[start:]],
        )
        conn.commit()


class LoginRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class StartExamRequest(BaseModel):
    subject: str = Field(default="All", max_length=30)


class AnswerRequest(BaseModel):
    question_id: str
    selected_index: int = Field(ge=0, le=20)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "era-adaptive-exam"}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict:
    student_id = payload.student_id.strip()
    with closing(_db()) as conn:
        row = conn.execute(
            "SELECT student_id, salt, password_hash FROM students WHERE student_id = ?", (student_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(401, "Invalid student ID or password.")
    candidate = hashlib.pbkdf2_hmac(
        "sha256", payload.password.encode("utf-8"), bytes.fromhex(row["salt"]), 310_000
    ).hex()
    if not hmac.compare_digest(candidate, row["password_hash"]):
        raise HTTPException(401, "Invalid student ID or password.")
    token = secrets.token_urlsafe(32)
    _auth_tokens[token] = (row["student_id"], time.time() + _AUTH_TTL_SECONDS)
    return {"access_token": token, "token_type": "bearer", "expires_in": _AUTH_TTL_SECONDS,
            "student_id": row["student_id"]}


@app.get("/api/meta")
def metadata() -> dict:
    subjects = sorted({q.subject for q in _questions})
    return {"subjects": subjects, "question_count": len(_questions),
            "question_bank": "synthetic" if all(q.synthetic for q in _questions) else "imported/mixed"}


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/trace")
def trace_page():
    return FileResponse(STATIC_DIR / "trace.html")


@app.post("/api/sessions")
def start_session(payload: StartExamRequest, student_id: str = Depends(_require_student)) -> dict:
    eligible = [q for q in _questions if payload.subject == "All" or q.subject.lower() == payload.subject.lower()]
    if not eligible:
        raise HTTPException(400, "No questions available for that subject.")
    if len(eligible) < 6:
        raise HTTPException(400, "At least six eligible questions are required for a demo session.")
    session_id = str(uuid.uuid4())
    total_limit = min(45, len(eligible))
    diagnostic_items = min(15, total_limit - 1)
    engine = AdaptiveEngine(
        eligible,
        max_exam_items=total_limit,
        diagnostic_items=diagnostic_items,
    )
    with _lock:
        _sessions[session_id] = engine
    try:
        _persist_new_session(session_id, student_id)
    except Exception as exc:
        with _lock:
            _sessions.pop(session_id, None)
        raise HTTPException(500, f"Could not create session storage: {exc}") from exc
    return {
        "session_id": session_id,
        "total_limit": engine.max_exam_items,
        "diagnostic_items": engine.diagnostic_items,
        "main_exam_items": engine.max_exam_items - engine.diagnostic_items,
        "available_questions": len(eligible),
    }


def _get_engine(session_id: str) -> AdaptiveEngine:
    engine = _sessions.get(session_id)
    if engine is None:
        raise HTTPException(404, "Session not found or server restarted. Start a new demo session.")
    return engine


def _public_question(question: Question, number: int, total_limit: int) -> dict:
    return {
        "question_id": question.question_id, "subject": question.subject, "topic": question.topic,
        "text": question.text, "options": list(question.options), "number": number,
        "total_limit": total_limit,
    }


@app.get("/api/sessions/{session_id}/question")
def get_next_question(session_id: str, student_id: str = Depends(_require_student)) -> dict:
    _assert_session_owner(session_id, student_id)
    with _lock:
        engine = _get_engine(session_id)
        start = len(engine.events)
        selection = engine.next_question()
        _persist_events(session_id, engine, start)
        if selection is None:
            with closing(_db()) as conn:
                conn.execute("UPDATE sessions SET complete=1, completed_at=?, response_count=? WHERE session_id=?",
                             (datetime.now(timezone.utc).isoformat(), engine.ability.responses, session_id))
                conn.commit()
            return {"complete": True, "message": "Thank You"}
        total_answered = engine.ability.responses
        diagnostic_items = engine.diagnostic_items or 0
        stage_number = (
            total_answered + 1
            if engine.stage == "diagnostic"
            else total_answered - diagnostic_items + 1
        )
        stage_limit = (
            diagnostic_items
            if engine.stage == "diagnostic"
            else engine.max_exam_items - diagnostic_items
        )
        return {
            "complete": False,
            "question": _public_question(
                selection.question,
                len(engine.attempted_ids) + 1,
                engine.max_exam_items,
            ),
            "phase": engine.phase,
            "stage": engine.stage,
            "stage_number": stage_number,
            "stage_limit": stage_limit,
            "diagnostic_items": diagnostic_items,
            "remaining": engine.max_exam_items - len(engine.attempted_ids),
        }


@app.post("/api/sessions/{session_id}/answer")
def submit_answer(session_id: str, payload: AnswerRequest, student_id: str = Depends(_require_student)) -> dict:
    _assert_session_owner(session_id, student_id)
    with _lock:
        engine = _get_engine(session_id)
        if not engine._pending_selection:
            raise HTTPException(409, "No question is currently awaiting an answer.")
        question = engine._pending_selection.question
        if question.question_id != payload.question_id:
            raise HTTPException(409, "This answer does not match the current question.")
        start = len(engine.events)
        try:
            engine.submit_response(question, payload.selected_index)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        _persist_events(session_id, engine, start)
        now = datetime.now(timezone.utc).isoformat()
        with closing(_db()) as conn:
            conn.execute("INSERT INTO responses(session_id, question_id, selected_index, correct, created_at) VALUES (?, ?, ?, ?, ?)",
                         (session_id, question.question_id, payload.selected_index,
                          int(payload.selected_index == question.correct_index), now))
            conn.execute("UPDATE sessions SET response_count=?, theta=?, posterior_sd=? WHERE session_id=?",
                         (engine.ability.responses, engine.ability.theta, engine.ability.posterior_sd, session_id))
            conn.commit()
        # Deliberately do not return correctness or ability to the student UI.
        return {"saved": True, "answered": engine.ability.responses, "remaining": engine.max_exam_items - engine.ability.responses}


@app.post("/api/sessions/{session_id}/submit")
def submit_exam(session_id: str, student_id: str = Depends(_require_student)) -> dict:
    _assert_session_owner(session_id, student_id)
    with _lock:
        engine = _get_engine(session_id)
        now = datetime.now(timezone.utc).isoformat()
        with closing(_db()) as conn:
            conn.execute("UPDATE sessions SET complete=1, completed_at=?, response_count=? WHERE session_id=?",
                         (now, engine.ability.responses, session_id))
            conn.commit()
        return {"complete": True, "message": "Thank You"}


@app.get("/api/admin/sessions/{session_id}/trace")
def get_trace(session_id: str) -> dict:
    # Demo-only developer endpoint. Add authentication before any public/real use.
    with _lock:
        engine = _get_engine(session_id)
        return {"session_id": session_id, "events": json.loads("[" + ",".join(render_events(engine.events).splitlines()) + "]"),
                "ability": {"theta": round(engine.ability.theta, 4), "posterior_sd": round(engine.ability.posterior_sd, 4),
                            "responses": engine.ability.responses}, "phase": engine.phase}


@app.get("/api/admin/summary")
def admin_summary() -> dict:
    # Demo-only aggregate endpoint. No student names or personal details are collected.
    with closing(_db()) as conn:
        row = conn.execute("SELECT COUNT(*) AS sessions, COALESCE(SUM(response_count), 0) AS responses FROM sessions").fetchone()
    return {"sessions": row["sessions"], "responses": row["responses"], "question_count": len(_questions),
            "question_bank": "synthetic" if all(q.synthetic for q in _questions) else "imported/mixed"}

@app.get("/api/research/ednet")
def ednet_research_summary() -> dict:
    """Read-only exploratory EdNet analysis for the ERA research demo."""
    report_path = Path.cwd() / "reports" / "ednet_research_summary.json"
    if not report_path.is_file():
        raise HTTPException(404, "EdNet research report is not available.")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(500, "Could not read EdNet research report.") from exc
    return report

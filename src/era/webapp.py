"""Local web application for the ERA adaptive examination research prototype."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from fastapi import FastAPI, HTTPException
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
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
_lock = RLock()
_sessions: dict[str, AdaptiveEngine] = {}


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
        theta REAL NOT NULL DEFAULT 0, posterior_sd REAL NOT NULL DEFAULT 1
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


def _persist_new_session(session_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with closing(_db()) as conn:
        conn.execute("INSERT INTO sessions(session_id, started_at) VALUES (?, ?)", (session_id, now))
        conn.commit()


def _persist_events(session_id: str, engine: AdaptiveEngine, start: int = 0) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with closing(_db()) as conn:
        conn.executemany(
            "INSERT INTO decision_events(session_id, event_type, details_json, created_at) VALUES (?, ?, ?, ?)",
            [(session_id, e.event_type, json.dumps(e.details, sort_keys=True), now) for e in engine.events[start:]],
        )
        conn.commit()


class StartExamRequest(BaseModel):
    subject: str = Field(default="All", max_length=30)


class AnswerRequest(BaseModel):
    question_id: str
    selected_index: int = Field(ge=0, le=20)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "era-adaptive-exam"}


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
def start_session(payload: StartExamRequest) -> dict:
    eligible = [q for q in _questions if payload.subject == "All" or q.subject.lower() == payload.subject.lower()]
    if not eligible:
        raise HTTPException(400, "No questions available for that subject.")
    if len(eligible) < 6:
        raise HTTPException(400, "At least six eligible questions are required for a demo session.")
    session_id = str(uuid.uuid4())
    engine = AdaptiveEngine(eligible)
    with _lock:
        _sessions[session_id] = engine
    try:
        _persist_new_session(session_id)
    except Exception as exc:
        with _lock:
            _sessions.pop(session_id, None)
        raise HTTPException(500, f"Could not create session storage: {exc}") from exc
    return {"session_id": session_id, "total_limit": engine.max_exam_items, "available_questions": len(eligible)}


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
def get_next_question(session_id: str) -> dict:
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
        return {"complete": False, "question": _public_question(selection.question, len(engine.attempted_ids) + 1, engine.max_exam_items),
                "phase": engine.phase, "remaining": engine.max_exam_items - len(engine.attempted_ids)}


@app.post("/api/sessions/{session_id}/answer")
def submit_answer(session_id: str, payload: AnswerRequest) -> dict:
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
def submit_exam(session_id: str) -> dict:
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

# -*- coding: utf-8 -*-
"""
MAXX AI DOJO — แอปคอร์สสอนทำงานร่วมกับ AI โดยมี Claude เป็นครูตรวจให้คะแนน
Flask + Postgres (Railway) + Anthropic API

ENV ที่ต้องตั้งบน Railway:
  ANTHROPIC_API_KEY   คีย์ Anthropic
  APP_PASSWORD        รหัสผ่านเข้าแอป (คนเดียว)
  SECRET_KEY          สตริงสุ่มยาวๆ สำหรับ session
  DATABASE_URL        Railway ใส่ให้อัตโนมัติเมื่อเพิ่ม Postgres
  CLAUDE_MODEL        (ไม่บังคับ) ค่าเริ่มต้น claude-sonnet-4-6
  FREE_MODE           (ไม่บังคับ) ตั้งเป็น 1 เพื่อปลดล็อกทุกบท
"""
import os
import json
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, abort, flash)

from courses import COURSES, ORDER, get_course, lesson_by_id, get_exercise
import grader

app = Flask(__name__)
app.template_filter("fromjson")(lambda s: json.loads(s) if s else [])
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-railway")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "dojo")
FREE_MODE = os.environ.get("FREE_MODE", "0") == "1"
PASS_SCORE = 7
MAX_ATTEMPTS = 3

# ------------------------------------------------------------------ DB
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    import psycopg2
    import psycopg2.extras

    def _connect():
        url = DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    PH = "%s"
    SERIAL = "SERIAL PRIMARY KEY"
else:
    import sqlite3

    def _connect():
        c = sqlite3.connect(os.environ.get("SQLITE_PATH", "dojo.db"))
        c.row_factory = sqlite3.Row
        return c
    PH = "?"
    SERIAL = "INTEGER PRIMARY KEY AUTOINCREMENT"


def q(sql, params=(), fetch=None):
    """รัน SQL แบบเดียวใช้ได้ทั้ง Postgres และ SQLite (เขียน placeholder เป็น ?)"""
    sql = sql.replace("?", PH)
    con = _connect()
    try:
        cur = con.cursor()
        cur.execute(sql, params)
        out = None
        if fetch == "one":
            r = cur.fetchone()
            out = dict(r) if r else None
        elif fetch == "all":
            out = [dict(r) for r in cur.fetchall()]
        elif fetch == "id":
            if DATABASE_URL:
                out = cur.fetchone()["id"]
            else:
                out = cur.lastrowid
        con.commit()
        return out
    finally:
        con.close()


def init_db():
    q(f"""CREATE TABLE IF NOT EXISTS submissions (
        id {SERIAL},
        course TEXT NOT NULL DEFAULT 'ai',
        lesson_id INTEGER NOT NULL,
        exercise_id TEXT NOT NULL,
        attempt INTEGER NOT NULL,
        kind TEXT NOT NULL,
        answer TEXT,
        transcript TEXT,
        score INTEGER NOT NULL,
        feedback TEXT NOT NULL,
        followup_q TEXT,
        followup_a TEXT,
        bonus INTEGER,
        followup_comment TEXT,
        created_at TEXT NOT NULL
    )""")
    q(f"""CREATE TABLE IF NOT EXISTS sandbox (
        id {SERIAL},
        course TEXT NOT NULL DEFAULT 'ai',
        lesson_id INTEGER NOT NULL,
        exercise_id TEXT NOT NULL,
        messages TEXT NOT NULL,
        submitted INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )""")
    q(f"""CREATE TABLE IF NOT EXISTS notes (
        id {SERIAL},
        course TEXT NOT NULL DEFAULT 'ai',
        summary TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")


    # migration สำหรับฐานข้อมูลเวอร์ชันแรกที่ยังไม่มีคอลัมน์ course
    for t in ("submissions", "sandbox", "notes"):
        try:
            q(f"ALTER TABLE {t} ADD COLUMN course TEXT NOT NULL DEFAULT 'ai'")
        except Exception:
            pass


init_db()


def now():
    return datetime.utcnow().isoformat(timespec="seconds")


def insert_returning(table, cols, vals):
    marks = ",".join(["?"] * len(vals))
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({marks})"
    if DATABASE_URL:
        sql += " RETURNING id"
    return q(sql, tuple(vals), fetch="id")


# ------------------------------------------------------------------ auth
def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not session.get("ok"):
            return redirect(url_for("login", next=request.path))
        return f(*a, **k)
    return w


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            session["ok"] = True
            session.permanent = True
            return redirect(request.args.get("next") or url_for("home"))
        flash("รหัสผ่านไม่ถูกต้อง")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------------------------------------------------------ progress
def submissions_for(course, lesson_id, ex_id):
    return q("SELECT * FROM submissions WHERE course=? AND lesson_id=? AND exercise_id=? ORDER BY attempt",
             (course, lesson_id, ex_id), fetch="all")


def exercise_status(course, lesson_id, ex_id):
    subs = submissions_for(course, lesson_id, ex_id)
    if not subs:
        return {"state": "new", "best": None, "attempts": 0, "latest": None}
    best = max(subs, key=lambda s: (s["score"] + (s["bonus"] or 0)))
    latest = subs[-1]
    passed = best["score"] >= PASS_SCORE and best["followup_a"] is not None
    if passed:
        state = "passed"
    elif len(subs) >= MAX_ATTEMPTS and latest["followup_a"] is not None:
        state = "done"      # ใช้ครบ 3 ครั้ง ยังไม่ถึง 7 แต่ไปต่อได้
    else:
        state = "progress"
    return {"state": state, "best": best, "attempts": len(subs), "latest": latest}


def lesson_status(course, lesson):
    exs = {e["id"]: exercise_status(course, lesson["id"], e["id"]) for e in lesson["exercises"]}
    complete = all(s["state"] in ("passed", "done") for s in exs.values())
    scores = [s["best"]["score"] + (s["best"]["bonus"] or 0) for s in exs.values() if s["best"]]
    avg = round(sum(scores) / len(scores), 1) if scores else None
    started = any(s["state"] != "new" for s in exs.values())
    return {"exercises": exs, "complete": complete, "avg": avg, "started": started}


def lesson_unlocked(lesson_id, statuses):
    if FREE_MODE or lesson_id == 1:
        return True
    return statuses[lesson_id - 1]["complete"]


def all_statuses(course):
    return {l["id"]: lesson_status(course, l) for l in COURSES[course]["lessons"]}


def course_or_404(slug):
    return get_course(slug) or abort(404)


# ------------------------------------------------------------------ pages
@app.route("/")
@login_required
def home():
    cards = []
    for slug in ORDER:
        c = COURSES[slug]
        st = all_statuses(slug)
        cards.append({"c": c, "done": sum(1 for s in st.values() if s["complete"]),
                      "total": len(c["lessons"]), "started": any(s["started"] for s in st.values())})
    return render_template("home.html", cards=cards)


@app.route("/<course>/")
@login_required
def index(course):
    c = course_or_404(course)
    statuses = all_statuses(course)
    unlocked = {l["id"]: lesson_unlocked(l["id"], statuses) for l in c["lessons"]}
    done = sum(1 for s in statuses.values() if s["complete"])
    return render_template("index.html", c=c, lessons=c["lessons"], statuses=statuses,
                           unlocked=unlocked, done=done)


@app.route("/<course>/lesson/<int:lid>")
@login_required
def lesson(course, lid):
    c = course_or_404(course)
    l = lesson_by_id(course, lid) or abort(404)
    statuses = all_statuses(course)
    if not lesson_unlocked(lid, statuses):
        flash("บทนี้ยังล็อกอยู่ ทำบทก่อนหน้าให้ผ่านก่อน")
        return redirect(url_for("index", course=course))
    return render_template("lesson.html", c=c, l=l, st=statuses[lid],
                           next_id=lid + 1 if lid < len(c["lessons"]) else None)


@app.route("/<course>/exercise/<int:lid>/<ex_id>")
@login_required
def exercise(course, lid, ex_id):
    c = course_or_404(course)
    l, e = get_exercise(course, lid, ex_id)
    if not e:
        abort(404)
    statuses = all_statuses(course)
    if not lesson_unlocked(lid, statuses):
        return redirect(url_for("index", course=course))
    st = exercise_status(course, lid, ex_id)
    subs = submissions_for(course, lid, ex_id)
    for s in subs:
        s["fb"] = json.loads(s["feedback"])
    sb = None
    if e["type"] == "sandbox":
        sb = q("SELECT * FROM sandbox WHERE course=? AND lesson_id=? AND exercise_id=? AND submitted=0 ORDER BY id DESC LIMIT 1",
               (course, lid, ex_id), fetch="one")
        if sb:
            sb["msgs"] = json.loads(sb["messages"])
    can_submit = st["state"] not in ("passed",) and st["attempts"] < MAX_ATTEMPTS
    pending_followup = st["latest"] if st["latest"] and st["latest"]["followup_a"] is None else None
    if pending_followup:
        pending_followup = dict(pending_followup)
        pending_followup["fb"] = json.loads(pending_followup["feedback"])
    return render_template("exercise.html", c=c, l=l, e=e, st=st, subs=subs, sb=sb,
                           can_submit=can_submit and not pending_followup,
                           pending=pending_followup, PASS=PASS_SCORE, MAXA=MAX_ATTEMPTS)


def _save_submission(course, l, e, kind, answer, transcript):
    subs = submissions_for(course, l["id"], e["id"])
    if len(subs) >= MAX_ATTEMPTS:
        return None, "ส่งครบ 3 ครั้งแล้ว"
    attempt = len(subs) + 1
    prev = json.loads(subs[-1]["feedback"]) if subs else None
    prev_text = None
    if prev:
        prev_text = f"คะแนน {subs[-1]['score']}: {prev.get('verdict','')} / จุดอ่อน: {'; '.join(prev.get('weaknesses', []))} / แก้: {prev.get('fix','')}"
    try:
        fb = grader.grade(l, e, answer=answer, transcript=transcript, attempt=attempt,
                          previous_feedback=prev_text, course_context=COURSES[course]["teacher_context"])
    except Exception as ex:  # noqa
        return None, f"ครูตรวจไม่สำเร็จ: {ex}"
    sid = insert_returning(
        "submissions",
        ["course", "lesson_id", "exercise_id", "attempt", "kind", "answer", "transcript", "score",
         "feedback", "followup_q", "created_at"],
        [course, l["id"], e["id"], attempt, kind, answer, json.dumps(transcript, ensure_ascii=False) if transcript else None,
         fb["score"], json.dumps(fb, ensure_ascii=False), fb.get("followup"), now()],
    )
    return sid, None


@app.route("/<course>/exercise/<int:lid>/<ex_id>/submit", methods=["POST"])
@login_required
def submit_text(course, lid, ex_id):
    course_or_404(course)
    l, e = get_exercise(course, lid, ex_id)
    if not e or e["type"] != "text":
        abort(404)
    answer = (request.form.get("answer") or "").strip()
    if len(answer) < 20:
        flash("งานสั้นเกินไป ครูยังไม่ตรวจ")
        return redirect(url_for("exercise", course=course, lid=lid, ex_id=ex_id))
    sid, err = _save_submission(course, l, e, "text", answer, None)
    if err:
        flash(err)
    return redirect(url_for("exercise", course=course, lid=lid, ex_id=ex_id))


@app.route("/submission/<int:sid>/followup", methods=["POST"])
@login_required
def followup(sid):
    s = q("SELECT * FROM submissions WHERE id=?", (sid,), fetch="one") or abort(404)
    back = url_for("exercise", course=s["course"], lid=s["lesson_id"], ex_id=s["exercise_id"])
    if s["followup_a"] is not None:
        return redirect(back)
    ans = (request.form.get("followup_a") or "").strip()
    if len(ans) < 10:
        flash("ตอบสั้นเกินไป")
        return redirect(back)
    l, e = get_exercise(s["course"], s["lesson_id"], s["exercise_id"])
    summary = s["answer"] or grader._transcript_text(json.loads(s["transcript"] or "[]"))
    try:
        r = grader.grade_followup(l, e, s["followup_q"], ans, summary,
                                  course_context=COURSES[s["course"]]["teacher_context"])
    except Exception as ex:  # noqa
        flash(f"ครูตรวจไม่สำเร็จ: {ex}")
        return redirect(back)
    q("UPDATE submissions SET followup_a=?, bonus=?, followup_comment=? WHERE id=?",
      (ans, r["bonus"], r.get("comment", ""), sid))
    return redirect(back)


# ------------------------------------------------------------------ sandbox
@app.route("/<course>/exercise/<int:lid>/<ex_id>/sandbox/message", methods=["POST"])
@login_required
def sandbox_message(course, lid, ex_id):
    course_or_404(course)
    l, e = get_exercise(course, lid, ex_id)
    if not e or e["type"] != "sandbox":
        abort(404)
    text = (request.json or {}).get("text", "").strip()
    if not text:
        return jsonify({"error": "ว่าง"}), 400
    sb = q("SELECT * FROM sandbox WHERE course=? AND lesson_id=? AND exercise_id=? AND submitted=0 ORDER BY id DESC LIMIT 1",
           (course, lid, ex_id), fetch="one")
    msgs = json.loads(sb["messages"]) if sb else []
    if len(msgs) >= 24:
        return jsonify({"error": "บทสนทนายาวเกิน 12 รอบแล้ว ส่งให้ครูตรวจหรือเริ่มใหม่"}), 400
    msgs.append({"role": "user", "content": text})
    try:
        reply = grader.sandbox_reply(e, msgs)
    except Exception as ex:  # noqa
        return jsonify({"error": f"AI ผู้ช่วยตอบไม่ได้: {ex}"}), 500
    msgs.append({"role": "assistant", "content": reply})
    if sb:
        q("UPDATE sandbox SET messages=? WHERE id=?", (json.dumps(msgs, ensure_ascii=False), sb["id"]))
    else:
        insert_returning("sandbox", ["course", "lesson_id", "exercise_id", "messages", "submitted", "created_at"],
                         [course, lid, ex_id, json.dumps(msgs, ensure_ascii=False), 0, now()])
    return jsonify({"reply": reply, "turns": len(msgs) // 2})


@app.route("/<course>/exercise/<int:lid>/<ex_id>/sandbox/reset", methods=["POST"])
@login_required
def sandbox_reset(course, lid, ex_id):
    q("DELETE FROM sandbox WHERE course=? AND lesson_id=? AND exercise_id=? AND submitted=0", (course, lid, ex_id))
    return redirect(url_for("exercise", course=course, lid=lid, ex_id=ex_id))


@app.route("/<course>/exercise/<int:lid>/<ex_id>/sandbox/submit", methods=["POST"])
@login_required
def sandbox_submit(course, lid, ex_id):
    course_or_404(course)
    l, e = get_exercise(course, lid, ex_id)
    if not e or e["type"] != "sandbox":
        abort(404)
    back = url_for("exercise", course=course, lid=lid, ex_id=ex_id)
    sb = q("SELECT * FROM sandbox WHERE course=? AND lesson_id=? AND exercise_id=? AND submitted=0 ORDER BY id DESC LIMIT 1",
           (course, lid, ex_id), fetch="one")
    if not sb:
        flash("ยังไม่มีบทสนทนาให้ตรวจ")
        return redirect(back)
    msgs = json.loads(sb["messages"])
    if len(msgs) < 2:
        flash("คุยกับ AI ผู้ช่วยก่อนอย่างน้อย 1 รอบ")
        return redirect(back)
    sid, err = _save_submission(course, l, e, "sandbox", None, msgs)
    if err:
        flash(err)
    else:
        q("UPDATE sandbox SET submitted=1 WHERE id=?", (sb["id"],))
    return redirect(back)


# ------------------------------------------------------------------ notebook
@app.route("/<course>/notebook")
@login_required
def notebook(course):
    c = course_or_404(course)
    rows = q("SELECT * FROM submissions WHERE course=? ORDER BY created_at", (course,), fetch="all")
    for r in rows:
        r["fb"] = json.loads(r["feedback"])
    statuses = all_statuses(course)
    per_lesson = [{"id": l["id"], "title": l["title"], "avg": statuses[l["id"]]["avg"],
                   "complete": statuses[l["id"]]["complete"]} for l in c["lessons"]]
    note = q("SELECT * FROM notes WHERE course=? ORDER BY id DESC LIMIT 1", (course,), fetch="one")
    return render_template("notebook.html", c=c, rows=rows, per_lesson=per_lesson, note=note,
                           chart=json.dumps([r["score"] + (r["bonus"] or 0) for r in rows]),
                           chart_labels=json.dumps([f"{r['lesson_id']}{r['exercise_id'][-1]}" for r in rows]))


@app.route("/<course>/notebook/summary", methods=["POST"])
@login_required
def notebook_summary(course):
    c = course_or_404(course)
    rows = q("SELECT lesson_id, exercise_id, attempt, score, bonus, feedback FROM submissions WHERE course=? ORDER BY created_at",
             (course,), fetch="all")
    for r in rows:
        r["verdict"] = json.loads(r["feedback"]).get("verdict", "")
    if not rows:
        flash("ยังไม่มีคะแนนให้สรุป")
        return redirect(url_for("notebook", course=course))
    try:
        s = grader.progress_summary(rows, c["title"], {l["id"]: l["title"] for l in c["lessons"]})
        insert_returning("notes", ["course", "summary", "created_at"], [course, s, now()])
    except Exception as ex:  # noqa
        flash(f"สรุปไม่สำเร็จ: {ex}")
    return redirect(url_for("notebook", course=course))


@app.route("/health")
def health():
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=False)

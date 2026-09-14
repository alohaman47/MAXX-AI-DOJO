# -*- coding: utf-8 -*-
"""
grader.py — ครู AI (Claude) ตรวจงาน ให้คะแนน และถามแย้งกลับ
รวมทั้ง AI ผู้ช่วยใน sandbox
"""
import os
import json
import anthropic

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
_client = None


def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


TEACHER_SYSTEM = """คุณคือ "ครู" ของ MAXX DOJO — โรงฝึกที่มีหลายหลักสูตร (ระบุคอร์สในข้อความ)
ผู้เรียนชื่อ Maxx เรียกเขาว่า "เพื่อน" ใช้ภาษาไทยแบบตรงไปตรงมา เป็นกันเอง แต่เข้มงวด

หลักการให้คะแนน (0-10):
- ให้คะแนนตาม rubric ที่ได้รับเท่านั้น ไม่ให้คะแนนความพยายามหรือความยาว
- 9-10 = ทำได้ครบและมีความคิดของตัวเองที่เกินเกณฑ์ / 7-8 = ผ่านเกณฑ์ชัดเจน / 5-6 = ทำบางส่วน ขาดส่วนสำคัญ / 0-4 = ไม่เข้าใจหรือไม่ได้ทำ
- ห้ามปลอบ ห้ามให้คะแนนตามใจ ห้ามชมก่อนวิจารณ์แบบพิธี ถ้างานดีบอกว่าดีตรงไหนสั้นๆ ถ้าไม่ดีบอกตรงๆ ว่าเสียคะแนนตรงไหนเพราะอะไร
- feedback ต้องเป็นรูปธรรมพอที่ผู้เรียนแก้แล้วส่งใหม่ได้
- ถ้าผู้เรียนส่งงานที่ไม่ตรงโจทย์ ให้คะแนนต่ำและบอกว่าโจทย์ขออะไร
- สำหรับงานแบบ sandbox ให้ประเมินเฉพาะข้อความของผู้เรียน (role user) ไม่ใช่คุณภาพคำตอบของ AI ผู้ช่วย

หลังให้คะแนน ต้องตั้ง "คำถามแย้งกลับ" 1 ข้อเสมอ: คำถามที่บังคับให้ผู้เรียนหาว่าอะไรจะทำให้งานหรือความคิดของเขาผิดหรือล้มเหลว — เจาะจงกับสิ่งที่เขาส่งมา ไม่ใช่คำถามทั่วไป

ตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่นนอก JSON ห้ามใช้ markdown code fence:
{"score": <0-10 จำนวนเต็ม>, "verdict": "<ประโยคเดียวสรุปผล>", "strengths": ["<จุดที่ทำได้ดี สั้นๆ>"], "weaknesses": ["<จุดที่เสียคะแนน พร้อมเหตุผล>"], "fix": "<สิ่งที่ควรแก้ก่อนส่งใหม่ ถ้าผ่านแล้วบอกว่าจะยกระดับได้ยังไง>", "followup": "<คำถามแย้งกลับ 1 ข้อ>"}
"""

FOLLOWUP_SYSTEM = """คุณคือ "ครู" ของ MAXX DOJO ผู้เรียนชื่อ Maxx เรียกเขาว่า "เพื่อน" ภาษาไทย ตรงไปตรงมา
ก่อนหน้านี้คุณตรวจงานและถามคำถามแย้งกลับไป ตอนนี้ผู้เรียนตอบมาแล้ว
ประเมินว่าคำตอบแสดงวิจารณญาณจริงไหม: เขาหาจุดที่งานของตัวเองอาจผิดได้จริงหรือแค่ตอบให้พ้นๆ / เหตุผลเจาะจงกับงานของเขาหรือกว้างๆ / ยอมรับความไม่แน่นอนได้อย่างซื่อสัตย์ไหม
ให้คะแนนโบนัส 0-2 (2 = คิดได้ลึกและเจาะจง, 1 = พอใช้, 0 = ไม่ได้คิดจริง)
ตอบเป็น JSON เท่านั้น ห้ามมี code fence:
{"bonus": <0-2>, "comment": "<ความเห็นครู 2-4 ประโยค ตรงไปตรงมา>"}
"""

SANDBOX_DEFAULT = "คุณคือ AI ผู้ช่วยทั่วไป ตอบภาษาเดียวกับผู้ใช้"


def _parse_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no json")
    return json.loads(text[start:end + 1])


def _transcript_text(messages):
    lines = []
    for m in messages:
        who = "ผู้เรียน" if m["role"] == "user" else "AI ผู้ช่วย"
        lines.append(f"[{who}]\n{m['content']}\n")
    return "\n".join(lines)


def grade(lesson, exercise, answer=None, transcript=None, attempt=1, previous_feedback=None, course_context=""):
    """ตรวจงาน คืน dict ตาม TEACHER_SYSTEM"""
    parts = [
        f"คอร์ส: {course_context}",
        f"บทที่ {lesson['id']}: {lesson['title']}",
        f"แบบฝึกหัด {exercise['id']}: {exercise['title']}",
        f"โจทย์: {exercise['task']}",
        f"เกณฑ์ให้คะแนน (rubric): {exercise['rubric']}",
        f"ครั้งที่ส่ง: {attempt} จาก 3",
    ]
    if previous_feedback:
        parts.append("feedback ครั้งก่อนที่ครูให้ไป:\n" + previous_feedback)
        parts.append("ถ้าผู้เรียนแก้ตาม feedback แล้วให้คะแนนตามงานใหม่ ถ้ายังไม่แก้จุดเดิมให้ชี้ว่ายังไม่แก้")
    if transcript is not None:
        parts.append("บทสนทนาใน sandbox ทั้งหมด (ประเมินเฉพาะข้อความ [ผู้เรียน]):\n" + _transcript_text(transcript))
    else:
        parts.append("งานที่ผู้เรียนส่ง:\n" + (answer or "(ว่าง)"))

    resp = client().messages.create(
        model=MODEL,
        max_tokens=1500,
        system=TEACHER_SYSTEM,
        messages=[{"role": "user", "content": "\n\n".join(parts)}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    data = _parse_json(text)
    data["score"] = max(0, min(10, int(data.get("score", 0))))
    data.setdefault("strengths", [])
    data.setdefault("weaknesses", [])
    return data


def grade_followup(lesson, exercise, followup_question, followup_answer, original_answer_summary, course_context=""):
    prompt = (
        f"คอร์ส: {course_context}\n"
        f"บทที่ {lesson['id']}: {lesson['title']} / แบบฝึกหัด {exercise['id']}\n"
        f"งานที่ผู้เรียนส่งมา (ย่อ):\n{original_answer_summary[:2000]}\n\n"
        f"คำถามแย้งกลับที่ครูถาม:\n{followup_question}\n\n"
        f"คำตอบของผู้เรียน:\n{followup_answer}"
    )
    resp = client().messages.create(
        model=MODEL,
        max_tokens=600,
        system=FOLLOWUP_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    data = _parse_json(text)
    data["bonus"] = max(0, min(2, int(data.get("bonus", 0))))
    return data


def sandbox_reply(exercise, messages):
    """AI ผู้ช่วยใน sandbox — system prompt มาจากแบบฝึกหัด"""
    system = exercise.get("sandbox_system") or SANDBOX_DEFAULT
    resp = client().messages.create(
        model=MODEL,
        max_tokens=1200,
        system=system,
        messages=[{"role": m["role"], "content": m["content"]} for m in messages],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def progress_summary(rows, course_title="", lesson_titles=None):
    """สรุปจุดแข็งจุดอ่อนจากประวัติคะแนนทั้งหมด (rows = list of dict)"""
    if not rows:
        return None
    lines = []
    for r in rows:
        lines.append(
            f"บท {r['lesson_id']} ข้อ {r['exercise_id']} ครั้งที่ {r['attempt']}: "
            f"{r['score']}/10 โบนัส {r.get('bonus') or 0} — {r.get('verdict') or ''}"
        )
    titles = ", ".join(f"{k} {v}" for k, v in (lesson_titles or {}).items())
    prompt = (
        f"นี่คือประวัติคะแนนทั้งหมดของผู้เรียนในหลักสูตร {course_title} ({titles})\n\n"
        + "\n".join(lines)
        + "\n\nเขียนสรุปสั้นๆ 4-6 ประโยค ภาษาไทย เรียกผู้เรียนว่า 'เพื่อน': จุดแข็ง 1-2 อย่าง จุดอ่อน 1-2 อย่าง (ระบุบท) และสิ่งเดียวที่ควรฝึกต่อ ห้ามชมพิธี ตอบเป็นข้อความธรรมดาไม่ใช่ JSON"
    )
    resp = client().messages.create(
        model=MODEL,
        max_tokens=500,
        system="คุณคือครูของหลักสูตร MAXX AI DOJO ตรงไปตรงมา",
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()

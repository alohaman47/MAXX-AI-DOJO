# -*- coding: utf-8 -*-
"""ทะเบียนคอร์สทั้งหมด — เพิ่มคอร์สใหม่: สร้าง lessons_<slug>.py แล้วลงทะเบียนที่นี่"""
import lessons_ai
import lessons_humanoid

COURSES = {
    "ai": {
        "slug": "ai",
        "title": "AI DOJO",
        "subtitle": "ทำงานร่วมกับ AI ให้เก่ง",
        "desc": "8 บท: รู้จัก AI, ตั้งโจทย์, ทำซ้ำ, แตกงาน, ตรวจสอบ, ทีม AI, AI ในระบบ, วิจารณญาณ",
        "teacher_context": "หลักสูตร AI DOJO ฝึกคนให้ทำงานร่วมกับ AI ได้เก่ง",
        "lessons": lessons_ai.LESSONS,
    },
    "humanoid": {
        "slug": "humanoid",
        "title": "HUMANOID DOJO",
        "subtitle": "จากศูนย์ถึงคนที่อุตสาหกรรม humanoid ต้องการ",
        "desc": "8 บท: ทำไมรูปคน, ร่างกาย, เซนเซอร์และสมอง, ข้อมูล teleop, Linux/ROS 2, MuJoCo, อุตสาหกรรมจริง, แผนงานและธุรกิจ",
        "teacher_context": "หลักสูตร HUMANOID DOJO เตรียมคนให้ทำงานหรือทำธุรกิจในอุตสาหกรรมหุ่นยนต์ humanoid (เป้าหมายแรก: ตำแหน่ง Data Collection Operator) ประเมินความถูกต้องทางเทคนิคอย่างเข้มงวด",
        "lessons": lessons_humanoid.LESSONS,
    },
}
ORDER = ["ai", "humanoid"]


def get_course(slug):
    return COURSES.get(slug)


def lesson_by_id(slug, lid):
    c = COURSES.get(slug)
    if not c:
        return None
    for l in c["lessons"]:
        if l["id"] == lid:
            return l
    return None


def get_exercise(slug, lid, ex_id):
    l = lesson_by_id(slug, lid)
    if not l:
        return None, None
    for e in l["exercises"]:
        if e["id"] == ex_id:
            return l, e
    return l, None

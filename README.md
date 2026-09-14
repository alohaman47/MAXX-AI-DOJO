# MAXX DOJO

โรงฝึกหลายคอร์ส มี Claude เป็นครูตรวจงาน ให้คะแนน และถามแย้งกลับ

คอร์สปัจจุบัน:
- **AI DOJO** (`/ai/`) — ทำงานร่วมกับ AI ให้เก่ง 8 บท
- **HUMANOID DOJO** (`/humanoid/`) — จากศูนย์ถึงคนที่อุตสาหกรรม humanoid ต้องการ 8 บท (เขียน 14 ก.ย. 2026 — บท 7 มีข้อมูลตลาดที่เปลี่ยนเร็ว)

## เพิ่มคอร์สใหม่

1. สร้าง `lessons_<slug>.py` ตามโครงเดียวกับ `lessons_ai.py`
2. ลงทะเบียนใน `courses.py` (COURSES + ORDER)
3. push — ไม่ต้องแก้ app.py หรือฐานข้อมูล

## ไฟล์

- `app.py` — Flask app ทั้งหมด (หน้า, ฐานข้อมูล, การส่งงาน)
- `grader.py` — ครู AI: system prompt, rubric, sandbox
- `courses.py` — ทะเบียนคอร์ส
- `lessons_ai.py`, `lessons_humanoid.py` — เนื้อหา ตัวอย่าง แบบฝึกหัด **แก้ตรงนี้ถ้าอยากเปลี่ยนเนื้อหา**
- `templates/` `static/` — หน้าเว็บ (มือถือเป็นหลัก)

## ขึ้น Railway (ทำจาก GitHub web ทั้งหมด)

1. สร้าง repo ใหม่บน GitHub เช่น `maxx-ai-dojo` แล้วอัปโหลดไฟล์ทั้งหมดในโฟลเดอร์นี้ (ลากทั้งโฟลเดอร์ `templates` และ `static` ไปด้วย)
2. Railway → New Project → Deploy from GitHub repo → เลือก repo
3. ในโปรเจค Railway กด **+ New → Database → PostgreSQL** (Railway จะใส่ `DATABASE_URL` ให้ service อัตโนมัติ ถ้าไม่ขึ้นให้เพิ่ม Variable Reference เอง)
4. ที่ service ของแอป → Variables เพิ่ม:
   - `ANTHROPIC_API_KEY` = คีย์จาก console.anthropic.com
   - `APP_PASSWORD` = รหัสเข้าแอป
   - `SECRET_KEY` = สตริงสุ่มยาวๆ อะไรก็ได้
   - (ไม่บังคับ) `CLAUDE_MODEL` = ค่าเริ่มต้น `claude-sonnet-4-6`
   - (ไม่บังคับ) `FREE_MODE` = `1` ถ้าอยากปลดล็อกทุกบทตั้งแต่แรก
5. Settings → Networking → Generate Domain แล้วเปิดจากมือถือ

## กติกา

- คะแนน 0-10 ต่อข้อ ผ่านที่ 7
- ทุกครั้งที่ครูตรวจ จะถามคำถามแย้งกลับ 1 ข้อ ต้องตอบก่อนถึงไปต่อได้ (โบนัส 0-2)
- ส่งได้สูงสุด 3 ครั้งต่อข้อ ถ้าครบ 3 ยังไม่ถึง 7 ไปต่อได้แต่บันทึกว่าไม่ผ่าน
- บทถัดไปปลดล็อกเมื่อทุกข้อในบทก่อนหน้าผ่านหรือครบ 3 ครั้ง
- แบบฝึกหัด sandbox: ครูให้คะแนนจากข้อความของเพื่อนเท่านั้น ไม่ใช่คำตอบของ AI ผู้ช่วย

## ค่าใช้จ่าย

ตรวจ 1 ครั้ง ≈ 1 call, sandbox 1 ข้อความ ≈ 1 call ใช้ Sonnet ตกข้อละไม่กี่บาท

## รันในเครื่อง (ถ้ามี)

```
pip install -r requirements.txt
ANTHROPIC_API_KEY=... APP_PASSWORD=dojo python app.py
```
ไม่มี `DATABASE_URL` จะใช้ SQLite (`dojo.db`) แทน

## ชั้น Ultralearning (ทุกคอร์ส)

ไฟล์ `ultra.py` ครอบทุกคอร์สอัตโนมัติ:
- **บท 0 Metalearning** — วางแผนการเรียนเองก่อนเริ่ม ต้องผ่านก่อนบท 1 แผนโผล่กลับมาในสมุดพกตอนจบคอร์ส
- **Retrieval** — ทุกบทต้องตอบคำถาม 3 ข้อจากหัวก่อนเห็นเนื้อหา (`RETRIEVAL` ใน ultra.py)
- **Retention** — ผ่านบทแล้วคำถามเดิมกลับมาถามในหน้าคอร์สทุก 3 → 7 → 14 → 30 วัน ตอบผิดกลับมา 3 วัน
- **Intuition (Feynman)** — ทุกบทมีข้อ `<บท>f` อธิบายให้เด็ก 10 ขวบฟัง ต้องผ่าน
- **Drill** — สมุดพก → "ซ้อมจุดอ่อน" ครูสร้างแบบฝึก 5 นาทีจากประวัติ ไม่นับคะแนน
- **Focus** — session timer 25 นาที บันทึกนาทีเรียนจริงต่อสัปดาห์

เพิ่มคอร์สใหม่ต้องเติม `RETRIEVAL[slug]` และ `FEYNMAN[slug]` ใน ultra.py ด้วย (ถ้าไม่เติม บทนั้นจะไม่มี gate และไม่มีข้อ Feynman)

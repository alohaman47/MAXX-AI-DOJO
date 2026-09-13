# MAXX AI DOJO

โรงฝึกทำงานร่วมกับ AI — หลักสูตร 8 บท มี Claude เป็นครูตรวจงาน ให้คะแนน และถามแย้งกลับ

## ไฟล์

- `app.py` — Flask app ทั้งหมด (หน้า, ฐานข้อมูล, การส่งงาน)
- `grader.py` — ครู AI: system prompt, rubric, sandbox
- `lessons.py` — เนื้อหา 8 บท ตัวอย่าง แบบฝึกหัด **แก้ตรงนี้ถ้าอยากเปลี่ยนเนื้อหา**
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

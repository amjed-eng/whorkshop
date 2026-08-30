أنت الآن تبدأ:

# PHASE 3 — PRE-FLIGHT 6/6 + RELIABILITY & FULL DEMO REHEARSAL

لمشروع:

**INTRUDER INVISIBLE — المتسلل الخفي**

المراجع الملزمة:

1. `ENGINEERING_LOG.md`
2. `PHASE_2_EXECUTION_PLAN.md`
3. دليل التنفيذ الهندسي الأصلي الموجود في المشروع/السياق

لا تعيد تصميم Commits 1–10.

لا تضف Framework أو Database أو Broker أو خدمة جديدة.

قبل Phase 3 نفّذ Final Phase-2 Gate صغيراً، ثم انتقل تلقائياً إلى Preflight إذا نجح.

---

## A. FINAL PHASE-2 GATE

### 1. أصلح Attack Path فقط إذا كانت المشكلة موجودة

راجع:

`static/app.js`

حالياً الـNetwork Graph يحتوي العقد المنطقية الست:

- Internet
- Gateway
- Web Service
- File Service
- Admin System
- Digital Vault

لكن لا تجعل ECharts link يستخدم `payload.source` كـNode غير موجود في graph.

يجب أن يبقى المصدر الحقيقي مأخوذاً من normalized event، لكن الرسم يجب أن يكون صالحاً فعلياً.

طبّق أبسط تصميم صحيح حسب الخطة:

إما:

- إضافة External Source node ديناميكياً باسم المصدر الحقيقي ثم ربطها بالهدف،

أو حل مكافئ يحافظ على:
- العقد الست الأصلية
- ظهور المصدر الخارجي
- Attack Path مرئي

لا تعد لإرسال `raw_event`.

أضف اختباراً يثبت أن source الخارجي له Node صالح في ECharts graph أو يتم تمثيله بطريقة قابلة للرسم فعلياً.

---

### 2. تحقق من Timeline Tests

تأكد أن:

`tests/test_timeline.py`

موجود فعلياً ومتعقب في Git، وليس مجرد اسم داخل `architecture.txt`.

يجب أن يثبت:

- Timeline تستخدم ECharts.
- المراحل الخمس موجودة.
- `updateTimeline()` تستخدم `state.timeline`.
- `RESET` يمسحها.
- `resize()` يشمل timelineChart.
- Timeline لا تعتمد على AI_RESULT.

---

### 3. Phase-2 Final Commands

شغّل من project root:

`python3 -m unittest discover -s tests -v`

المطلوب:

- Failures = 0
- Errors = 0
- Skipped = 0

ثم:

`python3 -m compileall app.py db.py state.py ai_worker.py telegram_worker.py prompt.py replay.py tests`

ثم:

`git status --short`

لا تبدأ Phase 3 إذا فشل أي شرط.

حدّث `ENGINEERING_LOG.md` بالعدد الحقيقي للاختبارات.

بعد النجاح فقط:

`Phase 2 Final Status = PASSED`

ثم انتقل مباشرة إلى Phase 3 أدناه.

============================================================
PHASE 3 — PRE-FLIGHT
============================================================

## 4. الهدف

قبل دخول الجمهور يجب أن يكون لدينا **فحص واحد فقط** يعطي حالة ستة أنظمة:

1. OpenCanary reachable
2. Flask running
3. Groq API responding
4. Telegram test delivered
5. SQLite writable
6. ECharts loaded locally

وعند نجاحها كلها فقط:

`DEMO READY — 6/6 SYSTEMS ONLINE`

ممنوع fake status.

ممنوع hard-coded PASS.

كل نتيجة يجب أن تأتي من فحص حقيقي.

---

## 5. تنفيذ Preflight بأقل معمارية ممكنة

أنشئ مكوّناً صغيراً فقط، مثل:

`preflight.py`

بحيث يمكن تشغيل Preflight بأمر واحد من terminal.

لا تضف Framework جديد.

استخدم Python Standard Library والمكونات الموجودة في المشروع.

يفضل أن تكون نتيجة كل check structured داخلياً، مثل:

- name
- status
- detail

ولا تعرض secrets.

---

## 6. OpenCanary Check

تحقق من أن OpenCanary reachable فعلياً باستخدام الإعداد الموجود للمشروع.

لا تخترع نجاحاً إذا لم يكن OpenCanary configured.

النتائج الممكنة:

`PASS`

أو:

`FAIL`

إذا فشل OpenCanary:

Preflight يجب أن يوضح:

`LIVE MODE UNAVAILABLE — USE REPLAY`

لكن لا تعتبر ذلك سبباً لتعطيل Replay نفسه.

لا تحاول إنشاء OpenCanary بديل داخل Flask.

---

## 7. Flask Check

تحقق من أن Flask الحالي يعمل فعلياً.

استخدم endpoint موجوداً مثل:

`GET /health`

ولا تنشئ Server ثانياً.

المطلوب:

HTTP success
+
response valid

---

## 8. Groq Check

استخدم Groq Python SDK الحقيقي.

الموديل يبقى:

`openai/gpt-oss-20b`

نفذ أصغر request حقيقي مناسب للتحقق أن:

- GROQ_API_KEY موجود
- API reachable
- model responding

هذا Preflight حقيقي، وليس Unit Test Fake.

لكن لا تستخدم Groq داخل Webhook.

Preflight مسار منفصل عن ingestion.

إذا فشل Groq:

اعرض:

`Groq = FAIL`

ولا تدّع AI ONLINE.

---

## 9. Telegram Check

استخدم Telegram transport الحالي نفسه.

نفذ رسالة Preflight حقيقية إلى:

`TELEGRAM_CHAT_ID`

باستخدام:

`TELEGRAM_BOT_TOKEN`

ولا تكرر implementation Telegram ثانية.

رسالة بسيطة مثل:

`INTRUDER INVISIBLE — PRE-FLIGHT TEST`

تكفي.

يجب التأكد من نجاح Telegram API response.

إذا فشل:

`Telegram = FAIL`

ولا يؤثر ذلك على بقية الفحوص.

لا تسجل token أو chat ID.

---

## 10. SQLite Writable Check

لا يكفي أن الملف موجود.

يجب إثبات أن SQLite قابلة للكتابة فعلياً.

استخدم اتصالاً مستقلاً قصير العمر وفق نفس قواعد المشروع.

نفذ write verification آمنة لا تترك Evidence وهمية داخل الجولة.

يمكن استخدام transaction ثم rollback أو آلية صغيرة مكافئة.

المطلوب:

Open
→ Write-capable transaction
→ Verify
→ Rollback/Cleanup
→ Close

إذا SQLite FAIL:

هذه حالة BLOCKING.

اعرض بوضوح:

`DEMO NOT READY — SQLITE FAILURE`

وحسب الدليل:

**لا يبدأ العرض.**

---

## 11. ECharts Check

تحقق من:

`static/echarts.min.js`

بأنه:

- موجود محلياً
- ملف حقيقي
- غير placeholder
- يتم تقديمه محلياً من Flask
- لا يعتمد على CDN

الأفضل أن يتحقق Preflight من وصول الملف عبر Flask المحلي أيضاً، وليس مجرد `os.path.exists`.

---

## 12. نتيجة Preflight

أظهر output واضحاً مثل:

`PRE-FLIGHT`

ثم الستة بالترتيب.

إذا كلها PASS:

`DEMO READY — 6/6 SYSTEMS ONLINE`

إذا بعضها FAIL:

لا تعرض 6/6.

اعرض العدد الحقيقي.

مثلاً:

`DEMO NOT READY — 5/6 SYSTEMS ONLINE`

إذا OpenCanary فقط FAIL ولكن الباقي سليم:

اعرض أيضاً:

`LIVE MODE UNAVAILABLE — REPLAY READY`

إذا SQLite FAIL:

اعرض بوضوح أن العرض غير جاهز.

---

## 13. لا تجعل Preflight جزءاً من المسار الحرج

ممنوع أن يصبح كل Webhook يعيد فحص الخدمات الست.

Preflight يعمل قبل العرض عند الطلب فقط.

بعد نجاحه، ingestion path يبقى كما هو.

============================================================
PHASE 3 — STABILITY TESTS
============================================================

بعد بناء Preflight، نفذ اختبارات الاستقرار الثمانية الموجودة في الدليل حرفياً.

---

## Test 1 — Event Ingestion

أرسل Event واحداً.

يجب أن يحدث:

- HTTP success
- SQLite row
- Dashboard/SSE update
- AI queue task

بدون انتظار Groq.

أثبت ذلك آلياً بقدر الإمكان.

---

## Test 2 — Groq Delay

حاكي delay أو timeout في Groq.

يجب أن يستمر:

- Dashboard
- Local risk
- Timeline
- SQLite

ولا تتجمد الشاشة.

لا تنتج AI result مزيفاً.

---

## Test 3 — Telegram Failure

حاكي Telegram failure أثناء حدث CRITICAL.

يجب أن يبقى:

- CRITICAL
- Risk 91
- AI Result
- SQLite Evidence
- Dashboard alive

الفشل فقط:

Telegram delivery.

---

## Test 4 — Browser Reload

ضع النظام في:

`CRITICAL_INTRUSION`

Risk:

`91`

Timeline populated.

ثم تحقق من snapshot الذي يرسله SSE عند اتصال Browser جديد.

يجب أن يستطيع Browser reload استعادة:

- CRITICAL
- 91
- Timeline
- containment/state information

بدون Reset.

---

## Test 5 — Reset During AI

ابدأ AI request.

قبل اكتماله:

`RESET DEMO`

ثم دع نتيجة AI القديمة تصل.

يجب:

`Ignored`

ولا تغير:

- generation الجديدة
- risk
- state
- SQLite classification للجولة الجديدة
- Telegram queue
- SSE AI_RESULT

---

## Test 6 — Replay

شغّل بالترتيب:

Event #1
Event #2
Event #3

وتحقق:

Event #1:
Risk 21

Event #2:
Risk 48

Event #3:
Risk 91
CRITICAL_INTRUSION

وتأكد أن Replay يستخدم نفس:

`ingest_event()`

وأن المخرجات البصرية/state هي نفس منطق Live.

لا Fake Dashboard events.

---

## Test 7 — Forensics

بعد الأحداث ثم Containment:

نفذ Crime Scene.

يجب أن تأتي الأدلة من SQLite فعلياً.

تحقق من:

1. First Seen
2. Origin
3. First Target
4. Activity Sequence
5. Critical Transition

ولا تستخدم Animation ثابتة أو بيانات hard-coded.

---

## Test 8 — Final Reset

بعد سيناريو كامل:

`RESET DEMO`

يجب:

- Risk = 0
- State = NORMAL
- Timeline = empty
- SQLite demo evidence = empty
- AI card cleared
- Network visual = NORMAL
- Telegram dedup reset
- generation incremented

النظام جاهز لجولة جديدة دون restart.

============================================================
FULL REHEARSAL
============================================================

## 14. نفذ بروفة السيناريو الكامل

استخدم Replay أولاً لأنه Safety Path الرسمي.

التسلسل:

RESET

→ Event 1
→ 21 / UNDER_OBSERVATION

→ Event 2
→ 48 / UNDER_OBSERVATION

→ Event 3
→ 91 / CRITICAL_INTRUSION

→ Telegram CRITICAL path

→ ISOLATE THREAT
→ CONTAINED

→ RECONSTRUCT CRIME SCENE
→ FORENSIC

→ EXECUTIVE SUMMARY
→ EXECUTIVE

→ RESET
→ NORMAL / 0

لا تغير قيم السيناريو.

---

## 15. Live/Replay Readiness

إذا OpenCanary متصل:

سجل:

`LIVE READY`

إذا OpenCanary غير متصل لكن Replay يعمل:

سجل:

`REPLAY READY`

لا تعتبر Replay فشلاً؛ هو fallback الرسمي في الدليل.

---

## 16. Manual Browser Verification

هذه المرحلة تحتاج فحصاً بصرياً حقيقياً.

تحقق يدوياً من:

- NORMAL screen
- Gauge 0
- Event 1 → 21
- Event 2 → 48
- Event 3 → 91
- Red critical visual
- Network attack path
- Timeline progression
- Audio after ARM AUDIO
- Containment stops critical pulse
- Crime Scene view
- Executive Mode
- Browser reload restores state
- Reset returns clean screen

إذا لم تستطع فتح Browser:

اكتب:

`Manual Browser Verification = NOT EXECUTED`

ولا تكتب PASSED.

---

## 17. Unit Tests

أنشئ Tests جديدة فقط حيث تحتاج لإثبات Preflight/Stability.

استخدم:

Python unittest

ولا تضف pytest أو Node test framework.

اختبارات Preflight الخارجية تستخدم mocks في Unit Tests.

أما Final Preflight الحقيقي فيتم تشغيله منفصلاً مع الخدمات الحقيقية.

---

## 18. Regression Gate

يجب أن تبقى كل اختبارات المشروع السابقة ناجحة.

شغّل:

`python3 -m unittest discover -s tests -v`

المطلوب:

- Failures = 0
- Errors = 0
- Skipped = 0

ثم:

`python3 -m compileall app.py db.py state.py ai_worker.py telegram_worker.py prompt.py replay.py preflight.py tests`

---

## 19. Security / Anti-Laziness

راجع مجدداً:

TODO
FIXME
PLACEHOLDER
NotImplementedError
pass
fake success
hard-coded external success

ومنع:

- Telegram secrets في frontend/logs
- Groq key في frontend
- CDN
- raw event في browser
- synchronous Groq
- synchronous Telegram
- shared SQLite connection

---

## 20. ENGINEERING_LOG

لا تحذف التاريخ السابق.

أضف:

`## Phase 3 — Preflight & Reliability`

ويحتوي:

### Preflight Implementation

### OpenCanary Check

### Flask Check

### Groq Check

### Telegram Check

### SQLite Check

### ECharts Check

### Stability Test 1

### Stability Test 2

### Stability Test 3

### Stability Test 4

### Stability Test 5

### Stability Test 6

### Stability Test 7

### Stability Test 8

### Automated Test Results

### Compile Result

### Real Preflight Result

### Manual Browser Verification

### Final Readiness

لا تكتب:

`DEMO READY — 6/6 SYSTEMS ONLINE`

في التوثيق كنجاح فعلي إلا إذا تم تشغيل Preflight الحقيقي ونجحت الخدمات الست فعلياً.

---

## 21. Final Verdict

التقرير النهائي يجب أن يكون أحد:

`DEMO READY — 6/6 SYSTEMS ONLINE`

أو:

`NOT READY`

أو:

`REPLAY READY — LIVE UNAVAILABLE`

حسب النتائج الحقيقية.

وأرسل في النهاية:

1. Phase-2 gate result
2. Final test count
3. Preflight six checks
4. Stability tests 1–8
5. Manual browser result
6. Live readiness
7. Replay readiness
8. Final demo readiness

لا تبدأ أي Feature جديدة بعد ذلك.
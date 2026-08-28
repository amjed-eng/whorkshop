أنت الآن تعمل كـ **Senior Python + Frontend + Security Engineer** على مشروع:

**INTRUDER INVISIBLE — المتسلل الخفي**

تم اعتماد Commits 1–5 نهائياً بعد:

* 54 Tests Passed
* 0 Failures
* 0 Errors
* 0 Skipped
* compileall successful
* Flask Debug disabled
* Werkzeug reloader disabled
* AI Worker startup idempotent
* SQLite thread isolation verified
* Groq asynchronous isolation verified

**لا تعيد تصميم Commits 1–5.**

مهمتك في هذه الجلسة هي تنفيذ:

**Commit 6 → Commit 10 فقط**

وبالترتيب الحرفي المحدد أدناه.

============================================================
0. القواعد المعمارية غير القابلة للتفاوض
========================================

اقرأ `ENGINEERING_LOG.md` كاملاً قبل تعديل أي ملف.

ثم افحص الكود الحالي:

* `app.py`
* `state.py`
* `db.py`
* `ai_worker.py`
* `prompt.py`
* `requirements.txt`
* جميع ملفات `tests/`

لا تفترض شكل البيانات.
استخرج العقود الحالية من الكود المعتمد.

يحظر كسر أي اختبار حالي.

بعد كل Commit:

1. شغل جميع الاختبارات.
2. أصلح أي regression.
3. حدّث `ENGINEERING_LOG.md`.
4. أنشئ Git commit حقيقياً إذا Git متاح.
5. لا تنتقل للـCommit التالي قبل نجاح المشروع كله.

---

# 1. Anti-Laziness Rules

ممنوع تماماً:

`TODO`
`FIXME`
`pass`
`NotImplementedError`
`PLACEHOLDER`
`Add code here`
`Implement later`
fake implementation
dummy response
hard-coded fake external success
pseudo-code داخل production files

كل Function يتم إنشاؤها يجب أن تعمل فعلياً.

كل Route جديد يجب أن يعمل فعلياً.

كل Button في الواجهة يجب أن يكون مربوطاً بوظيفة حقيقية.

ممنوع إنشاء UI شكلي لا يتصل بالنظام.

---

# 2. ممنوع إضافة تقنيات جديدة

Tech Stack يبقى حصراً:

* Python
* Flask
* sqlite3
* Groq Python SDK
* queue.Queue
* threading
* Telegram Bot API عبر HTTP
* urllib من Python Standard Library
* HTML
* CSS
* Vanilla JavaScript
* SSE / EventSource
* Apache ECharts
* Web Audio API
* Environment Variables

ممنوع:

* React
* Vue
* Angular
* Node.js
* npm runtime
* Tailwind
* Bootstrap
* Material UI
* jQuery
* Socket.IO
* WebSocket
* Redis
* Celery
* Kafka
* RabbitMQ
* python-telegram-bot
* Telethon
* requests كـdependency جديدة
* Axios
* Three.js
* WebGL Framework
* أي Database جديدة
* أي Audio Library
* أي Visualization Library غير ECharts

---

# 3. القاعدة الذهبية

المسار الأساسي يبقى:

OpenCanary
→ Flask
→ Normalize
→ SQLite
→ Local State
→ SSE
→ Browser

وبشكل منفصل:

AI Queue
→ AI Worker
→ Groq
→ SQLite
→ SSE AI_RESULT
→ Telegram Queue
→ Telegram Worker
→ Telegram API

ممنوع تماماً:

Webhook
→ Telegram API

وممنوع:

Webhook
→ wait for Groq

وممنوع:

Browser
→ Groq

وممنوع:

Browser
→ Telegram

---

# 4. التوثيق الإجباري

لا تمسح أي قسم موجود في:

`ENGINEERING_LOG.md`

هو سجل تراكمي دائم.

قبل كل Commit اقرأ السجل مرة أخرى.

بعد كل Commit أضف:

## Commit N — <Name>

### Goal

### Files Created

### Files Modified

### Functions Added

### Routes Added

### Data Flow

### Security Guarantees

### Tests Added

### Tests Executed

### Test Result

### Architectural Decisions

### Deferred By Design

إذا واجهت قراراً غير محدد صراحةً:
اختر أبسط حل يحافظ على المعمارية وسجله.

لا تضف Framework بسبب قرار صغير.

============================================================
COMMIT 6 — TELEGRAM TRANSPORT
=============================

أنشئ:

`telegram_worker.py`

و:

`tests/test_telegram_worker.py`

Telegram يجب أن يعمل باستخدام:

**Telegram Bot API مباشرة عبر HTTPS**

ومكتبات Python القياسية فقط.

استخدم:

* `urllib.request`
* `urllib.parse`
* `json` عند الحاجة
* `logging`
* `threading`

لا تستخدم:

`python-telegram-bot`

ولا:

`Telethon`

ولا:

`requests`

---

# 5. Telegram Secrets

اقرأ فقط:

`TELEGRAM_BOT_TOKEN`

و:

`TELEGRAM_CHAT_ID`

من:

`os.environ`

ممنوع:

* hard-code
* وضعهما في HTML
* وضعهما في JavaScript
* إرجاعهما من API
* تسجيلهما في logs
* تخزينهما في SQLite

---

# 6. Telegram sendMessage

أنشئ Function كاملة مثل:

`send_telegram_message(message, token=None, chat_id=None, opener=None)`

أو تصميم صغير مكافئ.

يجب أن ترسل:

`message`

إلى Telegram Bot API:

`sendMessage`

باستخدام HTTP POST.

استخدم plain text.

لا تضف Markdown/HTML parsing غير مطلوب.

ضع timeout معقول على HTTP request حتى لا يبقى Telegram Worker معلقاً بلا نهاية.

لكن:

**Telegram Worker منفصل أصلاً عن Flask وAI.**

أي timeout لا يجب أن يؤثر على Dashboard.

---

# 7. Telegram Task Contract

افحص `ai_worker.py` أولاً واعرف شكل الـtask الذي يدخل:

`telegram_queue`

لا تخترع contract آخر إذا الموجود كافٍ.

يجب أن يحمل على الأقل ما يسمح بـ:

* `event_id`
* `generation`
* message الناتجة من `telegram_alert`

إذا كان أحدها ناقصاً:

عدّل `ai_worker.py` بأقل تغيير ممكن فقط لإكمال العقد.

المصدر الوحيد لنص Telegram:

`telegram_alert`

من Groq JSON المقبول.

ممنوع إنشاء رسالة Telegram مستقلة مختلفة عن AI result.

---

# 8. Telegram Generation Protection

قبل أي network call:

قارن:

`task.generation`

مع:

`state.get_generation()`

إذا كانت task قديمة:

DISCARD

ولا تتصل بالإنترنت.

وبذلك:

Generation 7
→ Telegram queued

Reset
→ Generation 8

Old Telegram task from 7
→ discarded

---

# 9. Telegram Deduplication

الدليل يشترط أن:

`RESET DEMO`

يمسح Telegram deduplication state.

لذلك أنشئ أبسط Deduplication mechanism ممكن.

استخدم مفتاحاً مستقراً مرتبطاً بالجولة والحدث، مثل:

`(generation, event_id)`

أو equivalent مبني على contract الحالي.

لا ترسل نفس Critical Alert مرتين لنفس event في نفس generation.

استخدم Lock لأن Telegram Worker background thread.

أنشئ function واضحة مثل:

`reset_deduplication()`

وعند:

`POST /demo/reset`

يجب أن يتم مسح dedup state.

لا تعيد تشغيل Telegram service.

---

# 10. Telegram Failure Isolation

هذه الحالات يجب ألا تسقط Thread:

* token missing
* chat id missing
* DNS/network error
* timeout
* HTTP 4xx
* HTTP 5xx
* malformed task
* unexpected response

استخدم logging.

ممنوع crash.

ممنوع fake success.

إذا فشل Telegram:

* SQLite يبقى سليماً.
* AI result يبقى سليماً.
* Dashboard يبقى سليماً.
* Flask يبقى يعمل.

---

# 11. Telegram Background Worker

Telegram يجب أن يملك Worker منفصلاً عن AI Worker:

AI Worker
→ telegram_queue
→ Telegram Worker
→ HTTPS

ادمجه في:

`start_runtime_workers()`

مع الحفاظ على خصائص الدالة المعتمدة:

* idempotent
* لا duplicate Threads
* إعادة التشغيل ممكنة إذا مات Thread

احتفظ:

`_ai_thread`

وأضف:

`_telegram_thread`

مع Lock مناسب.

لا تغير التشغيل إلى Debug.

يبقى:

`debug=False`
`use_reloader=False`

---

# 12. Commit 6 Tests

اختبر بدون Internet باستخدام `unittest.mock`.

اختبر:

1. missing token.
2. missing chat ID.
3. malformed task.
4. stale generation discarded before network.
5. successful sendMessage.
6. HTTP 500.
7. network exception.
8. timeout.
9. duplicate same `(generation,event_id)` sent once.
10. reset dedup allows same event identity in new/reset context حسب التصميم.
11. Telegram failure does not affect state.
12. Telegram failure does not affect SQLite.
13. Telegram Worker survives failed task and processes next task.
14. `start_runtime_workers()` remains idempotent with both workers.
15. dead Telegram thread can be restarted.
16. AI thread remains unaffected by Telegram failure.

ممنوع الاتصال الحقيقي بـTelegram في Unit Tests.

ثم شغل:

`python3 -m unittest discover -s tests -v`

لا تنتقل إلا عند:

0 Failures
0 Errors
0 Skipped

ثم:

Git commit:

`feat(telegram): add asynchronous Telegram transport`

============================================================
COMMIT 7 — FULL SCREEN DASHBOARD + EVENTSOURCE
==============================================

أنشئ:

`templates/index.html`

`static/style.css`

`static/app.js`

لا تنشئ ECharts logic الآن إلا في Commit 8.

Commit 7 مسؤول عن:

* الصفحة
* Layout
* DOM
* Styling
* SSE connection
* State rendering
* AI card rendering
* controls
* reconnect behavior

---

# 13. Flask Root

غيّر:

`GET /`

من JSON backend response إلى:

`render_template("index.html")`

لا تضف React.

لا تضف `/api/status` إذا لم يكن هناك سبب في الدليل.

SSE هو قناة التحديث.

يبقى:

`GET /events`

مصدر التحديث اللحظي.

---

# 14. Dashboard Layout

صفحة واحدة:

**Full Screen**

ولا تعرض Terminal.

ولا Raw Logs.

قسّم الشاشة إلى:

1. أعلى:
   `SECURITY RISK`

2. يسار/وسط:
   `DIGITAL CITY`

3. يمين:
   `AI EXECUTIVE BRIEF`

4. أسفل:
   `ATTACK TIMELINE`

وأضف أربع بطاقات صغيرة فقط:

* Events Detected
* Most Targeted Asset
* Detection Time: LIVE
* Containment Status

لا تنشئ عشرين KPI.

---

# 15. حالات النظام المرئية

الواجهة يجب أن تدعم:

`NORMAL`

`UNDER_OBSERVATION`

`CRITICAL_INTRUSION`

`CONTAINED`

`FORENSIC`

`EXECUTIVE`

اعرض النص بصرياً بشكل واضح.

لا تجعل JavaScript يستنتج الحالة من نص AI.

الحالة تأتي من:

`STATE`

أو snapshot الحالي.

---

# 16. SSE EventSource

في `app.js`:

أنشئ:

`new EventSource("/events")`

وتعامل مع envelope الحالي:

`STATE`
`EVENT`
`AI_RESULT`
`RESET`

لا تستخدم WebSocket.

لا تستخدم polling كبديل أساسي.

---

# 17. SSE Snapshot

عند فتح الصفحة أو إعادة تحميلها:

الـSSE endpoint الحالي يرسل snapshot.

يجب أن تبني الواجهة نفسها من هذا snapshot.

إذا كان النظام قبل reload:

CRITICAL
Risk 91
Timeline populated

يجب أن تعود الشاشة إلى نفس الحالة.

لا تجعل reload يعيد UI إلى NORMAL بشكل أعمى.

---

# 18. EVENT Behavior

عند وصول:

`EVENT`

فوراً:

* حدث event count.
* حدث current risk.
* حدث current stage.
* حدث timeline.
* حدث containment/state label.
* أظهر:
  `Analyzing with Groq AI...`

ولا تنتظر:

`AI_RESULT`

حتى تحرك الشاشة.

---

# 19. AI_RESULT Behavior

عند وصول:

`AI_RESULT`

اعرض فقط الحقول التنفيذية المفهومة:

* `executive_title`
* `executive_summary`
* `business_impact`
* `recommended_action`
* `severity`

لا تعرض:

* raw log
* internal schema
* ports الخام
* src_host
* logtype
* JSON dump

---

# 20. DOM Security — إلزامي

ممنوع تماماً استخدام event/AI data عبر:

`innerHTML`

`outerHTML`

`insertAdjacentHTML`

استخدم:

`textContent`

أو:

`document.createElement()`

ثم:

`.textContent = value`

أي string من:

* OpenCanary
* Groq
* SQLite
* SSE

يعامل كـDATA فقط.

ليس HTML.

هذه قاعدة أمنية إلزامية.

---

# 21. External Assets

ممنوع:

CDN

ممنوع:

Google Fonts

ممنوع:

jsDelivr

ممنوع:

unpkg

ممنوع أي dependency runtime من الإنترنت.

CSS يستخدم system fonts.

---

# 22. Dashboard Controls

أضف Controls واضحة:

`ISOLATE THREAT`

`RECONSTRUCT CRIME SCENE`

`EXECUTIVE SUMMARY`

`RESET DEMO`

وزر:

`ARM AUDIO`

سيتم تفعيله فعلياً في Commit 9.

في Commit 7 يمكن أن يكون عنصر UI موجوداً، لكن لا تضع fake audio implementation.

إذا وجود Button غير فعال يخالف Anti-Laziness، لا تضفه حتى Commit 9.

الأفضل:
أضفه في Commit 9.

---

# 23. ISOLATE THREAT

يرسل:

`POST /contain`

فقط.

لا Firewall.

لا shell command.

لا iptables.

بعد النجاح:

الحالة تأتي من backend/SSE:

`CONTAINED`

ويجب أن تختفي/تتوقف visual pulse في الواجهة.

اعرض:

`THREAT CONTAINED`

---

# 24. Crime Scene

زر:

`RECONSTRUCT CRIME SCENE`

يرسل:

`POST /crime-scene`

استخدم response الحقيقي القادم من SQLite.

اعرض **خمسة أدلة فقط**:

1. First Seen
2. Origin
3. First Target
4. Activity Sequence
5. Critical Transition

استخدم المصطلح:

`Origin Observed First`

ولا تستخدم:

`Patient Zero`

لا تخترع Evidence من JavaScript.

---

# 25. Executive Mode

زر:

`EXECUTIVE SUMMARY`

يرسل:

`POST /executive`

ثم يبدل الشاشة إلى Executive View.

اخف التفاصيل التقنية.

استخدم AI result المقبول الموجود في state إذا كان متوفراً.

لا تخترع تحليل AI جديد في Browser.

---

# 26. Reset Demo

زر:

`RESET DEMO`

يرسل:

`POST /demo/reset`

وعند SSE:

`RESET`

يجب:

* risk → 0
* state → NORMAL
* timeline cleared
* AI card cleared
* network UI reset
* counters reset
* crime scene hidden
* executive mode hidden

ولا تعيد تحميل الصفحة إجبارياً.

---

# 27. Commit 7 Tests

استخدم Python `unittest`.

لا تضف Node testing tools.

اختبر:

* GET `/` returns HTML.
* template exists.
* CSS exists.
* JS exists.
* EventSource references `/events`.
* no WebSocket.
* no Socket.IO.
* no CDN.
* no Google Fonts.
* no `innerHTML`.
* no `insertAdjacentHTML`.
* no external script URLs.
* required dashboard sections exist.
* buttons call correct Flask endpoints.
* raw log table غير موجودة.

شغل كامل الاختبارات.

Git commit:

`feat(ui): add secure SSE dashboard shell`

============================================================
COMMIT 8 — LOCAL APACHE ECHARTS VISUALIZATION
=============================================

Commit 8 فقط الآن يضيف ECharts.

المكتبة الوحيدة للVisualization:

**Apache ECharts**

يجب أن يوجد الملف الحقيقي:

`static/echarts.min.js`

وتحميله داخل HTML هكذا محلياً.

ممنوع CDN.

ممنوع runtime Internet.

---

# 28. ECharts Artifact Rule

لا تكتب ملفاً وهمياً باسم:

`echarts.min.js`

ممنوع Placeholder.

يجب أن يكون **Apache ECharts distribution الحقيقي**.

إذا كان الملف موجوداً في البيئة:
استخدمه.

إذا كان يمكن الحصول على الـofficial distribution في البيئة:
ضعه محلياً.

ممنوع npm runtime أو Node architecture.

إذا تعذر تماماً الحصول على ملف Apache ECharts الحقيقي:

**أوقف Commit 8 كـBLOCKED.**

لا تنشئ مكتبة مزيفة.

لا تدّع النجاح.

---

# 29. Network Map

أنشئ ECharts Graph يحتوي الأصول المنطقية:

`Internet`

`Gateway`

`Web Service`

`File Service`

`Admin System`

`Digital Vault`

ويظهر المصدر الخارجي عند وجود Event.

الحالات:

`NORMAL`
`OBSERVED`
`CRITICAL`
`CONTAINED`

الوضع الطبيعي:
هادئ أخضر/أزرق.

---

# 30. Immediate Attack Visualization

Event #1:

External Source
→ Web Service

Pulse/edge animation مرئي.

Target يصبح observed.

Event #2:
يظهر استمرار المسار من نفس source.

Critical Event:
Target الحساس يحصل على:

* red visual
* glow
* critical state
* animated attack edge

**كل هذا من EVENT/STATE المحلي فوراً.**

لا تنتظر AI_RESULT.

---

# 31. Risk Gauge

أنشئ ECharts Gauge واحداً:

`SECURITY RISK`

القيم المطلوبة:

0
21
48
91

والـGauge يأخذ القيمة الحالية من state.

لا تضع animation يعيد risk إلى صفر عند AI delay.

---

# 32. Timeline

استخدم Timeline واحداً فقط:

`Discovery`

`Service Probe`

`Access Attempt`

`Escalation`

`Containment`

تضاء المرحلة فقط إذا ظهرت في state timeline.

لا تضف Timeline ثانية.

---

# 33. Attack Path

استخدم ECharts لإظهار المسار الفعلي بين العقد التي تم لمسها.

لا تستخدم animation فيديو جاهزة.

البيانات تأتي من Events الحالية.

عند Forensic View، يمكن إعادة استخدام نفس ECharts graph لتمثيل:

Origin
→ First Target
→ Activity Sequence
→ Critical Transition
→ Containment

---

# 34. ECharts Resize

عند تغيير حجم الشاشة:

استخدم:

`chart.resize()`

لكل chart.

لا تنشئ chart جديداً مع كل event.

أنشئ instances مرة واحدة ثم:

`setOption()`

---

# 35. No Additional Visualization Libraries

ممنوع:

Chart.js
D3
Three.js
Canvas libraries
WebGL frameworks

ECharts فقط.

CSS animations مسموح للمؤثرات المحيطة.

---

# 36. Commit 8 Tests

اختبر:

* `static/echarts.min.js` موجود.
* ليس Placeholder.
* HTML يحمل الملف محلياً.
* لا CDN ECharts.
* لا visualization library أخرى.
* Network nodes الستة موجودة.
* Gauge initialization موجود.
* Timeline initialization موجود.
* Attack Path يستخدم ECharts.
* resize handler موجود.
* Event rendering لا يعتمد على AI result.

أضف Manual Verification في ENGINEERING_LOG:

* Load dashboard.
* Verify NORMAL/0.
* simulate Event 1.
* visually confirm 21.
* Event 2 → 48.
* Critical event → 91.
* reload page.
* confirm state restored.

إذا لا تستطيع فتح Browser في IDE:
سجل manual verification كـNot Executed وليس Passed.

لا تكذب.

Git commit:

`feat(charts): add local ECharts security visualization`

============================================================
COMMIT 9 — WEB AUDIO API
========================

لا تستخدم Audio file.

لا تستخدم Audio library.

استخدم:

**Web Audio API Native**

مثل:

`AudioContext`

`OscillatorNode`

`GainNode`

لإنشاء صوت قصير جداً.

---

# 37. ARM AUDIO

المتصفحات قد تمنع autoplay.

لذلك أضف:

`ARM AUDIO`

ضمن Presenter Controls.

لا تستخدم audio تلقائياً قبل تفاعل المستخدم.

عند الضغط:

* create/resume AudioContext.
* set `audioArmed = true`.
* update button/status safely.

لا تخزن شيء في backend.

---

# 38. CRITICAL Alert

عندما يصل local state إلى:

`CRITICAL_INTRUSION`

يجب:

* Red Pulse
* Target Glow
* CRITICAL label
* short audio alert IF audioArmed

الصوت **لا يجب أن ينتظر Groq**.

لكن إذا جاء AI_RESULT severity CRITICAL لنفس event بعد ذلك:

لا تشغل الصوت مرة ثانية.

استخدم local dedupe داخل الواجهة حسب:

generation + critical transition

أو أبسط equivalent متوافق مع snapshot الحالي.

---

# 39. Audio Failure Isolation

هذه الحالات لا تؤثر على العرض:

* Web Audio unavailable
* AudioContext creation error
* resume error
* browser blocks audio

Visual alert يبقى يعمل.

لا تظهر JavaScript crash.

---

# 40. Reset Audio State

عند:

`RESET`

امسح critical-alert dedupe الخاص بالجولة.

لا يلزم إغلاق AudioContext إذا كان Armed للعرض التالي.

لكن لا تجعل Reset يشغل صوتاً.

---

# 41. Commit 9 Tests

Static/frontend contract tests باستخدام Python:

* no audio library.
* `AudioContext` used.
* ARM AUDIO control exists.
* audio only follows user interaction.
* critical handler exists.
* RESET clears alert dedupe.
* no external audio file required.
* no autoplay attribute.
* visual CRITICAL logic لا يعتمد على نجاح audio.

ثم كامل tests.

Git commit:

`feat(audio): add resilient critical Web Audio alert`

============================================================
COMMIT 10 — DEMO REPLAY MODE
============================

أنشئ:

`replay.py`

ومجلد:

`replay/`

وملف:

`replay/events.json`

هذه أهم طبقة Safety Demo.

---

# 42. Replay Architecture Rule

ممنوع:

Replay
→ Dashboard directly

ممنوع:

Replay
→ JavaScript fake event

ممنوع:

Replay
→ Fake AI result

الصحيح:

Replay Event
→ SAME backend ingestion path
→ normalize_event()
→ SQLite
→ state machine
→ SSE
→ AI queue
→ Groq
→ Telegram queue

Replay يغير فقط:

**مصدر الحدث**

كل شيء بعد ذلك متطابق.

---

# 43. Shared Ingestion Function

راجع `POST /webhook/opencanary`.

إذا كانت خطوات ingestion لا تزال داخل Route نفسها:

استخرجها بأقل refactor ممكن إلى Function داخل `app.py` مثل:

`ingest_event(raw_event)`

ويجب أن تنفذ بنفس الترتيب المعتمد:

1. normalize
2. hash
3. SQLite save
4. state update
5. DB risk update
6. SSE EVENT
7. AI queue
8. result

ثم:

`POST /webhook/opencanary`

يستدعي:

`ingest_event(raw_event)`

Replay أيضاً يستدعي **نفس function** داخل نفس Flask process.

لا تنشئ parser ثاني.

---

# 44. Replay Trigger

أنشئ أبسط presenter-controlled mechanism.

يمكن إضافة Route واضحة:

`POST /demo/replay/<int:event_number>`

بحيث:

1. يقرأ Event المحدد من `replay/events.json`.
2. يتحقق أن event number صالح.
3. يمرره إلى `ingest_event()`.
4. يعيد نفس نتيجة ingestion.

لا ترسل Replay مباشرة إلى SSE.

لا تخترع pipeline ثانية.

---

# 45. replay.py

اجعل `replay.py` مسؤولاً فقط عن:

* تحميل `events.json`
* validation الأساسية للملف
* جلب event حسب sequence/index
* عدم تعديل payload بطرق مختلفة عن Live

يمكن إنشاء functions مثل:

`load_replay_events()`

`get_replay_event(number)`

كلها مكتملة.

لا تجعل `replay.py` يحتوي State Machine ثانية.

---

# 46. events.json

أنشئ 3 Events فقط للسيناريو الأساسي.

كلها من نفس source.

Event #1:
Discovery
→ Web Service
→ يؤدي محلياً إلى 21.

Event #2:
نفس source
→ Service Probe
→ يؤدي إلى 48.

Event #3:
نفس source
→ sensitive target مثل `Admin System`
→ Access Attempt / Critical transition
→ يؤدي إلى 91.

استخدم canonical normalized input المعتمد فعلياً في Commits 1–5:

* event_type
* source
* target_service
* timestamp
* attempt_count
* previous_related_events
* current_risk_context

و`current_risk_context` يجب أن يطابق الـcanonical model الحالي بالكامل.

لا تستخدم Events لا تمر `normalize_event()`.

---

# 47. Replay Timing

لا تجعل Replay يشغل العرض كله تلقائياً.

Presenter هو من يشغل كل Event.

المخطط:

03:00 → Replay Event 1

04:00 → Replay Event 2

06:00 → Replay Event 3

لا تنشئ Timer يدير العرض 15 دقيقة تلقائياً.

---

# 48. Presenter Replay Controls

يمكن إضافة Presenter Controls صغيرة وغير مشتتة:

`EVENT 1`
`EVENT 2`
`EVENT 3`

كل Button يستدعي:

`POST /demo/replay/1`

مثلاً.

لا ترسل events من JavaScript نفسه.

JavaScript لا يحتوي replay payloads.

Payloads تبقى في:

`replay/events.json`

---

# 49. Replay + Telegram

Replay Event #3 يذهب:

same ingestion
→ AI Worker
→ Groq
→ severity CRITICAL
→ Telegram Queue
→ Telegram Worker

لا تستدع Telegram من Replay مباشرة.

---

# 50. Replay + Reset

بعد:

`RESET DEMO`

ثم Replay Event 1:

يجب أن تبدأ جولة جديدة نظيفة:

risk 21
timeline Discovery
new generation

أي AI/Telegram task قديمة:
discarded بسبب generation.

---

# 51. Commit 10 Tests

أضف:

`tests/test_replay.py`

اختبر:

1. events.json loads.
2. exactly expected demo events exist.
3. every replay event passes normalize_event().
4. all three share same source.
5. Event 3 targets sensitive service.
6. invalid replay event number → 404/400 مناسب.
7. replay endpoint invokes same `ingest_event()`.
8. Replay 1 creates SQLite evidence.
9. Replay 1 → risk 21.
10. Replay 2 → risk 48.
11. Replay 3 → risk 91.
12. Replay 3 → CRITICAL_INTRUSION.
13. SSE broadcast occurs.
14. AI queue gets tasks.
15. Replay does not call Groq synchronously.
16. Replay does not call Telegram synchronously.
17. Reset clears replay evidence/state.
18. old generation AI result remains rejected.
19. old generation Telegram task remains rejected.
20. Replay uses no separate parser/state machine.

ممنوع Internet في tests.

---

# 52. Full End-to-End Local Smoke Test

بعد Commit 10:

شغل Flask محلياً.

بدون Groq/Telegram الحقيقيين يمكن إجراء Local smoke path باستخدام controlled environment.

السيناريو:

RESET

→ NORMAL / 0

Replay Event 1

→ 21
→ UNDER_OBSERVATION
→ Discovery

Replay Event 2

→ 48
→ UNDER_OBSERVATION
→ Service Probe

Replay Event 3

→ 91
→ CRITICAL_INTRUSION
→ Escalation

ثم:

POST /contain

→ CONTAINED
→ Containment added

ثم:

POST /crime-scene

→ خمسة Evidence من SQLite

ثم:

POST /executive

→ EXECUTIVE

ثم:

RESET

→ NORMAL
→ 0
→ DB empty

لا تستخدم Fake Dashboard data.

---

# 53. Frontend Security Final Gate

قبل اعتماد Commit 10:

ابحث في:

`templates/`
`static/`

عن:

`innerHTML`
`outerHTML`
`insertAdjacentHTML`

يجب ألا تستخدم لعرض event data.

وابحث عن:

`http://`
`https://`

داخل HTML/CSS/JS.

يجب ألا توجد Runtime CDN dependencies.

استثناءات URLs داخل backend Telegram code ليست Frontend.

---

# 54. Telegram Security Final Gate

تأكد:

`TELEGRAM_BOT_TOKEN`

و:

`TELEGRAM_CHAT_ID`

لا يظهران في:

* index.html
* app.js
* style.css
* SSE payload
* Flask JSON response
* logs
* SQLite

---

# 55. ECharts Final Gate

تأكد:

`static/echarts.min.js`

هو local.

ولا يوجد:

`cdn.jsdelivr`
`unpkg`
أو external ECharts URL.

---

# 56. Anti-Laziness Scan النهائي

ابحث في كل production source الذي كتبته عن:

TODO
FIXME
PLACEHOLDER
NotImplementedError
Add code here
Implement later

وافحص:

`pass`

ممنوع implementation ناقص.

افحص أيضاً:

* fake Telegram result
* fake Replay AI result
* hard-coded Evidence
* hard-coded Dashboard events

---

# 57. Regression Gate

كل Tests القديمة 54 يجب أن تبقى ناجحة.

ثم Tests الجديدة.

شغل:

`python3 -m unittest discover -s tests -v`

المطلوب:

Failed = 0
Errors = 0
Skipped = 0

ثم:

`python3 -m compileall app.py db.py state.py ai_worker.py telegram_worker.py prompt.py replay.py tests`

---

# 58. Runtime Mode يبقى ثابتاً

لا تغير:

`debug=False`

ولا تغير:

`use_reloader=False`

لا تعيد Debug mode.

---

# 59. ENGINEERING_LOG Final Section

بعد Commit 10 أضف:

## Phase 2 Acceptance — Commits 6–10

### Status

### Commit 6 Telegram Verification

### Commit 7 SSE Dashboard Verification

### Commit 8 ECharts Verification

### Commit 9 Audio Verification

### Commit 10 Replay Verification

### Security Verification

### External Dependency Verification

### Test Results

### Compile Results

### Manual Browser Checks

### Remaining Deferred Work

لا تدّع Manual Browser Test إذا لم تنفذه.

---

# 60. Git Commit Messages

Commit 6:

`feat(telegram): add asynchronous Telegram transport`

Commit 7:

`feat(ui): add secure SSE dashboard shell`

Commit 8:

`feat(charts): add local ECharts security visualization`

Commit 9:

`feat(audio): add resilient critical Web Audio alert`

Commit 10:

`feat(replay): add shared-pipeline demo replay`

---

# 61. Definition of Done — Commits 6–10

لا تعتبر هذه المرحلة منتهية إلا إذا:

* Telegram Worker منفصل عن AI Worker.
* Telegram failure لا يؤثر على AI/Dashboard/SQLite.
* Telegram يستخدم `telegram_alert` نفسه.
* Telegram secrets في environment فقط.
* stale Telegram tasks لا ترسل.
* Telegram dedup يعمل.
* Reset يمسح dedup state.
* Dashboard Full Screen.
* لا Raw Logs كواجهة أساسية.
* SSE/EventSource يعمل.
* reload يستعيد current state.
* UI تتحرك قبل Groq.
* AI Executive Brief من structured result فقط.
* Event/AI strings لا تدخل DOM عبر HTML.
* ISOLATE THREAT لا يدعي Firewall.
* Crime Scene من SQLite.
* الخمسة Evidence فقط.
* Origin Observed First مستخدم.
* Executive Mode يخفي التفاصيل التقنية.
* ECharts هو Visualization library الوحيد.
* ECharts محلي.
* لا CDN.
* Network Map يحتوي Internet/Gateway/Web/File/Admin/Vault.
* Risk Gauge يعمل 0/21/48/91.
* Timeline يعمل.
* Attack Path يعمل.
* Web Audio Native فقط.
* الصوت يحتاج Arm user interaction.
* فشل الصوت لا يكسر العرض.
* Replay يحتوي 3 Events.
* Replay يستخدم نفس ingestion path.
* Replay لا يرسل للDashboard مباشرة.
* Replay لا يستدعي Telegram مباشرة.
* Replay Event 1 → 21.
* Replay Event 2 → 48.
* Replay Event 3 → 91.
* Replay Event 3 → CRITICAL.
* Reset يعيد الجولة للصفر.
* no React.
* no Node.
* no Redis.
* no Celery.
* no WebSocket.
* no Socket.IO.
* no extra DB.
* no placeholders.
* all tests pass.
* compileall passes.
* `ENGINEERING_LOG.md` محدث بعد كل Commit.

ابدأ الآن بـCommit 6 فقط.

بعد نجاح اختبارات Commit 6 وتوثيقه وإنشاء Commit، انتقل إلى Commit 7.

ولا تقفز مباشرة إلى Commit 10.


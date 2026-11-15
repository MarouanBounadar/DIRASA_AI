# 🎓 DIRASA AI (دراسة)

> **Plateforme Universitaire Intelligente : Transformez vos enregistrements d'amphi en cours PDF structurés, quiz QCM, flashcards et préparation aux examens.**  
> *100% Gratuit (Faboor) — Conçu pour les étudiants marocains.*

---

## 🇲🇦 بالدارجة المغربية : شنو هي DIRASA AI ؟

تطبيق لسطح المكتب (Windows) كيهنيك من روينة التسجيلات و الكورات الطويلة :
1. **كتعطيه تسجيل الحصة** : رابط BigBlueButton، YouTube، Google Drive، Zoom، أو ملف صوت/فيديو، أو كتسجل مباشرة بالميكرو ديال البيسي فوسط لافاك.
2. **(اختياري) كتعطيه ديابو الأستاذ (Slides PDF)** : الذكاء الاصطناعي كيدير دمج بين هضرة البروف فالميكرو و بين الكود و التعاريف لي فالديابو.
3. **التطبيق كيصاوب ليك تلقائياً :**
   - 📄 **Cours PDF أكاديمي** منظم بالفصول، التعاريف، القواعد، و الملاحظات لي كيركز عليها البروف.
   - 🖨️ **نسخة PDF إيكو** (أبيض وأسود بدون حبر زايد) صالحة للطباعة فالفوطوكوبي بأقل تكلفة.
   - 🎯 **20+ سؤال QCM تفاعلي** مع شرح الأجوبة.
   - 🧠 **20+ بطاقة Flashcard** مع إمكانية التصدير لبرنامج Anki.
   - 📝 **امتحان تجريبي موقوت على 20** مع تصحيح ذكي بالملاحظات.
   - 💬 **سول البروف (Sawel l'Prof)** : كتسولو بالصوت بالميكرو وكيجاوبك بالصوت وبالدارجة/الفرنسية.
   - ⚡ **ملخص شامل للمادة (Synthèse Express)** : وثيقة مركزة ليلة الامتحان فيها أهم القواعد و الفخاخ.
   - 📅 **جدول مراجعة ذكي (Spaced Repetition)** : كيحدد ليك شنو تراجع فـ J+1، J+3، J+7، J+14 باش متنساش.

---

## 🏗️ بنية المشروع (Project Structure)

```text
DIRASA/
├── app.py                      # واجهة التطبيق الرئيسية (CustomTkinter GUI)
├── ai_transcription.py         # معالجة الصوت و تحويله لكور عبر Gemini / Groq
├── downloader.py               # تحميل الفيديوهات و الصوت مع استئناف التحميل التلقائي
├── pdf_generator.py            # توليد ملفات PDF الأكاديمية و نسخة الإيكو
├── cheat_sheet_service.py      # توليد الملخصات السريعة للمادة (Synthèse Express)
├── slides_service.py           # استخراج وقراءة محتوى سلايدات البروف (pypdf)
├── spaced_repetition_service.py# خوارزمية التكرار المتباعد وجدولة المراجعة
├── voice_service.py            # التعرف على الصوت و نطق إجابات البروف (TTS)
├── library_service.py          # مكتبة الكورات المنظمة حسب المواد و الحصص
├── stats_service.py            # إحصائيات التمارين و نسبة النجاح
├── exam_service.py             # توليد الامتحانات التجريبية وتصحيحها
├── recorder.py                 # مسجل الصوت المباشر من ميكروفون الحاسوب
├── tools.py                    # أدوات التصدير لـ Anki / CSV
├── config.py                   # إعدادات التطبيق
├── config.example.json         # نموذج للإعدادات بدون مفاتيح خاصة
├── requirements.txt            # المكتبات البرمجية المطلوبة
├── run.bat                     # تشغيل سريع بنقرة واحدة (Python)
├── build_exe.bat               # سكريبت بناء ملف DIRASA_AI.exe المستقل
└── LISEZ-MOI_DARIJA.txt        # دليل الاستعمال السريع الموجه للطلبة
```

---

## 🚀 طريقة التشغيل (Quick Start)

### الطريقة الأولى : عبر الملف التنفيذي الجاهز (بدون بايثون)
1. نزل ملف `DIRASA_AI.zip` من خانة الـ Releases أو الرابط المباشر.
2. فك الضغط على المجلد بالكامل.
3. شغل `DIRASA_AI.exe`.

### الطريقة الثانية : للمطورين (Python 3.10+)
```bash
# 1. استنساخ المشروع
git clone https://github.com/MarouanBounadar/DIRASA_AI.git
cd DIRASA_AI

# 2. تثبيت المكتبات المطلوبة
pip install -r requirements.txt

# 3. تشغيل التطبيق
python app.py
```
*(أو اضغط مرتين على `run.bat` مباشرة).*

---

## 🔑 مفتاح Google Gemini المجاني (Free API Key)

التطبيق لا يتطلب أي اشتراك مدفوع ولا بطاقة بنكية :
1. ادخل إلى [Google AI Studio](https://aistudio.google.com/apikey).
2. سجل دخولك بحساب Gmail.
3. اضغط على **Create API Key**.
4. انسخ المفتاح، ثم ألصقه في خانة **"Paramètres & Clés"** داخل التطبيق واضغط **"Enregistrer"**.

---

## 🛡️ الحماية و الأمان (Security & Privacy)
- ملف `config.json` مسجل داخل `.gitignore` لضمان عدم رفع مفاتيح الـ API الشخصية إلى GitHub.
- كل البيانات، التسجيلات، و ملفات الـ PDF تخزن محلياً داخل جهاز الطالب في مجلد `exports/`.

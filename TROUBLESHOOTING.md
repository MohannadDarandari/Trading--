# 🛠️ استكشاف الأخطاء | Troubleshooting Guide

## 🔴 مشاكل شائعة وحلولها

---

### ❌ خطأ: "ModuleNotFoundError: No module named 'web3'"

**السبب:** المكتبات غير مثبتة

**الحل:**
```powershell
pip install -r requirements.txt
```

---

### ❌ خطأ: "PRIVATE_KEY not configured in .env"

**السبب:** ملف `.env` غير موجود أو فارغ

**الحل:**
```powershell
# انسخ ملف المثال
copy .env.example .env

# عدّله وأضف مفاتيحك
notepad .env
```

**تأكد من:**
- [x] الملف اسمه `.env` (مو `.env.txt`)
- [x] فيه `PRIVATE_KEY=your_key_here`
- [x] المفتاح من محفظة على شبكة Polygon

---

### ❌ خطأ: "No markets found" أو "API connection failed"

**السبب:** مشكلة في الاتصال بـ Polymarket API

**الحل 1:** تحقق من الإنترنت
```powershell
ping google.com
```

**الحل 2:** تحقق من RPC
```powershell
# في .env، استخدم RPC موثوق
RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
```

**الحل 3:** جرب RPC ثاني
```bash
# Alchemy
RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/demo

# Infura  
RPC_URL=https://polygon-mainnet.infura.io/v3/YOUR_KEY

# QuickNode
RPC_URL=https://YOUR_ENDPOINT.quiknode.pro/YOUR_KEY
```

---

### ❌ خطأ: "Failed to fetch market details"

**السبب:** Polymarket API بطيء أو معلق

**الحل:**
```powershell
# زيد الـ timeout في analyzer.py
# أو انتظر شوي وجرب مرة ثانية
```

**أو:**
```powershell
# قلل عدد الأسواق
python agent/trader.py --interval 90
```

---

### ❌ خطأ: "HTTPError: 429 Too Many Requests"

**السبب:** كثرت الطلبات للـ API

**الحل:**
```powershell
# في .env
STRATEGY=manual  # أقل طلبات

# أو زيد interval
python agent/trader.py --interval 120  # كل دقيقتين
```

---

### ❌ خطأ: "Insufficient funds"

**السبب:** ما فيه USDC في المحفظة

**الحل:**
1. تأكد أن المحفظة على شبكة **Polygon** (مو Ethereum!)
2. احصل على USDC:
   - Bridge من Ethereum: https://wallet.polygon.technology/
   - اشتري مباشرة: https://app.uniswap.org/
3. تأكد انت على الشبكة الصح:
   ```
   Network: Polygon
   Chain ID: 137
   ```

---

### ❌ خطأ: "Transaction failed" أو "Gas estimation failed"

**السبب:** مشكلة في Gas أو الشبكة

**الحل 1:** زيد Gas multiplier
```bash
# في .env
GAS_MULTIPLIER=1.5  # زيد الـ gas
```

**الحل 2:** تأكد من رصيد MATIC
```powershell
# لازم فيه MATIC للـ gas fees
python scripts/utils.py balance
```

**الحل 3:** انتظر وحاول مرة ثانية
```powershell
# الشبكة ممكن تكون مزدحمة
```

---

### ❌ خطأ: "KeyError" أو "IndexError"

**السبب:** بيانات السوق ناقصة أو غير متوقعة

**الحل:**
```powershell
# هذا error في الكود، جرب:
# 1. حدّث المكتبات
pip install --upgrade -r requirements.txt

# 2. جرب سوق ثاني
# 3. أو ابلّغ عن الخطأ
```

---

### ❌ البوت بطيء جداً

**السبب:** كثرة التحليلات أو RPC بطيء

**الحل:**
```bash
# في .env

# قلل عدد الأسواق
MAX_DAILY_TRADES=5

# زيد الـ interval
# في أمر التشغيل
python agent/trader.py --interval 120

# استخدم RPC أسرع
RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
```

---

### ❌ البوت يدخل صفقات غريبة

**السبب:** الثقة (confidence) منخفضة أو الاستراتيجية مو مناسبة

**الحل:**
```bash
# في .env

# زيد الحد الأدنى للثقة
MIN_CONFIDENCE=0.8  # 80% confidence

# قلل حجم الصفقات
MAX_POSITION_SIZE=20  # $20 max

# جرب استراتيجية ثانية
STRATEGY=manual  # أنت تقرر
```

---

### ❌ "Permission denied" عند الكتابة في `data/`

**السبب:** مشكلة في الصلاحيات

**الحل:**
```powershell
# Windows: شغل VS Code as Administrator
# أو تأكد من صلاحيات المجلد

# أو غير DATA_DIR في .env
DATA_DIR=C:/Users/YOUR_USER/Documents/trading_data
```

---

### ❌ الكود ما يشتغل على Python 3.11 أو 3.12

**السبب:** بعض المكتبات قد لا تدعم الإصدارات الجديدة

**الحل:**
```powershell
# استخدم Python 3.10
python --version  # تحقق من الإصدار

# ثبت Python 3.10 من python.org
```

---

### ❌ "SSL Certificate Error"

**السبب:** مشكلة في الاتصال المشفر

**الحل:**
```powershell
# Windows
pip install --upgrade certifi

# أو استخدم RPC مختلف
```

---

### ❌ البوت يتوقف فجأة

**الأسباب المحتملة:**
1. خطأ غير متوقع
2. نفذت الصفقات اليومية
3. مشكلة في الشبكة

**الحل:**
```powershell
# 1. شوف logs
cat data/logs/bot_YYYYMMDD.log

# 2. فعّل auto-restart
# في .env
AUTO_RESTART=true

# 3. شغل في screen/tmux (Linux) أو استخدم Windows Task Scheduler
```

---

### ❌ "DRY_RUN=true but transactions are being sent"

**السبب:** خطأ في القراءة من .env

**الحل:**
```bash
# تأكد من .env
DRY_RUN=true  # كله lowercase

# مو
DRY_RUN=True  # ✗
DRY_RUN=TRUE  # ✗
```

**أو شغل مع command:**
```powershell
python agent/trader.py --dry-run
```

---

### ❌ "Invalid private key format"

**السبب:** المفتاح الخاص غير صحيح

**الحل:**
```bash
# في .env

# ✓ صح (64 حرف hex)
PRIVATE_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef

# ✗ خطأ - فيه مسافات
PRIVATE_KEY= 0123...def  

# ✗ خطأ - ناقص
PRIVATE_KEY=0123456

# ✗ خطأ - فيه علامات
PRIVATE_KEY="0123..."
```

**احصل على المفتاح الصح:**
1. افتح MetaMask
2. Settings → Security & Privacy
3. Reveal Private Key
4. انسخه بالكامل (64 حرف)
5. الصقه بدون علامات تنصيص

---

## 🔍 أدوات التشخيص

### 1. تحقق من الإعداد الكامل
```powershell
python scripts/utils.py check
```

### 2. اختبر الاتصال بالـ API
```powershell
python scripts/utils.py markets
```

### 3. شوف رصيد المحفظة
```powershell
python scripts/utils.py balance
```

### 4. اختبر analyzer وحده
```powershell
python agent/analyzer.py
```

### 5. اختبر strategies وحدها
```powershell
python agent/strategies.py
```

### 6. شغل dry-run وراقب
```powershell
python agent/trader.py --dry-run --interval 30
```

---

## 📋 Checklist للتشخيص

عند مواجهة مشكلة، تحقق من:

- [ ] Python مثبت (3.10+)
- [ ] المكتبات مثبتة (`pip install -r requirements.txt`)
- [ ] ملف `.env` موجود وصحيح
- [ ] `PRIVATE_KEY` صحيح (64 حرف)
- [ ] `RPC_URL` يعمل
- [ ] الإنترنت متصل
- [ ] المحفظة فيها USDC + MATIC
- [ ] المحفظة على شبكة Polygon (Chain ID: 137)
- [ ] VPN موقوف (إذا كان يسبب مشاكل)
- [ ] Firewall/Antivirus ما يحجب Python

---

## 🆘 ما زال ما اشتغل؟

### خطوات متقدمة:

1. **حذف وإعادة التثبيت:**
```powershell
# احذف env
Remove-Item -Recurse -Force venv/

# أنشئ env جديد
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. **تحقق من versions:**
```powershell
python --version
pip list
```

3. **شغل في virtual environment:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python agent/trader.py --dry-run
```

4. **شوف logs بالتفصيل:**
```powershell
# في .env
LOG_LEVEL=DEBUG
```

---

## 📞 طلب المساعدة

إذا ما زال فيه مشكلة، اجمع:

1. رسالة الخطأ الكاملة
2. نسخة Python (`python --version`)
3. نسخة المكتبات (`pip list`)
4. محتوى `.env` (⚠️ احذف PRIVATE_KEY قبل المشاركة!)
5. الخطوات اللي سويتها

---

**معظم المشاكل تحل بـ:**
1. ✅ إعادة تثبيت المكتبات
2. ✅ التأكد من `.env` صحيح
3. ✅ استخدام Python 3.10
4. ✅ التحقق من الاتصال بالشبكة

**حظ موفق! 🚀**

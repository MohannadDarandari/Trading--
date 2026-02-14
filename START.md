# ⚡ Quick Start - تشغيل سريع في 5 دقائق

## 🚀 للمستعجلين

### خطوة 1: ثبت المتطلبات (دقيقة واحدة)

```powershell
pip install -r requirements.txt
```

### خطوة 2: أعد ملف الإعدادات (دقيقة واحدة)

```powershell
copy .env.example .env
notepad .env
```

**عدّل في `.env`:**
- ضع `PRIVATE_KEY` (من محفظة جديدة للتجربة!)
- ضع `RPC_URL` (احصل عليه مجاناً من [Alchemy](https://www.alchemy.com/))

### خطوة 3: تحقق من الإعداد (30 ثانية)

```powershell
python scripts/utils.py check
```

### خطوة 4: شوف الأسواق (30 ثانية)

```powershell
python scripts/utils.py markets
```

### خطوة 5: شغل البوت! (دقيقتين)

```powershell
# وضع آمن - بدون تداول حقيقي
python agent/trader.py --strategy copy_whales --dry-run
```

---

## 🎯 أوامر سريعة مفيدة

```powershell
# مراقب الأسواق live
python scripts/monitor.py

# ابحث عن فرص
python scripts/utils.py opportunities

# شوف رصيد محفظتك
python scripts/utils.py balance

# اختبر استراتيجية
python scripts/utils.py test-strategy --strategy arbitrage

# شغل بوت حقيقي (⚠️ فلوس حقيقية!)
python agent/trader.py --strategy arbitrage
```

---

## ⚙️ تخصيص سريع

عدّل `.env` للتحكم في البوت:

```bash
# حجم الصفقات
MAX_POSITION_SIZE=50        # دولار

# عدد الصفقات اليومية
MAX_DAILY_TRADES=10

# الاستراتيجية
STRATEGY=copy_whales        # copy_whales | arbitrage | momentum | manual

# الأمان
DRY_RUN=true               # true = تجريبي | false = حقيقي!

# الحد الأدنى للثقة
MIN_CONFIDENCE=0.7          # 70%

# إدارة المخاطر
STOP_LOSS=0.2              # 20% خسارة
TAKE_PROFIT=0.5            # 50% ربح
```

---

## 🆘 مشاكل شائعة

### المكتبات ما تثبت؟
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### ملف .env مو موجود؟
```powershell
copy .env.example .env
```

### PRIVATE_KEY not configured؟
```powershell
notepad .env
# أضف PRIVATE_KEY=your_key_here
```

### No markets found؟
```bash
# في .env، استخدم Alchemy RPC
RPC_URL=https://polygon-mainnet.g.alchemy.com/v2/YOUR_KEY
```

---

## 📚 مراجع سريعة

- 📖 دليل كامل بالعربي: [ARABIC_GUIDE.md](ARABIC_GUIDE.md)
- 🚀 دليل البدء: [QUICKSTART.md](QUICKSTART.md)
- 🔒 دليل الأمان: [SECURITY.md](SECURITY.md)
- 🛠️ حل المشاكل: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## ⚠️ تذكّر دائماً

```
✅ ابدأ بوضع --dry-run
✅ استخدم مبالغ صغيرة ($10-$50)
✅ استخدم محفظة منفصلة للتداول

❌ لا تستخدم محفظتك الرئيسية
❌ لا تتوقع أرباح مضمونة
❌ لا تضع كل أموالك
```

---

**🎉 يلا ابدأ! Good luck!**

```powershell
python agent/trader.py --strategy copy_whales --dry-run
```

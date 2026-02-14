# 🚀 دليل البدء السريع | Quick Start Guide

## خطوات التشغيل السريعة | Quick Setup Steps

### 1️⃣ تثبيت المتطلبات | Install Dependencies

```powershell
# في VS Code Terminal
pip install -r requirements.txt
```

### 2️⃣ إعداد ملف البيئة | Setup Environment

```powershell
# انسخ ملف المثال | Copy example file
copy .env.example .env

# عدّل .env وأضف مفاتيحك | Edit .env and add your keys
notepad .env
```

### 3️⃣ احصل على المفاتيح المطلوبة | Get Required Keys

#### 🔹 Polygon RPC (مجاني | Free):
1. اذهب إلى → https://www.alchemy.com/
2. أنشئ حساب مجاني
3. أنشئ App جديد على شبكة **Polygon**
4. انسخ الـ **HTTPS URL**
5. ضعه في `.env` تحت `RPC_URL`

#### 🔹 Wallet Private Key:
⚠️ **استخدم محفظة جديدة للتجربة - لا تستخدم محفظتك الرئيسية!**

1. أنشئ محفظة جديدة في **MetaMask**
2. اذهب لـ: Settings → Security & Privacy → Reveal Private Key
3. انسخ المفتاح وضعه في `.env` تحت `PRIVATE_KEY`
4. احصل على USDC على شبكة Polygon (bridge من Ethereum أو اشتري مباشرة)

### 4️⃣ تشغيل البوت | Run the Bot

#### 🧪 وضع التجريب (موصى به للبداية):
```powershell
python agent/trader.py --strategy copy_whales --dry-run
```

#### 🔴 تداول حقيقي (على مسؤوليتك!):
```powershell
python agent/trader.py --strategy arbitrage
```

---

## 🎯 الاستراتيجيات المتاحة | Available Strategies

### 1. Copy Whales (نسخ الحيتان) 🐋
- يتتبع محافظ كبيرة ويقلد صفقاتهم
- جيد للمبتدئين

```powershell
python agent/trader.py --strategy copy_whales --dry-run
```

### 2. Arbitrage (المراجحة) ⚖️
- يبحث عن أسواق مسعرة خطأ
- يحتاج سرعة تنفيذ

```powershell
python agent/trader.py --strategy arbitrage --dry-run
```

### 3. Momentum (الزخم) 📈
- يتبع الأسواق ذات الحجم الكبير
- متوسط المخاطر

```powershell
python agent/trader.py --strategy momentum --dry-run
```

### 4. Manual (يدوي) 🎮
- البوت يعطيك توصيات فقط
- أنت تقرر متى تدخل

```powershell
python agent/trader.py --strategy manual
```

---

## 🧪 تجربة البوت بدون مخاطرة | Test Without Risk

### مثال 1: تحليل الأسواق فقط
```powershell
# اختبر analyzer وحده
python agent/analyzer.py
```

### مثال 2: اختبر الاستراتيجيات
```powershell
# اختبر strategies
python agent/strategies.py
```

### مثال 3: شغل البوت في وضع dry-run
```powershell
# البوت يعمل لكن بدون تداول حقيقي
python agent/trader.py --strategy copy_whales --dry-run --interval 30
```

---

## ⚙️ تخصيص الإعدادات | Customize Settings

عدّل ملف `.env`:

```bash
# حجم أقصى للصفقة (دولار)
MAX_POSITION_SIZE=50

# عدد صفقات يومياً
MAX_DAILY_TRADES=10

# وقف الخسارة (20% = 0.2)
STOP_LOSS=0.2

# جني الأرباح (50% = 0.5)
TAKE_PROFIT=0.5

# الحد الأدنى للثقة (70% = 0.7)
MIN_CONFIDENCE=0.7

# وضع التجريب
DRY_RUN=true
```

---

## 🐋 إضافة محافظ الحيتان | Add Whale Wallets

في `.env`:

```bash
# أضف عناوين محافظ الحيتان (افصل بفواصل)
WHALE_WALLETS=0x1234567890...,0xabcdef1234...

# الحد الأدنى لحجم صفقة الحوت
MIN_WHALE_TRADE_SIZE=100
```

كيف تجد الحيتان؟
1. اذهب لـ Polymarket
2. افتح سوق نشط
3. شوف Order Book
4. انسخ عناوين المحافظ الكبيرة

---

## 📊 مراقبة الأداء | Monitor Performance

### سجلات الصفقات:
```powershell
# شوف سجلات اليوم
cat data/trades/trades_20260212.json
```

### الإحصائيات:
- البوت يعرض إحصائيات كل دورة
- يحفظ كل الصفقات في `data/trades/`
- يحفظ logs في `data/logs/`

---

## 🛑 إيقاف البوت | Stop the Bot

```
Ctrl + C
```

---

## ⚠️ تحذيرات مهمة | Important Warnings

### ✅ افعل:
- ✅ ابدأ في وضع `--dry-run`
- ✅ استخدم مبالغ صغيرة ($10-$50)
- ✅ استخدم محفظة منفصلة
- ✅ راقب البوت باستمرار
- ✅ اقرأ الكود وافهمه

### ❌ لا تفعل:
- ❌ لا تستخدم كل أموالك
- ❌ لا تترك البوت بدون مراقبة
- ❌ لا تشارك مفاتيحك الخاصة
- ❌ لا تتوقع أرباح مضمونة
- ❌ لا تستخدم محفظتك الرئيسية

---

## 🆘 حل المشاكل | Troubleshooting

### مشكلة: "PRIVATE_KEY not configured"
**الحل:**
```powershell
# تأكد من نسخ .env.example إلى .env
copy .env.example .env
notepad .env
# أضف مفاتيحك الحقيقية
```

### مشكلة: "No markets found"
**الحل:**
- تأكد من اتصال الإنترنت
- تأكد من RPC_URL صحيح
- حاول استخدام Alchemy RPC

### مشكلة: "Module not found"
**الحل:**
```powershell
pip install -r requirements.txt
```

### مشكلة: البوت بطيء
**الحل:**
```powershell
# قلل interval (بالثواني)
python agent/trader.py --interval 30
```

---

## 📚 موارد إضافية | Additional Resources

- [Polymarket Docs](https://docs.polymarket.com)
- [py-clob-client](https://github.com/Polymarket/py-clob-client)
- [Alchemy](https://www.alchemy.com/)
- [MetaMask](https://metamask.io/)

---

## 💬 دعم | Support

إذا واجهت مشاكل:
1. راجع هذا الدليل
2. تأكد من `.env` صحيح
3. شوف `data/logs/` للأخطاء
4. جرب وضع `--dry-run` أولاً

---

**بالتوفيق! 🚀**

*تذكر: هذا للتعلم. ابدأ صغير، وتعلم، ثم قرر.*

# 🎨 DASHBOARD GUIDE - دليل الواجهة

## 🚀 كيف تستخدم الواجهة (Dashboard)

### تشغيل الواجهة:

```powershell
# بعد التثبيت، شغل:
streamlit run dashboard.py
```

ستفتح صفحة في المتصفح على: `http://localhost:8501`

---

## 📱 الواجهة والمميزات

### 1️⃣ **الصفحة الرئيسية (Dashboard)**
```
📊 تعرض:
- إحصائيات الأداء
- الصفقات اليوم
- نسبة النجاح
- الربح/الخسارة

🎯 أزرار سريعة:
- Scan Markets
- Find Opportunities
- View Reports
- Settings
```

### 2️⃣ **Market Scanner (ماسح الأسواق)**
```
🔍 المميزات:
- عرض الأسواق النشطة
- فلترة حسب الحجم
- تحليل تفصيلي لكل سوق
- معلومات الأسعار والسيولة

📊 معلومات كل سوق:
- YES Price
- Trading Volume
- Liquidity
- تحليل متقدم بضغطة زر
```

### 3️⃣ **Opportunities (الفرص)**
```
💎 البحث عن أفضل الفرص:
- فلترة حسب نسبة الثقة
- اختيار الاستراتيجية
- تفاصيل كل فرصة
- Scores ومعلومات التحليل

🎯 معلومات الفرصة:
- Confidence Level
- Opportunity Type
- Expected Return
- Risk Level
- Recommended Action
```

### 4️⃣ **Settings (الإعدادات)**
```
⚙️ تحكم كامل:
- Max Position Size
- Max Daily Trades
- Stop Loss %
- Take Profit %
- Min Confidence %
- Dry Run Mode

💾 حفظ فوري للإعدادات
```

---

## 🎨 المميزات البصرية

### 🌈 **تصميم احترافي**
- ألوان gradient جميلة
- Cards منظمة
- Responsive design
- سهل الاستخدام

### 📊 **Charts & Graphs** (قريباً)
- Performance charts
- Market trends
- Portfolio distribution
- P&L graphs

### 📱 **Mobile Friendly**
- يعمل على الجوال
- تصميم متجاوب
- سهل التصفح

---

## ⚡ أوامر سريعة

### تشغيل Dashboard:
```powershell
streamlit run dashboard.py
```

### تشغيل في الخلفية:
```powershell
Start-Process powershell -ArgumentList "streamlit run dashboard.py" -WindowStyle Hidden
```

### إيقاف Dashboard:
```
اضغط Ctrl+C في PowerShell
```

---

## 🔧 تخصيص Dashboard

يمكنك تعديل ملف `dashboard.py` لإضافة:
- ألوان مخصصة
- صفحات جديدة
- widgets إضافية
- charts متقدمة

---

## 📞 مشاكل شائعة

### Dashboard ما يفتح؟
```powershell
# تأكد من تثبيت streamlit
pip install streamlit plotly

# جرب
streamlit run dashboard.py
```

### الصفحة فاضية؟
```
- تأكد من ملف .env صحيح
- تأكد من Python يشتغل
- شوف console للأخطاء
```

### بطء في التحميل؟
```
- الاتصال بالإنترنت
- Polymarket API connection
- حجم البيانات المطلوبة
```

---

## 🎯 الميزات القادمة

```
🔜 Coming Soon:
- ✨ Live trading من الواجهة
- 📊 Advanced charts
- 📱 Mobile app
- 🔔 Push notifications
- 💬 Telegram integration
- 🤖 Auto-trading toggles
- 📈 Backtesting interface
- 🎨 Theme customization
```

---

**🎨 استمتع بالواجهة الجميلة!**

*Dashboard v1.0 - Built with Streamlit*

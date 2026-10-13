# اجرای دماوند در Windows و PyCharm

پوشهٔ اصلی پروژه و شاخهٔ `feature/admin-panel-v1` را باز کنید. Python 3.12+ و Node.js 22.18+ لازم‌اند. Docker لازم نیست.

در ترمینال PowerShell ریشهٔ پروژه:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env.local
cd backend
..\.venv\Scripts\python.exe manage.py migrate
..\.venv\Scripts\python.exe manage.py createsuperuser
```

فایل تنظیم موجود را دوباره کپی نکنید. برای نصب یا migrate از Python همان محیط مجازی استفاده کنید. پایگاه دادهٔ موجود را پاک نکنید؛ قبل از به‌روزرسانی از آن نسخهٔ پشتیبان بگیرید. migration فاز دوم مشتریان قبلی را حفظ می‌کند و هیچ رمز یا ظرفیت ساختگی برای آن‌ها ایجاد نمی‌کند.

در **Settings → Python Interpreter** مسیر `.venv\Scripts\python.exe` را انتخاب کنید. در **Run → Edit Configurations** یک اجرای Python بسازید: Script برابر `backend\manage.py`، Parameters برابر `runserver 127.0.0.1:8000` و Working directory برابر پوشهٔ `backend`.

برای رابط، در ترمینال دیگری از ریشه:

```powershell
cd frontend
npm ci
npm run dev
```

می‌توانید پیکربندی npm با `frontend\package.json` و اسکریپت `dev` بسازید. هر دو سرویس باید هم‌زمان اجرا باشند؛ اجرای Django به‌تنهایی رابط Next.js را اجرا نمی‌کند. مقدار `DJANGO_API_ORIGIN` برابر `http://127.0.0.1:8000` و `FRONTEND_URL` برابر `http://127.0.0.1:3000/` باشد. در توسعه HTTP، `DEBUG=true` را از نمونه حفظ کنید. همیشه از یک میزبان ثابت استفاده کنید.

پنل داخلی را در `http://127.0.0.1:3000/login` باز کنید. برای نمونهٔ آزمایشی، «مجموعه جدید» با نام آفتاب، نشانی **aftab**، ظرفیت مثبت و تاریخ‌های سرویس بسازید. راه‌اندازی هم‌زمان پرتال را انتخاب کنید، نام کاربری **aftab.manager** و رمز قوی خودتان را تعیین کنید. نشانی ثابت است و پس از ثبت تغییر نمی‌کند. برای مشتری قدیمی، جزئیات مشتری ← تنظیم دسترسی پرتال را باز کنید و ظرفیت و اعتبارنامه را ثبت کنید.

ورود مجموعه: `http://127.0.0.1:3000/aftab`؛ داشبورد پس از ورود: `http://127.0.0.1:3000/aftab/dashboard`. حساب داخلی مجوز ورود به داشبورد مجموعه را ندارد؛ با اعتبارنامهٔ پرتال وارد شوید. هر دو نشست می‌توانند در یک مرورگر فعال باشند. انقضا تنها هشدار است؛ خروج از پرتال، نشست پنل مرکزی را نمی‌بندد.

برای کنترل کیفیت، دستورات بخش «اجرای کنترل‌های کیفیت» [README.md](README.md) را اجرا کنید. آزمون مرورگر از پایگاه دادهٔ موقت استفاده می‌کند و نیازمند build رابط و پورت‌های آزاد ۸۰۰۰/۳۰۰۰ است. دادهٔ توسعه جایگزین نمی‌شود.

# PhD & Predoc Radar

ایجنت روزانه که آگهی‌های **PhD / Predoc / RA / Doctoral researcher** در **اروپا** را از چند سایت جمع می‌کند، با حوزه‌های تو و زهرا فیلتر می‌کند و یک **صفحه‌ی وب** می‌سازد که روی آیپد/گوشی/لپ‌تاپ باز می‌شود. بدون API و بدون هزینه. **لپ‌تاپ لازم نیست**: روی سرورهای GitHub (Actions) هر روز خودش اجرا می‌شود.

## ⚠️ چه چیزی تست شده و چه چیزی نه
- فیلتر، پارسرها و کل پایپ‌لاین: ۳۹ تست آفلاین (`python -m unittest discover -s tests`). رابط صفحه در مرورگر واقعی (اندازه‌ی آیپد و گوشی) آزمایش شده.
- **اسکرپ زنده از سرور هنوز تست نشده** (محیط ساخت اینترنت نداشت). ساختار PhDScanner و AcademicTransfer را در مرورگر واقعی دیدم، ولی بقیه‌ی منابع را از روی توصیف صفحه‌هایشان نوشته‌ام. **اولین اجرای GitHub را باید نگاه کنیم** (پایین‌ترین بخش صفحه: «Source health» هر منبع را OK/PROBLEM نشان می‌دهد).

## راه‌اندازی یک‌باره (از آیپد، حدود ۱۰ دقیقه)
1. در GitHub یک ریپوی **خالی** به نام `phd-radar` بساز (New repository → Public → بدون README). اسم را به من بگو تا کد را داخلش بگذارم (یا خودت zip را آپلود کن).
2. ریپو ← **Settings ← Pages ← Source: GitHub Actions**.
3. ریپو ← **Actions ← daily ← Run workflow** (تیک `deep` را بزن؛ اولین اجرا چند ده دقیقه طول می‌کشد).
4. صفحه در `https://<username>.github.io/phd-radar/` است. در Safari: Share ← **Add to Home Screen** تا مثل اپ باز شود.

> ریپوی Public یعنی صفحه و فایل‌های تنظیمات برای همه قابل دیدن است (آگهی‌های عمومی + حوزه‌های پژوهشی شما). اگر نمی‌خواهی، در `config/easy.yaml` ایمیل نگذار. (Pages روی ریپوی Private نیاز به حساب Pro دارد.)

## هر روز چه می‌شود؟
- خودکار هر روز ساعت **۰۹:۰۰ تهران** (cron داخل `.github/workflows/daily.yml`، به وقت UTC). ممکن است GitHub چند دقیقه تا یکی دو ساعت دیر اجرا کند.
- دستی: Actions ← daily ← **Run workflow** — یا دکمه‌ی «Run update now» پایین خود صفحه (بعد از پر کردن `github_repo` در `config/easy.yaml`).
- هر اجرا خودش زمان‌بندی را زنده نگه می‌دارد (GitHub زمان‌بندی‌های بی‌فعالیتِ ۶۰ روزه را متوقف می‌کند).

## خود صفحه
- تب‌ها: **To review / ⭐ Saved / ✓ Applied / Hidden** — روی هر آگهی Save / Applied / Hide بزن. علامت‌ها فقط داخل همان مرورگر ذخیره می‌شوند؛ برای انتقال بین آیپد و گوشی: Backup → Restore (پایین صفحه).
- فیلتر: Both/Shayan/Zahra، Strong یا +Adjacent، نوع موقعیت، فقط اروپای غربی، فقط جدیدها، جستجو، مرتب‌سازی بر اساس ددلاین.
- نوار سبز = جدید؛ نوار نارنجی = کمتر از ۱۴ روز تا ددلاین.

## تنظیم ساده (فقط `config/easy.yaml`)
از آیپد: GitHub ← فایل را باز کن ← آیکون مداد ← تغییر ← Commit. می‌توانی کلمه‌ی اضافه (`my_keywords`)، کلمه‌ی ممنوع در عنوان (`block_title_words`) و سازمان ممنوع (`block_orgs`) بدهی. تغییرات از اجرای بعدی اعمال می‌شود.
تنظیمات پیشرفته‌تر: `config/profiles.yaml` (حوزه‌ها)، `config/sources.yaml` (منابع)، `config/settings.yaml`، `config/geography.yaml`.

## منابع
EURAXESS · INOMICS (PhD، RA، researcher) · jobs.ac.uk · **Academic Positions** (کلی + ۸ صفحه‌ی حوزه‌ای) · **AcademicTransfer** (هلند؛ از sitemap رسمی چون API‌اش کلید می‌خواهد؛ طبق robots.txt بین درخواست‌ها ۱۰ ثانیه صبر می‌کند، پس اولین اجرا کند است) · **PhDScanner** (از همان JSON که خود سایت استفاده می‌کند و robots.txt اجازه داده) · PREDOC.org (آگهی‌های غیراروپایی حذف می‌شوند).
منبع جدید: یک بلوک به `config/sources.yaml` اضافه کن (نمونه‌ها داخل فایل).

## چطور فیلتر می‌کند
1. **نوع**: فقط PhD / Predoc / RA / Doctoral researcher (چندزبانه). Postdoc/Professor/Summer school حذف.
2. **جغرافیا**: فقط اروپا؛ غربی امتیاز بیشتر (UK هم غربی حساب شده). مکان نامشخص حذف نمی‌شود.
3. **حوزه**: ۱۲ حوزه از CVها. **Strong** = حوزه‌ی مشخص؛ **Adjacent** = اقتصادی بدون تطابق دقیق؛ **Rejected** = مالی/حسابداری/بازاریابی/غیراقتصادی (همه با دلیل در `rejected.csv`، تا چیز مهمی گم نشود).
4. زبان و GRE بررسی نمی‌شود.

## اجرا روی کامپیوتر (اختیاری)
```
pip install -r requirements.txt
python -m agent check      # سلامت منابع
python -m agent run --deep # اجرای اول
python -m agent run        # روزانه  (یا run_daily.bat / run_daily.sh)
python -m agent rescore    # اعمال تغییر تنظیمات بدون دانلود مجدد
python tests/make_demo.py  # صفحه‌ی نمونه با داده‌ی ساختگی در output_demo/
```

## محدودیت‌ها
- پوشش «همه‌ی سایت‌های هر کشور» با منابع تجمیعی تقریب خوبی است ولی کامل نیست؛ سایت ملی/دپارتمانی را به `sources.yaml` اضافه کن.
- فیلتر قاعده‌محور است و گاهی خطا می‌کند (برای همین Adjacent و rejected.csv هست). نقطه‌ی اتصال LLM در آینده: `agent/logic.py: evaluate()`.
- سایت‌ها ممکن است ساختار را عوض کنند؛ جدول Source health و `python -m agent check` همین را نشان می‌دهند.

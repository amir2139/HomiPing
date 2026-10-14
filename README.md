# HomiPing

[فارسی](#فارسی) · [English](#english)

---

## فارسی

ثبت کیفیت و قطعی اینترنت. فقط با کتابخانه‌ی استاندارد پایتون ۳، روی ویندوز و لینوکس؛ نیازی به نصب بسته نیست (فقط دستور `ping` سیستم لازم است).

### نصب
```bash
git clone https://github.com/amir2139/HomiPing.git
cd HomiPing
```

### اجرا
```bash
# ثبت داده، هر ۳۰ ثانیه (Ctrl+C برای توقف)
python homiping.py run

# تغییر فاصله و هدف‌ها
python homiping.py run -i 10 --domestic aparat.com digikala.com --foreign 1.1.1.1 8.8.8.8

# ساخت گزارش HTML تکی (آفلاین) از ۱ روز اخیر
python homiping.py report -d 1 -o report.html
```
- هر دور، به هر هدف `-c` بسته (پیش‌فرض ۳) ping زده می‌شود؛ میانگین تأخیر و درصد loss در `homiping-data/YYYY-MM-DD.csv` ثبت می‌شود.
- قطعی یعنی همه‌ی هدف‌های یک گروه جواب ندهند. شروع و پایان در `homiping-data/outages.csv` جدا ثبت می‌شود.
- گزارش شامل نمودار SVG تأخیر، جدول قطعی‌ها و مقایسه‌ی داخلی/خارجی است (فارسی و راست‌چین، بدون CDN).
- مسیر داده با `--data-dir` تغییر می‌کند.

### نمونه‌ی خروجی
```
14:02:11 domestic aparat.com        18.3 ms  loss 0%
14:02:11 domestic digikala.com      21.0 ms  loss 0%
14:02:11 foreign  1.1.1.1           --       loss 100%
14:02:11 foreign  google.com        --       loss 100%
*** foreign: outage STARTED
```
```
timestamp,group,target,avg_ms,loss_pct
2026-10-14 14:02:11,domestic,aparat.com,18.3,0
```
```
timestamp,group,event
2026-10-14 14:02:11,foreign,start
2026-10-14 14:09:41,foreign,end
```

---

## English

Log internet quality and outages. Pure Python 3 standard library, works on Windows and Linux; no packages needed (only the system `ping` command).

### Install
```bash
git clone https://github.com/amir2139/HomiPing.git
cd HomiPing
```

### Usage
```bash
# log every 30 s (Ctrl+C to stop)
python homiping.py run

# custom interval and targets
python homiping.py run -i 10 --domestic aparat.com digikala.com --foreign 1.1.1.1 8.8.8.8

# build a single-file offline HTML report for the last day
python homiping.py report -d 1 -o report.html
```
- Each round sends `-c` pings (default 3) to every target; average latency and loss % go to `homiping-data/YYYY-MM-DD.csv`.
- An outage means every target of a group failed. Start and end are logged separately in `homiping-data/outages.csv`.
- The report has an SVG latency chart, an outage table and a domestic vs. foreign comparison (Persian, RTL, no CDN).
- Change the data folder with `--data-dir`.

### Sample output
See the Persian section above: console lines, the daily CSV and `outages.csv`.

## License
See [LICENSE](LICENSE).

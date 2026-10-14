#!/usr/bin/env python3
"""HomiPing - log internet quality and outages. Standard library only."""
import argparse
import csv
import html
import os
import platform
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

GROUPS = {
    "domestic": ["aparat.com", "digikala.com"],
    "foreign": ["1.1.1.1", "google.com"],
}
GROUP_FA = {"domestic": "داخلی", "foreign": "خارجی"}
COLORS = {"domestic": "#2e8b57", "foreign": "#1f6fd1"}
IS_WIN = platform.system() == "Windows"
TIME_RE = re.compile(r"(?:time|زمان)\s*([=<])\s*([\d.]+)\s*ms", re.I)
FMT = "%Y-%m-%d %H:%M:%S"


def ping(host, count, timeout):
    """Return (avg_ms or None, loss_percent) for `count` pings to host."""
    if IS_WIN:
        cmd = ["ping", "-n", str(count), "-w", str(int(timeout * 1000)), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", str(int(max(1, timeout))), host]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             timeout=count * (timeout + 2) + 5,
                             errors="replace").stdout
    except (subprocess.TimeoutExpired, OSError):
        return None, 100.0
    times = []
    for sign, val in TIME_RE.findall(out):
        times.append(0.5 if sign == "<" else float(val))
    loss = 100.0 * (count - len(times)) / count
    return (sum(times) / len(times) if times else None), loss


def append_row(path, header, row):
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(header)
        w.writerow(row)


def last_states(events_path):
    state = {}
    if os.path.exists(events_path):
        with open(events_path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                state[r["group"]] = r["event"] == "start"
    return state


def cmd_run(a):
    os.makedirs(a.data_dir, exist_ok=True)
    events = os.path.join(a.data_dir, "outages.csv")
    groups = {"domestic": a.domestic, "foreign": a.foreign}
    down = last_states(events)
    rounds = 0
    print(f"HomiPing: every {a.interval}s, data in {a.data_dir} (Ctrl+C to stop)")
    try:
        while True:
            started = time.time()
            now = datetime.now()
            jobs = [(g, t) for g, ts in groups.items() for t in ts]
            with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
                res = list(ex.map(lambda j: ping(j[1], a.count, a.timeout), jobs))
            day = os.path.join(a.data_dir, now.strftime("%Y-%m-%d") + ".csv")
            alive = {g: False for g in groups}
            for (g, t), (avg, loss) in zip(jobs, res):
                append_row(day, ["timestamp", "group", "target", "avg_ms", "loss_pct"],
                           [now.strftime(FMT), g, t,
                            "" if avg is None else f"{avg:.1f}", f"{loss:.0f}"])
                if loss < 100:
                    alive[g] = True
                print(f"{now:%H:%M:%S} {g:8} {t:16} "
                      f"{'--' if avg is None else f'{avg:6.1f} ms'}  loss {loss:.0f}%")
            for g in groups:
                is_down = not alive[g]
                if is_down != down.get(g, False):
                    append_row(events, ["timestamp", "group", "event"],
                               [now.strftime(FMT), g, "start" if is_down else "end"])
                    print(f"*** {g}: outage {'STARTED' if is_down else 'ENDED'}")
                    down[g] = is_down
            rounds += 1
            if a.rounds and rounds >= a.rounds:
                break
            time.sleep(max(0, a.interval - (time.time() - started)))
    except KeyboardInterrupt:
        print("stopped")


# ---------------------------------------------------------------- report
def load(data_dir, since):
    samples = []  # (datetime, group, target, avg, loss)
    if os.path.isdir(data_dir):
        for name in sorted(os.listdir(data_dir)):
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.csv", name):
                continue
            with open(os.path.join(data_dir, name), newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    t = datetime.strptime(r["timestamp"], FMT)
                    if t >= since:
                        samples.append((t, r["group"], r["target"],
                                        float(r["avg_ms"]) if r["avg_ms"] else None,
                                        float(r["loss_pct"])))
    outages, open_ = [], {}  # (group, start, end or None)
    ep = os.path.join(data_dir, "outages.csv")
    if os.path.exists(ep):
        with open(ep, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                t = datetime.strptime(r["timestamp"], FMT)
                if r["event"] == "start":
                    open_[r["group"]] = t
                elif r["group"] in open_:
                    s = open_.pop(r["group"])
                    if t >= since:
                        outages.append((r["group"], s, t))
    outages += [(g, s, None) for g, s in open_.items()]
    outages.sort(key=lambda o: o[1])
    return samples, outages


def fmt_dur(sec):
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}س {m}د {s}ث" if h else (f"{m}د {s}ث" if m else f"{s}ث")


def chart(series, width=900, height=300):
    """series: {group: [(datetime, ms)]} -> SVG string."""
    pts = [p for s in series.values() for p in s]
    if not pts:
        return "<p>داده‌ای برای نمودار نیست.</p>"
    l, r, t, b = 55, 15, 15, 35
    t0, t1 = min(p[0] for p in pts), max(p[0] for p in pts)
    span = max((t1 - t0).total_seconds(), 1)
    ymax = max(p[1] for p in pts) * 1.1 or 1
    X = lambda d: l + (d - t0).total_seconds() / span * (width - l - r)
    Y = lambda v: t + (1 - v / ymax) * (height - t - b)
    o = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
         f'style="width:100%;max-width:{width}px;direction:ltr">']
    for i in range(5):
        v = ymax * i / 4
        o.append(f'<line x1="{l}" x2="{width - r}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#ddd"/>'
                 f'<text x="{l - 6}" y="{Y(v) + 4:.1f}" text-anchor="end" font-size="11">{v:.0f}</text>')
    for i in range(5):
        d = t0 + timedelta(seconds=span * i / 4)
        o.append(f'<text x="{X(d):.1f}" y="{height - 12}" text-anchor="middle" font-size="11">'
                 f'{d:%m-%d %H:%M}</text>')
    o.append(f'<text x="12" y="{t + 8}" font-size="11">ms</text>')
    for g, s in series.items():
        if s:
            d = " ".join(f"{X(a):.1f},{Y(v):.1f}" for a, v in s)
            o.append(f'<polyline points="{d}" fill="none" stroke="{COLORS.get(g, "#888")}" '
                     f'stroke-width="1.5"/>')
    o.append("</svg>")
    return "".join(o)


def cmd_report(a):
    since = datetime.now() - timedelta(days=a.days)
    samples, outages = load(a.data_dir, since)
    # per-timestamp group average latency
    bucket = {}
    for ts, g, _, avg, _ in samples:
        if avg is not None:
            bucket.setdefault((g, ts), []).append(avg)
    series = {}
    for (g, ts), v in sorted(bucket.items(), key=lambda kv: kv[0][1]):
        series.setdefault(g, []).append((ts, sum(v) / len(v)))
    now = datetime.now()
    rows = []
    for g in GROUPS:
        gs = [s for s in samples if s[1] == g]
        lat = [s[3] for s in gs if s[3] is not None]
        loss = [s[4] for s in gs]
        go = [o for o in outages if o[0] == g]
        down = sum(((e or now) - s).total_seconds() for _, s, e in go)
        total = (now - since).total_seconds()
        if gs:
            total = max((max(s[0] for s in gs) - min(s[0] for s in gs)).total_seconds(), 1)
        rows.append(
            f"<tr><td>{GROUP_FA[g]}</td>"
            f"<td>{sum(lat) / len(lat):.1f}</td>" if lat else f"<tr><td>{GROUP_FA[g]}</td><td>-</td>")
        rows[-1] += (f"<td>{min(lat):.1f} / {max(lat):.1f}</td>" if lat else "<td>-</td>")
        rows[-1] += (f"<td>{sum(loss) / len(loss):.1f}٪</td>" if loss else "<td>-</td>")
        rows[-1] += (f"<td>{len(go)}</td><td>{fmt_dur(down)}</td>"
                     f"<td>{max(0, 100 - 100 * down / total):.2f}٪</td></tr>")
    orows = "".join(
        f"<tr><td>{GROUP_FA.get(g, html.escape(g))}</td><td>{s:{FMT}}</td>"
        f"<td>{'ادامه دارد' if e is None else f'{e:{FMT}}'}</td>"
        f"<td>{fmt_dur(((e or now) - s).total_seconds())}</td></tr>" for g, s, e in outages
    ) or '<tr><td colspan="4">قطعی ثبت نشده است.</td></tr>'
    legend = " ".join(f'<span style="color:{COLORS[g]}">■ {GROUP_FA[g]}</span>' for g in GROUPS)
    page = f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>گزارش HomiPing</title>
<style>
body{{font-family:Tahoma,Vazirmatn,sans-serif;max-width:960px;margin:20px auto;padding:0 12px;color:#222}}
table{{border-collapse:collapse;width:100%;margin:8px 0 24px}}
th,td{{border:1px solid #ccc;padding:6px 8px;text-align:center}}th{{background:#f0f0f0}}
</style></head><body>
<h1>گزارش کیفیت اینترنت</h1>
<p>بازه: {a.days} روز اخیر · ساخته‌شده در {now:{FMT}} · تعداد نمونه: {len(samples)}</p>
<h2>تأخیر (میلی‌ثانیه)</h2><p>{legend}</p>
{chart(series)}
<h2>مقایسه داخلی و خارجی</h2>
<table><tr><th>گروه</th><th>میانگین تأخیر</th><th>کمینه / بیشینه</th><th>میانگین loss</th>
<th>تعداد قطعی</th><th>مجموع قطعی</th><th>دسترس‌پذیری</th></tr>{"".join(rows)}</table>
<h2>جدول قطعی‌ها</h2>
<table><tr><th>گروه</th><th>شروع</th><th>پایان</th><th>مدت</th></tr>{orows}</table>
</body></html>"""
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"report written: {a.out}")


def main():
    p = argparse.ArgumentParser(description="HomiPing - internet quality and outage logger")
    p.add_argument("--data-dir", default="homiping-data", help="CSV directory")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="start logging")
    r.add_argument("-i", "--interval", type=float, default=30, help="seconds between rounds")
    r.add_argument("-c", "--count", type=int, default=3, help="pings per target per round")
    r.add_argument("--timeout", type=float, default=2, help="per-ping timeout (s)")
    r.add_argument("--domestic", nargs="+", default=GROUPS["domestic"], metavar="HOST")
    r.add_argument("--foreign", nargs="+", default=GROUPS["foreign"], metavar="HOST")
    r.add_argument("--rounds", type=int, default=0, help="stop after N rounds (0 = forever)")
    r.set_defaults(fn=cmd_run)
    q = sub.add_parser("report", help="build a single-file HTML report")
    q.add_argument("-d", "--days", type=float, default=1, help="days to include")
    q.add_argument("-o", "--out", default="report.html")
    q.set_defaults(fn=cmd_report)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

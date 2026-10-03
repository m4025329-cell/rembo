#!/usr/bin/env python3
"""Генератор статического сайта с курсами валют (программное SEO).

Запуск:  python3 generate.py            # живые курсы (open.er-api.com, без ключа)
         python3 generate.py --offline  # тестовые курсы, без сети
Результат в папке dist/.
"""
import html, json, shutil, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "dist"
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

CURRENCIES = {
    "USD": "Доллар США", "EUR": "Евро", "RUB": "Российский рубль", "UAH": "Украинская гривна",
    "KZT": "Казахстанский тенге", "BYN": "Белорусский рубль", "PLN": "Польский злотый",
    "GBP": "Британский фунт", "CNY": "Китайский юань", "TRY": "Турецкая лира",
    "CZK": "Чешская крона", "CHF": "Швейцарский франк", "JPY": "Японская иена",
    "GEL": "Грузинский лари", "AMD": "Армянский драм", "AZN": "Азербайджанский манат",
    "UZS": "Узбекский сум", "MDL": "Молдавский лей", "AED": "Дирхам ОАЭ",
    "THB": "Таиландский бат", "INR": "Индийская рупия", "CAD": "Канадский доллар",
}
AMOUNTS = [1, 5, 10, 50, 100, 500, 1000, 5000, 10000, 50000]
SAMPLE = {"USD": 1, "EUR": 0.92, "RUB": 92, "UAH": 41, "KZT": 480, "BYN": 3.27, "PLN": 4.0,
          "GBP": 0.79, "CNY": 7.2, "TRY": 34, "CZK": 23, "CHF": 0.88, "JPY": 150, "GEL": 2.7,
          "AMD": 388, "AZN": 1.7, "UZS": 12700, "MDL": 17.8, "AED": 3.67, "THB": 35,
          "INR": 83, "CAD": 1.36}


def fetch_rates(offline):
    if offline:
        return SAMPLE, "тестовые данные"
    req = urllib.request.Request("https://open.er-api.com/v6/latest/USD",
                                 headers={"User-Agent": "rates-site/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if data.get("result") != "success":
        raise SystemExit("API error: %r" % data)
    rates = {c: data["rates"][c] for c in CURRENCIES if c in data["rates"]}
    if len(rates) < 10:
        raise SystemExit("Слишком мало валют в ответе API")
    return rates, data.get("time_last_update_utc", "")


def fmt(x):
    if x >= 100:
        s = f"{x:,.2f}"
    elif x >= 1:
        s = f"{x:,.4f}"
    else:
        s = f"{x:,.6f}"
    return s.replace(",", " ").rstrip("0").rstrip(".") if "." in s else s


def monetization():
    parts = []
    if CFG["affiliate_url"]:
        parts.append(f'<div class="aff"><p>{html.escape(CFG["affiliate_text"])}</p>'
                     f'<a rel="sponsored nofollow noopener" target="_blank" href="{html.escape(CFG["affiliate_url"])}">'
                     f'{html.escape(CFG["affiliate_label"])}</a></div>')
    if CFG["affiliate_banner_html"]:
        parts.append(CFG["affiliate_banner_html"])
    if CFG["adsense_client"]:
        parts.append(f'<ins class="adsbygoogle" style="display:block" data-ad-client="{CFG["adsense_client"]}" '
                     'data-ad-format="auto" data-full-width-responsive="true"></ins>'
                     '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script>')
    return "\n".join(parts)


def page(title, desc, path, body, jsonld=None):
    url = CFG["site_url"].rstrip("/") + path
    head_extra = ""
    if CFG["adsense_client"]:
        head_extra += (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client='
                       f'{CFG["adsense_client"]}" crossorigin="anonymous"></script>')
    if CFG["analytics_id"]:
        a = CFG["analytics_id"]
        head_extra += (f'<script async src="https://www.googletagmanager.com/gtag/js?id={a}"></script>'
                       f'<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}'
                       f'gtag("js",new Date());gtag("config","{a}");</script>')
    if jsonld:
        head_extra += f'<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>'
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{url}"><link rel="stylesheet" href="{BASE}/style.css">
{head_extra}</head><body><header><a href="{BASE}/">{html.escape(CFG['site_name'])}</a></header>
<main>{body}</main>
<footer><p>Курсы носят справочный характер и не являются офертой. {html.escape(CFG['site_name'])}.</p></footer>
</body></html>"""


BASE = ""


def main():
    global BASE
    offline = "--offline" in sys.argv
    BASE = "/" + CFG["site_url"].rstrip("/").split("/", 3)[3] if CFG["site_url"].rstrip("/").count("/") > 2 else ""
    rates, updated = fetch_rates(offline)
    codes = [c for c in CURRENCIES if c in rates]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    (OUT / "style.css").write_text(
        "body{font:16px/1.5 system-ui,sans-serif;margin:0;color:#222}header{background:#0b5;padding:12px 20px}"
        "header a{color:#fff;font-weight:700;text-decoration:none}main,footer{max-width:820px;margin:0 auto;padding:16px}"
        "table{border-collapse:collapse;width:100%;margin:12px 0}td,th{border:1px solid #ddd;padding:6px 10px;text-align:right}"
        "th:first-child,td:first-child{text-align:left}.big{font-size:1.6em;font-weight:700}"
        ".aff{background:#f3faf5;border:1px solid #bde5c8;padding:12px;margin:16px 0;border-radius:8px}"
        ".aff a{display:inline-block;background:#0b5;color:#fff;padding:8px 14px;border-radius:6px;text-decoration:none}"
        ".grid{columns:2 220px}.grid a{display:block}form.c{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}"
        "form.c input,form.c select{padding:8px;font-size:1em}", encoding="utf-8")
    mon = monetization()
    urls = ["/"]
    js_rates = json.dumps({c: rates[c] for c in codes})

    # страницы пар
    for a in codes:
        for b in codes:
            if a == b:
                continue
            r = rates[b] / rates[a]
            name_a, name_b = CURRENCIES[a], CURRENCIES[b]
            rows = "".join(f"<tr><td>{n:,} {a}</td><td>{fmt(n * r)} {b}</td></tr>".replace(",", " ")
                           for n in AMOUNTS)
            rev = "".join(f"<tr><td>{n:,} {b}</td><td>{fmt(n / r)} {a}</td></tr>".replace(",", " ")
                          for n in AMOUNTS)
            body = f"""<h1>{a} в {b}: курс на {today}</h1>
<p class="big">1 {a} = {fmt(r)} {b}</p>
<p>Актуальный курс: {name_a} ({a}) к валюте «{name_b}» ({b}). Обратный курс: 1 {b} = {fmt(1 / r)} {a}.
Данные обновляются ежедневно.</p>
{mon}
<h2>Конвертер {a} → {b}</h2>
<form class="c"><input id="v" type="number" value="100" min="0"> <span>{a} =</span> <b id="o"></b> <span>{b}</span></form>
<script>var R={r!r};function u(){{document.getElementById('o').textContent=(document.getElementById('v').value*R).toLocaleString('ru-RU',{{maximumFractionDigits:4}})}}document.getElementById('v').oninput=u;u();</script>
<h2>Таблица {a} → {b}</h2><table><tr><th>{a}</th><th>{b}</th></tr>{rows}</table>
<h2>Таблица {b} → {a}</h2><table><tr><th>{b}</th><th>{a}</th></tr>{rev}</table>
<p><a href="{BASE}/{b.lower()}-{a.lower()}/">Курс {b} в {a}</a></p>
<h2>Другие направления {a}</h2><div class="grid">{"".join(f'<a href="{BASE}/{a.lower()}-{x.lower()}/">{a} в {x}</a>' for x in codes if x not in (a, b))}</div>"""
            faq = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [{
                "@type": "Question", "name": f"Сколько будет 1 {a} в {b}?",
                "acceptedAnswer": {"@type": "Answer", "text": f"На {today} 1 {a} = {fmt(r)} {b}."}}]}
            d = OUT / f"{a.lower()}-{b.lower()}"
            d.mkdir()
            (d / "index.html").write_text(page(
                f"{a} в {b} — курс на {today}, конвертер валют",
                f"Курс {a} к {b} сегодня: 1 {a} = {fmt(r)} {b}. Конвертер и таблицы сумм.",
                f"/{a.lower()}-{b.lower()}/", body, faq), encoding="utf-8")
            urls.append(f"/{a.lower()}-{b.lower()}/")

    # главная
    pop = ["USD", "EUR", "RUB", "UAH", "KZT", "PLN", "GBP", "CNY", "TRY"]
    links = "".join(f'<h2>{a}</h2><div class="grid">' +
                    "".join(f'<a href="{BASE}/{a.lower()}-{b.lower()}/">{a} в {b} — {fmt(rates[b]/rates[a])}</a>'
                            for b in codes if b != a) + "</div>" for a in pop if a in codes)
    (OUT / "index.html").write_text(page(
        f"{CFG['site_name']} — конвертер {', '.join(pop[:4])} и других валют",
        "Актуальные курсы валют и онлайн-конвертер. Обновляется ежедневно.", "/",
        f"<h1>{html.escape(CFG['site_name'])}</h1><p>Обновлено: {html.escape(updated)}</p>{mon}{links}"),
        encoding="utf-8")

    # sitemap / robots / ads.txt
    site = CFG["site_url"].rstrip("/")
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
        "".join(f"<url><loc>{site}{u}</loc><lastmod>{today}</lastmod></url>" for u in urls) + "</urlset>")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {site}/sitemap.xml\n")
    if CFG["adsense_client"]:
        pub = CFG["adsense_client"].replace("ca-", "")
        (OUT / "ads.txt").write_text(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n")
    (OUT / ".nojekyll").write_text("")
    print(f"Сгенерировано страниц: {len(urls)} -> {OUT}")


if __name__ == "__main__":
    main()

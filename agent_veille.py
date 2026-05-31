#!/usr/bin/env python3
"""
Agent de Veille IA — Recherche quotidienne + résumé email
Exécuté chaque jour à 8h Paris via GitHub Actions
"""

import os
import smtplib
import logging
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import feedparser
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
GEMINI_API_KEY     = os.environ["GEMINI_API_KEY"]
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT          = "redonebek@gmail.com"

MAX_ARTICLES_PER_SOURCE = 5
MAX_CONTENT_CHARS       = 600

# ── Sources RSS ────────────────────────────────────────────────────────────────
RSS_SOURCES = [
    {"name": "TechCrunch AI",        "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "VentureBeat AI",       "url": "https://venturebeat.com/ai/feed/"},
    {"name": "The Verge AI",         "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"name": "Wired AI",             "url": "https://www.wired.com/feed/category/artificial-intelligence/latest/rss"},
    {"name": "MIT Technology Review","url": "https://www.technologyreview.com/feed/"},
    {"name": "AI News",              "url": "https://artificialintelligence-news.com/feed/"},
    {"name": "Google AI Blog",       "url": "https://blog.google/technology/ai/rss/"},
    {"name": "Hugging Face Blog",    "url": "https://huggingface.co/blog/feed.xml"},
    {"name": "Towards Data Science", "url": "https://towardsdatascience.com/feed"},
    {"name": "Import AI",            "url": "https://jack-clark.net/feed/"},
]

HEADERS = {"User-Agent": "Mozilla/5.0 (VeilleIA-Bot/1.0)"}


# ── Collecte ───────────────────────────────────────────────────────────────────

def fetch_rss(source: dict) -> list:
    try:
        feed = feedparser.parse(source["url"])
        articles = []
        for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
            raw = getattr(entry, "summary", "") or getattr(entry, "description", "")
            content = BeautifulSoup(raw, "html.parser").get_text()[:MAX_CONTENT_CHARS]
            articles.append({
                "source":  source["name"],
                "title":   entry.get("title", "").strip(),
                "url":     entry.get("link", ""),
                "content": content,
            })
        log.info(f"✅ {source['name']}: {len(articles)} articles")
        return articles
    except Exception as exc:
        log.warning(f"⚠️  {source['name']}: {exc}")
        return []


def collect_articles() -> list:
    all_articles = []
    for src in RSS_SOURCES:
        all_articles.extend(fetch_rss(src))
    log.info(f"📊 Total collecté: {len(all_articles)} articles")
    return all_articles


# ── Synthèse Gemini ────────────────────────────────────────────────────────────

def build_prompt(articles: list) -> str:
    today = date.today().strftime("%d/%m/%Y")
    bloc = "\n".join(
        f"[{a['source']}] {a['title']}\nURL: {a['url']}\n{a['content']}\n---"
        for a in articles
    )
    return f"""Tu es un expert en veille technologique IA. Date: {today}

Voici {len(articles)} articles récents collectés depuis les meilleurs sites spécialisés IA:

{bloc}

MISSION: Identifie les 10 NOUVEAUTÉS LES PLUS PROMETTEUSES.
Pour chaque point:
- Titre accrocheur en <strong>
- 2-3 phrases d'explication claire en français
- Pourquoi c'est prometteur / impact potentiel
- Lien source <a href="URL">source</a>

CRITÈRES: vraies innovations, percées, impacts concrets. Pas de doublons ni de marketing pur.

Réponds UNIQUEMENT en HTML valide pour email (balises <h2>, <ol>, <li>, <p>, <strong>, <a>).
Commence par un <p> d'introduction (tendances du jour), puis le <ol> des 10 points, puis un <p> de conclusion.
"""


def synthesize(articles: list) -> str:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
    log.info("🤖 Appel Gemini API...")
    response = model.generate_content(
        build_prompt(articles),
        generation_config=genai.GenerationConfig(temperature=0.7, max_output_tokens=4096),
    )
    return response.text


# ── Email ──────────────────────────────────────────────────────────────────────

def build_html(body: str, count: int) -> str:
    today_str = date.today().strftime("%d %B %Y")
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0f2f5;margin:0;padding:20px}}
  .wrap{{max-width:680px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.10)}}
  .header{{background:linear-gradient(135deg,#0f0c29,#302b63,#24243e);color:#fff;padding:36px 32px;text-align:center}}
  .header h1{{margin:0;font-size:26px;letter-spacing:-.5px}}
  .header p{{margin:8px 0 0;opacity:.75;font-size:14px}}
  .badge{{display:inline-block;background:#e94560;color:#fff;border-radius:20px;padding:4px 14px;font-size:12px;margin-top:10px;font-weight:600}}
  .body{{padding:32px}}
  .stats{{background:#f8f9fa;border-left:4px solid #302b63;padding:12px 16px;border-radius:0 8px 8px 0;margin-bottom:24px;font-size:13px;color:#555}}
  .content ol{{padding-left:22px}} .content li{{margin-bottom:20px;line-height:1.7}}
  .content strong{{color:#0f0c29}} .content a{{color:#302b63}}
  .footer{{background:#f8f9fa;padding:20px 32px;text-align:center;font-size:12px;color:#999;border-top:1px solid #eee}}
</style></head><body>
<div class="wrap">
  <div class="header">
    <h1>🤖 Veille IA Quotidienne</h1>
    <p>{today_str}</p>
    <span class="badge">Top 10 Nouveautés</span>
  </div>
  <div class="body">
    <div class="stats">📡 <strong>{count} articles</strong> analysés depuis 10 sources spécialisées · Synthèse par Gemini AI</div>
    <div class="content">{body}</div>
  </div>
  <div class="footer">
    🤖 Agent Veille IA · Propulsé par Gemini &amp; GitHub Actions<br>
    Sources: TechCrunch · VentureBeat · The Verge · Wired · MIT Tech Review · Google AI · Hugging Face · Import AI
  </div>
</div>
</body></html>"""


def send_email(html: str) -> None:
    today_str = date.today().strftime("%d/%m/%Y")
    subject = f"🤖 Veille IA — Top 10 du {today_str}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = RECIPIENT
    msg.attach(MIMEText(html, "html", "utf-8"))
    log.info(f"📧 Envoi à {RECIPIENT}...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
        srv.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        srv.sendmail(GMAIL_USER, RECIPIENT, msg.as_string())
    log.info("✅ Email envoyé!")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    log.info("🚀 Démarrage Agent Veille IA")
    articles = collect_articles()
    if not articles:
        log.error("❌ Aucun article. Abandon.")
        return
    gemini_body = synthesize(articles)
    html_email  = build_html(gemini_body, len(articles))
    send_email(html_email)
    log.info("🎉 Agent terminé avec succès!")


if __name__ == "__main__":
    main()
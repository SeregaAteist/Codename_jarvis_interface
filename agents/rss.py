"""RSS news headlines agent."""


class RSSAgent:
    name = "rss"
    icon = "📡"

    def __init__(self, feeds: list[str]):
        self.feeds = feeds

    def ask(self, _prompt: str = "") -> str:
        try:
            import feedparser
        except ImportError:
            return "feedparser не установлен: pip install feedparser"

        headlines = []
        for url in self.feeds[:3]:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:3]:
                    t = entry.get("title", "").strip()
                    if t:
                        headlines.append(t)
            except Exception:
                continue

        if not headlines:
            return "Не удалось загрузить новости."
        return "Последние новости:\n" + "\n".join(f"• {h}" for h in headlines[:6])

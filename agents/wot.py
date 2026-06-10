"""World of Tanks statistics via Wargaming public API."""
import json
import re
import urllib.request
import urllib.parse


_SERVERS = {
    "eu":   "https://api.worldoftanks.eu/wot",
    "na":   "https://api.worldoftanks.com/wot",
    "ru":   "https://api.worldoftanks.ru/wot",
    "asia": "https://api.worldoftanks.asia/wot",
}


class WotAgent:
    name = "wot"
    icon = "⊞"

    def __init__(
        self,
        application_id: str = "demo",
        server: str = "eu",
        default_nickname: str = "",
    ):
        self.app_id   = application_id
        self.base     = _SERVERS.get(server.lower(), _SERVERS["eu"])
        self.nickname = default_nickname

    def ask(self, prompt: str = "") -> str:
        nick = self._extract_nick(prompt) or self.nickname
        if not nick:
            return (
                "Укажи никнейм: «джарвис статистика WoT MyNickname» "
                "или задай wot.nickname в config.yaml."
            )

        try:
            account_id = self._search(nick)
            if not account_id:
                return f"Игрок «{nick}» не найден на сервере {self.base.split('/')[2]}."
            return self._stats(account_id, nick)
        except Exception as e:
            return f"Ошибка WoT API: {e}"

    # ── private ──────────────────────────────────────────────────────────────

    def _extract_nick(self, text: str) -> str:
        """Try to find a nickname after known keywords."""
        m = re.search(
            r"\b(?:wot|танки|статистик(?:а|у)|игрок|никнейм)\s+(\S+)",
            text, re.I,
        )
        return m.group(1) if m else ""

    def _fetch(self, path: str, **params) -> dict:
        params["application_id"] = self.app_id
        qs  = urllib.parse.urlencode(params)
        url = f"{self.base}{path}?{qs}"
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.loads(r.read())

    def _search(self, nick: str) -> int | None:
        data = self._fetch("/account/search/", search=nick, type="exact", limit=1)
        if data.get("status") != "ok" or not data.get("data"):
            return None
        return data["data"][0]["account_id"]

    def _stats(self, account_id: int, nick: str) -> str:
        data = self._fetch("/account/info/", account_id=account_id)
        p = data.get("data", {}).get(str(account_id))
        if not p:
            return "Нет данных для этого аккаунта."

        all_s    = p["statistics"]["all"]
        battles  = all_s.get("battles", 0)
        wins     = all_s.get("wins", 0)
        survived = all_s.get("survived_battles", 0)
        frags    = all_s.get("frags", 0)
        damage   = all_s.get("damage_dealt", 0)

        winrate  = round(wins / battles * 100, 1) if battles else 0
        avg_dmg  = round(damage / battles) if battles else 0
        avg_frag = round(frags / battles, 2) if battles else 0

        # Tank count
        tanks_data = self._fetch("/account/tanks/", account_id=account_id, fields="tank_id")
        tank_count = len(tanks_data.get("data", {}).get(str(account_id)) or [])

        return (
            f"WoT: {p['nickname']}\n"
            f"Боёв: {battles:,}  |  Победы: {winrate}%\n"
            f"Выжил: {survived:,}  |  Уничтожил: {frags:,}\n"
            f"Ср. урон: {avg_dmg:,}  |  Ср. фраги: {avg_frag}\n"
            f"Танков в ангаре: {tank_count}"
        )

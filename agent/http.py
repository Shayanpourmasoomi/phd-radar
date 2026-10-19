"""Polite HTTP: per-host delay, retries, robots.txt, hard failure -> (None, error)."""
from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlparse

import requests


class Http:
    def __init__(self, settings: dict):
        self.s = settings
        self.sess = requests.Session()
        self.sess.headers.update({"User-Agent": settings["user_agent"], "Accept-Language": "en;q=0.9"})
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.requests_made = 0
        self._pw = None          # Playwright / Chromium, started lazily, only for sources with `render:`
        self._browser = None

    def _allowed(self, url: str) -> bool:
        if not self.s.get("respect_robots_txt", True):
            return True
        p = urlparse(url)
        host = f"{p.scheme}://{p.netloc}"
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.sess.get(host + "/robots.txt", timeout=10)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                    self._robots[host] = rp
                else:
                    self._robots[host] = None
            except Exception:
                self._robots[host] = None
        rp = self._robots[host]
        return True if rp is None else rp.can_fetch(self.s["user_agent"], url)

    def _crawl_delay(self, url: str) -> float:
        p = urlparse(url)
        rp = self._robots.get(f"{p.scheme}://{p.netloc}")
        try:
            d = rp.crawl_delay(self.s["user_agent"]) if rp else None
            return float(d or 0)
        except Exception:
            return 0.0

    def _render(self, url: str, opts: dict) -> tuple[str | None, str | None]:
        """Load a JavaScript-driven page in headless Chromium and return the final HTML.
        opts: click_text (regex of a 'load more' button), max_clicks, scrolls, wait_ms."""
        import re as _re
        try:
            if self._browser is None:
                from playwright.sync_api import sync_playwright
                self._pw = sync_playwright().start()
                self._browser = self._pw.chromium.launch()
        except Exception as e:
            return None, f"browser unavailable ({type(e).__name__}: {str(e)[:80]})"
        page = None
        try:
            page = self._browser.new_page(user_agent=self.s["user_agent"], locale="en-GB")
            page.set_default_timeout(30000)
            page.goto(url, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=12000)
            except Exception:
                pass
            page.wait_for_timeout(int(opts.get("wait_ms", 1500)))
            for _ in range(int(opts.get("scrolls", 0))):
                page.mouse.wheel(0, 20000)
                page.wait_for_timeout(900)
            rx = opts.get("click_text")
            for _ in range(int(opts.get("max_clicks", 0)) if rx else 0):
                btn = page.get_by_role("button", name=_re.compile(rx, _re.I)).first
                if not btn.count():
                    btn = page.get_by_role("link", name=_re.compile(rx, _re.I)).first
                if not btn.count() or not btn.is_visible():
                    break
                btn.click()
                page.wait_for_timeout(1500)
            return page.content(), None
        except Exception as e:
            return None, f"{type(e).__name__}: {str(e)[:120]}"
        finally:
            if page is not None:
                page.close()

    def close(self):
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    def get(self, url: str, delay: float | None = None, headers: dict | None = None, render: dict | None = None) -> tuple[str | None, str | None]:
        """-> (html, error).  `delay` = minimum seconds between requests to this host
        (the larger of this, the global setting and the site's robots.txt Crawl-delay).
        `render` = options dict -> load with a real (headless) browser instead of plain HTTP."""
        if not self._allowed(url):
            return None, "disallowed by robots.txt"
        host = urlparse(url).netloc
        gap = max(self.s["request_delay_sec"], delay or 0, self._crawl_delay(url))
        if render is not None and render is not False:
            wait = gap - (time.time() - self._last.get(host, 0))
            if wait > 0:
                time.sleep(wait)
            self._last[host] = time.time()
            self.requests_made += 1
            html, err = self._render(url, render if isinstance(render, dict) else {})
            self._last[host] = time.time()
            return html, err
        last_err = None
        for attempt in range(self.s.get("retries", 2) + 1):
            wait = gap - (time.time() - self._last.get(host, 0))
            if wait > 0:
                time.sleep(wait)
            try:
                self._last[host] = time.time()
                self.requests_made += 1
                r = self.sess.get(url, timeout=self.s["timeout_sec"], headers=headers)
                if r.status_code == 200:
                    r.encoding = r.encoding or "utf-8"
                    return r.text, None
                last_err = f"HTTP {r.status_code}"
                if r.status_code in (403, 404, 410):
                    break
            except Exception as e:  # network / TLS / timeout
                last_err = f"{type(e).__name__}: {str(e)[:120]}"
            time.sleep(2 * (attempt + 1))
        return None, last_err

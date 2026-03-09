from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm

BASE_URL = "https://www.zalando.it"
CATEGORIES_URL = "https://www.zalando.it/faq/self-help/categories"
OUTPUT_PATH = Path("data/zalando_faq.json")
WAIT_TIMEOUT = 45
SLEEP_BETWEEN_REQUESTS = 0.35


@dataclass
class FaqItem:
    id: str
    category_slug: str
    category_label: str
    question: str
    answer: str
    source_url: str


def create_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1600,1200")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=it-IT")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )

    service = Service()
    return webdriver.Chrome(service=service, options=options)


def get_soup(driver: webdriver.Chrome, url: str) -> BeautifulSoup:
    driver.get(url)

    WebDriverWait(driver, WAIT_TIMEOUT).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    WebDriverWait(driver, WAIT_TIMEOUT).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )

    return BeautifulSoup(driver.page_source, "lxml")


def normalize_space(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_faq_article(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc != "www.zalando.it":
        return False
    path = parsed.path
    return path.startswith("/faq/") and path.endswith(".html")


def category_slug_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path.split("/")[-1]


def get_category_links(driver: webdriver.Chrome) -> dict[str, str]:
    soup = get_soup(driver, CATEGORIES_URL)
    links: dict[str, str] = {}

    for a in soup.select('a[href^="/faq/"]'):
        href = a.get("href", "").strip()
        full = urljoin(BASE_URL, href)
        parsed = urlparse(full)
        path = parsed.path.rstrip("/")

        if path.lower() in {"/faq", "/faq/self-help/categories"}:
            continue

        if path.endswith(".html"):
            continue

        label = normalize_space(a.get_text(" ", strip=True))
        if not label:
            continue

        links[label] = full

    return links


def get_article_links_for_category(driver: webdriver.Chrome, category_url: str) -> list[str]:
    soup = get_soup(driver, category_url)
    result: set[str] = set()

    for a in soup.select('a[href^="/faq/"]'):
        href = a.get("href", "").strip()
        full = urljoin(BASE_URL, href)
        if is_faq_article(full):
            result.add(full)

    return sorted(result)


def extract_answer_text(soup: BeautifulSoup) -> str:
    # Prefer semantic containers if present.
    selectors = [
        "main article",
        "main [data-testid='faq-answer']",
        "main",
        "article",
    ]

    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            chunks = [normalize_space(el.get_text(" ", strip=True)) for el in node.select("p, li")]
            chunks = [c for c in chunks if c]
            if chunks:
                return "\n".join(chunks)

    body_text = normalize_space(soup.get_text(" ", strip=True))
    return body_text


def extract_question(soup: BeautifulSoup, fallback_url: str) -> str:
    h1 = soup.select_one("h1")
    if h1:
        text = normalize_space(h1.get_text(" ", strip=True))
        if text:
            return text

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    title = normalize_space(title)
    if title:
        return title

    return category_slug_from_url(fallback_url).replace("-", " ").strip().capitalize()


def scrape_faq_articles(driver: webdriver.Chrome, category_links: dict[str, str]) -> list[FaqItem]:
    items: list[FaqItem] = []
    seen_urls: set[str] = set()

    for category_label, category_url in tqdm(category_links.items(), desc="Categorie"):
        category_slug = category_slug_from_url(category_url)
        try:
            article_links = get_article_links_for_category(driver, category_url)
        except (TimeoutException, WebDriverException):
            continue

        for article_url in article_links:
            if article_url in seen_urls:
                continue

            seen_urls.add(article_url)
            try:
                soup = get_soup(driver, article_url)
            except (TimeoutException, WebDriverException):
                continue

            question = extract_question(soup, article_url)
            answer = extract_answer_text(soup)
            answer = normalize_space(answer)

            if not answer or len(answer) < 40:
                continue

            faq_id = category_slug + "::" + category_slug_from_url(article_url)
            items.append(
                FaqItem(
                    id=faq_id,
                    category_slug=category_slug,
                    category_label=category_label,
                    question=question,
                    answer=answer,
                    source_url=article_url,
                )
            )
            time.sleep(SLEEP_BETWEEN_REQUESTS)

    return items


def save_items(items: Iterable[FaqItem], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(item) for item in items]
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    driver = create_driver()
    try:
        category_links = get_category_links(driver)
        if not category_links:
            raise RuntimeError("Nessuna categoria FAQ trovata su Zalando")

        items = scrape_faq_articles(driver, category_links)
        if not items:
            raise RuntimeError("Nessuna FAQ estratta. Verifica struttura pagina o blocchi anti-bot.")

        save_items(items, OUTPUT_PATH)
        print(f"FAQ salvate: {len(items)} -> {OUTPUT_PATH}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

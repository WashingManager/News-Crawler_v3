# FnNews_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import crawler_utils # 👈 공통 유틸리티 임포트

# --- ⬇️ 공통 코드 ⬇️ ---
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'Fn_News.json') # 👈 고유값

keywords, exclude_keywords = crawler_utils.load_keywords()
today = crawler_utils.get_today_string()

# --- ⬇️ 고유 로직 ⬇️ ---
urls = ['https://www.fnnews.com/newsflash'] # 👈 고유값
processed_links = set()

def process_article(element):
    title_element = element.find('strong', class_='tit_thumb')
    if not title_element:
        return None

    link_element = title_element.find('a')
    if not link_element:
        return None

    href_link = link_element.get('href')
    if not href_link.startswith('http'):
        href_link = 'https://www.fnnews.com' + href_link

    if href_link in processed_links:
        return None

    title = link_element.text.strip()
    time_element = element.find('span', class_='caption')
    if not time_element:
        return None

    time_str = time_element.text.strip()
    try:
        published_time = datetime.strptime(time_str, '%Y.%m.%d %H:%M')
        formatted_time = published_time.isoformat()
    except ValueError:
        return None

    img_element = element.find('img')
    img_url = img_element.get('src') if img_element else ''

    text_content = title
    # 👈 공통 유틸리티 함수 사용
    if crawler_utils.is_relevant(text_content, keywords, exclude_keywords):
        processed_links.add(href_link)
        return {
            'title': title,
            'time': formatted_time,
            'img': img_url,
            'url': href_link,
            #'original_url': href_link
        }
    return None

def scrape_page(url):
    print(f"Scraping URL: {url}")
    articles = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        relevant_elements = soup.select('div.wrap_txt')
        print(f"Found {len(relevant_elements)} articles")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_article, element) for element in relevant_elements]
            for future in as_completed(futures):
                article = future.result()
                if article:
                    articles.append(article)
        
        return articles
    except Exception as e:
        print(f"페이지 처리 실패 ({url}): {e}")
        return []

# --- ⬇️ main 함수 (공통 유틸리티를 사용하도록 수정) ⬇️ ---
def main():
    global processed_links
    
    #crawler_utils.ensure_file_exists(result_filename)
    processed_links = crawler_utils.get_existing_links(result_filename)
    
    all_articles = []

    for url in urls:
        articles = scrape_page(url)
        all_articles.extend(articles)

    if all_articles:
        crawler_utils.save_articles_to_json(result_filename, all_articles, today)
    else:
        print("No new articles found")

if __name__ == "__main__":
    main()

# Gukje_Crawler.py
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
result_filename = os.path.join(NEWS_JSON_DIR, 'Gukje_News.json') # 👈 고유값

keywords, exclude_keywords = crawler_utils.load_keywords()
today = crawler_utils.get_today_string()

# --- ⬇️ 고유 로직 ⬇️ ---
urls = [
    'https://www.gukjenews.com/news/articleList.html?sc_section_code=S1N1&view_type=sm',
    'https://www.gukjenews.com/news/articleList.html?sc_section_code=S1N3&view_type=sm',
    'https://www.gukjenews.com/news/articleList.html?sc_section_code=S1N6&view_type=sm'
] # 👈 고유값

processed_links = set()

def process_article(element, base_url):
    title_element = element.select_one('h4.titles a')
    if not title_element:
        return None

    href_link = 'https://www.gukjenews.com' + title_element['href']
    if href_link in processed_links:
        return None
    
    title = title_element.text.strip()
    time_element = element.select_one('span.byline em:nth-of-type(3)')
    time_str = time_element.text.strip() if time_element else ''
    try:
        published_time = datetime.strptime(time_str, '%Y.%m.%d %H:%M')
        formatted_time = published_time.isoformat()
    except ValueError:
        return None
    
    img_element = element.select_one('img')
    img_url = img_element.get('src') if img_element else ''
    if img_url and not img_url.startswith('http'):
        img_url = 'https://www.gukjenews.com' + img_url
    
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

def scrape_page(url, page):
    print(f"Scraping URL: {url}&page={page}")
    articles = []
    try:
        full_url = f"{url}&page={page}"
        response = requests.get(full_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        relevant_elements = soup.select('ul.type2 li')
        print(f"Found {len(relevant_elements)} articles")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_article, element, url) for element in relevant_elements]
            for future in as_completed(futures):
                article = future.result()
                if article:
                    articles.append(article)
        
        return articles
    except Exception as e:
        print(f"페이지 처리 실패 ({full_url}): {e}")
        return []

# --- ⬇️ main 함수 (공통 유틸리티를 사용하도록 수정) ⬇️ ---
def main():
    global processed_links
    
    #crawler_utils.ensure_file_exists(result_filename)
    processed_links = crawler_utils.get_existing_links(result_filename)
    
    all_articles = []
    
    for url in urls:
        page = 1
        while page <= 5:
            articles = scrape_page(url, page)
            all_articles.extend(articles)
            if not articles:
                break
            page += 1
            time.sleep(1)
    
    if all_articles:
        crawler_utils.save_articles_to_json(result_filename, all_articles, today)
    else:
        print("No new articles found")

if __name__ == "__main__":
    main()

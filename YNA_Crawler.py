# YNA_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import urllib.parse
import crawler_utils  # 👈 공통 유틸리티 임포트
import crawler_config # 👈 설정 파일 임포트

# --- ⬇️ 공통 코드 (삭제 및 utils로 대체) ⬇️ ---
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'yna_News.json') # 👈 고유값

# 1. 공통 유틸리티에서 키워드와 날짜 가져오기
keywords, exclude_keywords = crawler_utils.load_keywords()
today = crawler_utils.get_today_string()

# 2. 고유한 URL 리스트
base_urls = [
    'https://www.yna.co.kr/nk/news/politics',
    'https://www.yna.co.kr/nk/news/military',
    'https://www.yna.co.kr/nk/news/diplomacy',
    'https://www.yna.co.kr/nk/news/economy',
    'https://www.yna.co.kr/nk/news/society',
    'https://www.yna.co.kr/nk/news/cooperation',
    'https://www.yna.co.kr/nk/news/correspondents',
    'https://www.yna.co.kr/nk/news/advisory-column',
    'https://www.yna.co.kr/politics/all',
    'https://www.yna.co.kr/politics/diplomacy',
    'https://www.yna.co.kr/economy/all',
    'https://www.yna.co.kr/industry/all',
    'https://www.yna.co.kr/society/all',
    'https://www.yna.co.kr/international/all',
    'https://www.yna.co.kr/local/all',
    'https://www.yna.co.kr/culture/all'
] # 👈 고유값

processed_links = set()
processed_titles = set()

# 3. is_relevant_article, get_existing_links, save_to_json 함수
# (이 파일에서 모두 삭제 -> crawler_utils가 대신 처리)

# --- ⬇️ 이 크롤러만의 '고유한' 로직 (그대로 둠) ⬇️ ---

def process_article(article, base_url):
    """(고유 로직)"""
    title_element = article.select_one('span.title01') # 👈 고유 선택자
    title = title_element.text.strip() if title_element else ''
    if not title or title in processed_titles:
        return None
    
    link_element = article.select_one('a.tit-news') # 👈 고유 선택자
    href_link = link_element['href'] if link_element else ''
    if not href_link:
        return None
    
    full_link = 'https:' + href_link if href_link.startswith('//') else href_link
    parsed_url = urllib.parse.urlparse(full_link)
    clean_link = urllib.parse.urlunparse(parsed_url._replace(query=''))
    
    if clean_link in processed_links:
        return None
    
    lead_element = article.select_one('p.lead') # 👈 고유 선택자
    lead_full_text = lead_element.text.strip() if lead_element else ''
    
    # --- ⬇️ 수정된 부분 ⬇️ ---
    # p.lead의 텍스트를 줄바꿈(\n) 기준으로 1번만 분리
    lead_parts = lead_full_text.split('\n', 1)
    # 첫 번째 부분(부제목)을 요약문(lead)으로 사용
    lead = lead_parts[0].strip() if lead_parts else ''
    # --- ⬆️ 수정된 부분 ⬆️ ---

    # 키워드 관련 여부 검사는 원본 전체 텍스트(full_text)로 수행
    full_text = f"{title} {lead_full_text}" 
    
    # 👈 공통 유틸리티 함수 사용
    if not crawler_utils.is_relevant(full_text, keywords, exclude_keywords):
        return None
    
    time_element = article.select_one('span.txt-time') # 👈 고유 선택자
    published_time = ''
    if time_element:
        time_str = time_element.text.strip()
        try:
            current_year = datetime.now().year
            if '-' in time_str:  # 예: 04-18 20:54 # 👈 고유 시간 파싱
                parsed_time = datetime.strptime(f"{current_year}-{time_str}", '%Y-%m-%d %H:%M')
            else:  # 예: 2025-04-18 20:54
                parsed_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
            published_time = parsed_time.isoformat()
        except ValueError as e:
            print(f"Invalid time format: {time_str}, Error: {e}")
            return None
    
    img_element = article.select_one('img')
    img_url = img_element.get('src', '') if img_element else ''
    
    processed_links.add(clean_link)
    processed_titles.add(title)
    print(f"Article processed: {title} ({published_time})")
    return {
        'title': title,
        'time': published_time,
        'img': img_url,
        'url': clean_link,
        #'original_url': clean_link,
        'summary': lead # 👈 수정된 'lead' 변수(부제목)를 저장
    }

def scrape_page(url, page):
    """(고유 로직)"""
    print(f"Scraping URL: {url}/{page}")
    articles = []
    try:
        full_url = f"{url}/{page}" if page > 1 else url
        response = requests.get(full_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        article_elements = soup.select('ul.list01 li') # 👈 고유 선택자
        print(f"Found {len(article_elements)} articles")
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(process_article, article, url) for article in article_elements]
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
    global processed_links, processed_titles
    
    # 1. 공통 함수로 파일 생성 및 기존 링크 로드
    #crawler_utils.ensure_file_exists(result_filename)
    processed_links = crawler_utils.get_existing_links(result_filename)
    
    all_articles = []
    
    # 2. 고유한 스크래핑 로직 실행
    for url in base_urls:
        page = 1
        while page <= 5: # 👈 YNA 고유의 페이지네이션 로직
            articles = scrape_page(url, page)
            all_articles.extend(articles)
            if not articles:
                break
            page += 1
            time.sleep(2)
    
    # 3. 공통 함수로 저장
    if all_articles:
        crawler_utils.save_articles_to_json(result_filename, all_articles, today)
    else:
        print("No new articles found")

if __name__ == "__main__":
    main()

# SkyDaily_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import crawler_utils  # 👈 공통 유틸리티 임포트
import crawler_config # 👈 설정 파일 임포트 (is_relevant_article에서 사용)

# --- ⬇️ 공통 코드 (삭제 및 utils로 대체) ⬇️ ---
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'skyDaily_News.json') # 👈 고유값

# 1. 공통 유틸리티에서 키워드와 날짜 가져오기
keywords, exclude_keywords = crawler_utils.load_keywords()
today = crawler_utils.get_today_string()

# 2. 고유한 URL 리스트
urls = [
    'https://www.skyedaily.com/news/articlelist.html?mode=list',  # 최신기사
    'https://www.skyedaily.com/news/news_list21.html',  # 오피니언
    'https://www.skyedaily.com/news/news_list30.html?mode=ct&m_section=4',  # 정치
    'https://www.skyedaily.com/news/news_list30.html?mode=ct&m_section=5',  # 사회
    'https://www.skyedaily.com/news/news_list30.html?mode=ct&m_section=40',  # 경제
    'https://www.skyedaily.com/news/news_list30.html?mode=ct&m_section=2',  # 산업
    'https://www.skyedaily.com/news/news_list30.html?mode=ct&m_section=51',  # 생활경제
    'https://www.skyedaily.com/news/news_list30.html?mode=ct&m_section=30',  # 금융
    'https://www.skyedaily.com/news/news_list30.html?mode=ct&m_section=6',  # 문화
] # 👈 고유값

processed_links = set()

# 3. is_relevant_article, get_existing_links, save_to_json 함수
# (이 파일에서 모두 삭제 -> crawler_utils가 대신 처리)

# --- ⬇️ 이 크롤러만의 '고유한' 로직 (그대로 둠) ⬇️ ---

def extract_article_details(url):
    """(고유 로직)"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        response.encoding = 'euc-kr' # 👈 SkyDaily 고유 인코딩
        soup = BeautifulSoup(response.text, 'html.parser')
        summary_element = soup.select_one('div.article_txt')
        summary = summary_element.text.strip() if summary_element else ''
        #print(f"URL: {url}, 요약: {summary[:50]}...")
        return summary
    except Exception as e:
        print(f"데이터 추출 실패 ({url}): {e}")
        return ''

def process_article(element):
    """(고유 로직)"""
    href_link = element.get('href')
    if not href_link.startswith('http'):
        href_link = 'https://www.skyedaily.com' + href_link
    
    if href_link in processed_links:
        # print(f"이미 처리된 링크: {href_link}")
        return None
    
    title_element = element.find('font', class_='sctionarticletitle')
    time_element = element.find_next('font', class_='picarticletxt')
    
    if not (title_element and time_element):
        # print(f"제목 또는 시간 요소 누락: {href_link}")
        return None
    
    title = title_element.text.strip()
    time_str = time_element.text.strip()
    
    try:
        # 기본 시간 형식: 2025.03.16 12:34
        parsed_time = datetime.strptime(time_str, '%Y.%m.%d %H:%M')
        formatted_time = parsed_time.isoformat()
    except ValueError:
        try:
            # 대체 형식: 2025.03.16
            parsed_time = datetime.strptime(time_str, '%Y.%m.%d')
            formatted_time = parsed_time.replace(hour=0, minute=0, second=0).isoformat()
        except ValueError:
            try:
                # 한국어 형식: 2025년 3월 16일
                parsed_time = datetime.strptime(time_str, '%Y년 %m월 %d일')
                formatted_time = parsed_time.replace(hour=0, minute=0, second=0).isoformat()
            except ValueError as e:
                print(f"잘못된 시간 형식: {time_str}, 에러: {e}")
                return None
    
    summary = extract_article_details(href_link)
    text_content = f"{title} {summary}"
    
    # 👈 공통 유틸리티 함수 사용
    if not crawler_utils.is_relevant(text_content, keywords, exclude_keywords):
        #print(f"관련 없는 기사: {title}")
        return None
    
    img_element = element.find('img')
    img_url = img_element.get('src') if img_element else ''
    if img_url and not img_url.startswith('http'):
        img_url = 'https://www.skyedaily.com' + img_url
    
    processed_links.add(href_link)
    print(f"처리된 기사: {title} ({formatted_time})")
    return {
        'title': title,
        'time': formatted_time,
        'img': img_url,
        'url': href_link,
        #'original_url': href_link,
        'summary': summary
    }

def scrape_page(url):
    """(고유 로직)"""
    #print(f"Scraping URL: {url}")
    articles = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        response.encoding = 'euc-kr' # 👈 SkyDaily 고유 인코딩
        soup = BeautifulSoup(response.text, 'html.parser')
        relevant_elements = soup.select('div.picarticle a') # 👈 SkyDaily 고유 선택자
        print(f"선택된 요소 수: {len(relevant_elements)}")
        
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
    
    # 1. 공통 함수로 파일 생성 및 기존 링크 로드
    #crawler_utils.ensure_file_exists(result_filename)
    processed_links = crawler_utils.get_existing_links(result_filename)
    
    all_articles = []
    
    # 2. 고유한 스크래핑 로직 실행
    for url in urls:
        articles = scrape_page(url)
        all_articles.extend(articles)
        time.sleep(1)
    
    # 3. 공통 함수로 저장
    if all_articles:
        crawler_utils.save_articles_to_json(result_filename, all_articles, today)
    else:
        print("새로운 기사를 찾지 못함")

if __name__ == "__main__":
    main()

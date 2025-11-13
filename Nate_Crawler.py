# Nate_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, urlunparse
import time
import crawler_utils  # 👈 공통 유틸리티 임포트

# --- ⬇️ 공통 코드 ⬇️ ---
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'nate_News.json') # 👈 고유값

keywords, exclude_keywords = crawler_utils.load_keywords()
today = crawler_utils.get_today_string()

# --- ⬇️ 고유 로직 ⬇️ ---
base_urls = [
    'https://news.nate.com/recent?mid=n0102',  # 경제
    'https://news.nate.com/recent?mid=n0103',  # 사회
    'https://news.nate.com/recent?mid=n0104',  # 세계
    'https://news.nate.com/recent?mid=n0105',  # IT/과학
] # 👈 고유값

processed_links = set()
processed_titles = set()

def get_date_list():
    today_dt = datetime.now()
    return [today_dt.strftime('%Y%m%d')]

# --- ⬇️ 'Nate_Crawler.py'의 'get_nate_summary' 함수를 통째로 교체하세요 ⬇️ ---

def get_nate_summary(url):
    """
    [수정됨] Nate 기사 상세 페이지에서 두 가지 유형의 요약을 순차적으로 추출합니다.
    유형 1: div.subArea.subTitle (새로 발견된 구조)
    유형 2: div#realArtcContents (기존의 첫 텍스트 노드 구조)
    """
    try:
        # 1. 상세 페이지 HTML 요청
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        detail_soup = BeautifulSoup(response.text, 'html.parser')
        
        summary = ""

        # --- ⬇️ [수정된 로직] ⬇️ ---

        # 1. (신규) '유형 2' (subArea subTitle) 케이스 먼저 시도
        #    이 요소는 <br> 태그를 포함할 수 있습니다.
        summary_element_1 = detail_soup.select_one('div.subArea.subTitle')
        
        if summary_element_1:
            summary_html = summary_element_1.decode_contents()
            summary = summary_html.replace('<br>', '\n').replace('<br/>', '\n').strip()

        # 2. (기존) '유형 2'가 없다면, '유형 1' (realArtcContents) 시도
        if not summary:
            content_area = detail_soup.select_one('div#realArtcContents')
            if content_area:
                # div#realArtcContents 바로 아래의 첫 번째 텍스트 노드를 찾습니다.
                for node in content_area.find_all(string=True, recursive=False):
                    summary_text = node.strip()
                    # 비어있지 않고, 주석이 아닌 첫 텍스트
                    if summary_text and not summary_text.startswith('google_ad_section_start'):
                        summary = summary_text
                        break # 첫 번째 텍스트를 찾았으면 종료
        
        # --- ⬆️ [로직 수정 완료] ⬆️ ---

        if not summary:
             print(f"Summary not found: No known summary structure matched on {url}")

        return summary
        
    except Exception as e:
        print(f"Nate 요약 추출 실패 ({url}): {e}")
        return ""

def process_article(article, base_url):
    link_element = article.select_one('a.lt1')
    if not link_element:
        print("No link element found")
        return None
    
    href_link = link_element.get('href', '')
    if not href_link:
        print("No href in link element")
        return None
    
    full_link = urljoin(base_url, href_link)
    parsed_url = urlparse(full_link)
    clean_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, '', '', ''))
    
    if clean_url in processed_links:
        print(f"Duplicate URL: {clean_url}")
        return None
    
    title_element = article.select_one('h2.tit')
    if not title_element:
        print("No title element found")
        return None
    
    text_content = title_element.get_text(strip=True)
    
    # 👈 공통 유틸리티 함수 사용
    if text_content in processed_titles or not crawler_utils.is_relevant(text_content, keywords, exclude_keywords):
        return None
    
    time_element = article.select_one('span.medium em')
    published_time = time_element.get_text(strip=True) if time_element else ''
    if not published_time:
        print("No time element found")
        return None
    
    # 유연한 시간 형식 처리
    try:
        if '-' in published_time:  # 예: 04-18 20:54
            parsed_time = datetime.strptime(published_time, '%m-%d %H:%M')
            parsed_time = parsed_time.replace(year=datetime.now().year)  # 연도 추가
        else:  # 예: 2025.04.18 20:54
            parsed_time = datetime.strptime(published_time, '%Y.%m.%d %H:%M')
        formatted_time = parsed_time.isoformat()
    except ValueError as e:
        print(f"Invalid time format: {published_time}, Error: {e}")
        return None
    
    img_element = article.select_one('img')
    img_url = img_element.get('src', '') if img_element else ''

    summary = get_nate_summary(clean_url)
    
    processed_links.add(clean_url)
    processed_titles.add(text_content)
    print(f"Article processed: {text_content}")
    return {
        'title': text_content,
        'time': formatted_time,
        'img': img_url,
        'url': clean_url,
        #'original_url': clean_url,
        'summary': summary  # 👈 요약 필드 추가
    }

def scrape_page(url):
    print(f"Scraping URL: {url}")
    articles = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        article_elements = soup.select('div.mlt01')
        print(f"Found {len(article_elements)} articles")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_article, article, url) for article in article_elements]
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
    global processed_links, processed_titles
    
    #crawler_utils.ensure_file_exists(result_filename)
    processed_links = crawler_utils.get_existing_links(result_filename)
    
    all_articles = []
    
    for base_url in base_urls:
        for date in get_date_list():
            page = 1
            while page <= 10:
                url = f'{base_url}&type=c&date={date}&page={page}'
                articles = scrape_page(url)
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

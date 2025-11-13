# Naver_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import os
import re
import crawler_utils  # 👈 공통 유틸리티 임포트

# --- ⬇️ 공통 코드 (대부분 삭제됨) ⬇️ ---
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'naver_News.json') # 👈 고유값

# 1. 공통 유틸리티에서 키워드와 날짜 가져오기
keywords, exclude_keywords = crawler_utils.load_keywords()
today = crawler_utils.get_today_string()

# 2. 고유한 URL 리스트
urls = [
    'https://news.naver.com/section/100',  # 정치
    'https://news.naver.com/section/101',  # 경제
    'https://news.naver.com/section/103',  # 생활/문화
    'https://news.naver.com/section/104',  # 세계
    'https://news.naver.com/section/105',  # IT/과학
    'https://news.naver.com/breakingnews/section/104/231',  # 아시아/호주
    'https://news.naver.com/breakingnews/section/104/232',  # 유럽
    'https://news.naver.com/breakingnews/section/104/233',  # 중남미
    'https://news.naver.com/breakingnews/section/104/234',  # 중동/아프리카
    'https://news.naver.com/breakingnews/section/104/322',  # 북미
] # 👈 고유값

processed_links = set()
processed_titles = set()

# 3. is_relevant_article 함수 -> 공통 유틸리티 사용 (삭제됨)
# 4. get_existing_links 함수 -> 공통 유틸리티 사용 (삭제됨)

# --- ⬇️ 이 크롤러만의 '고유한' 로직 (그대로 둠) ⬇️ ---

def extract_article_details(url):
    """네이버 기사 페이지에서 상세 정보 추출 (고유 로직)"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 시간 정보 추출
        time_element = soup.select_one('span[class*="ARTICLE_DATE_TIME"]')
        published_time = ''
        if time_element:
            published_time_data = time_element.get('data-date-time', '')
            if published_time_data:
                try:
                    dt = datetime.strptime(published_time_data, '%Y-%m-%d %H:%M:%S')
                    published_time = dt.isoformat()
                except ValueError as e:
                    print(f"Invalid time format: {published_time_data}, Error: {e}")
                    return '', '', ''
        
        # 요약 정보 추출
        summary_element = soup.select_one('article#dic_area strong[style*="border-left: 2px solid"]')
        
        summary = ''
        
        # 1. 첫 번째 케이스 시도: .media_end_summary (기존에 작동하던 방식)
        #    이 케이스는 <br> 태그를 포함할 수 있습니다.
        summary_element_1 = soup.select_one('.media_end_summary')
        
        if summary_element_1:
            summary_html = summary_element_1.decode_contents()
            summary = summary_html.replace('<br>', '\n').replace('<br/>', '\n').strip()
            
        # 2. 첫 번째 케이스가 실패했거나 존재하지 않으면 (summary가 여전히 비어있다면), 
        #    두 번째 케이스를 시도합니다.
        if not summary:
            #    이 케이스는 단순 <strong> 태그입니다.
            summary_element_2 = soup.select_one('article#dic_area strong[style*="border-left: 2px solid"]')
            
            if summary_element_2:
                summary = summary_element_2.get_text(strip=True)
        
        # --- ⬆️ 요약 정보 추출 끝 ⬆️ ---
        
        # 이미지 URL 추출
        img_element = soup.select_one('img#img1')
        img_url = img_element.get('data-src', '') if img_element else ''
        
        return published_time, img_url, summary
    except Exception as e:
        print(f"데이터 추출 실패 ({url}): {e}")
        return '', '', ''

def scrape_page(url):
    """네이버 섹션 페이지 스크래핑 (고유 로직)"""
    print(f"Scraping URL: {url}")
    articles = []
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        article_elements = soup.select('div.section_latest_article ul li')
        print(f"Found {len(article_elements)} articles")
        
        for element in article_elements:
            title_element = element.select_one('div.sa_text a strong')
            if title_element:
                text_content = title_element.get_text(strip=True)
                href_link = title_element.parent['href']
                full_link = href_link if href_link.startswith('http') else f'https://news.naver.com{href_link}'
                
                # 👈 공통 유틸리티 함수 사용
                is_relevant = crawler_utils.is_relevant(text_content, keywords, exclude_keywords)
                
                if full_link not in processed_links and text_content not in processed_titles and is_relevant:
                    published_time, img_url, summary = extract_article_details(full_link)
                    if published_time:
                        processed_links.add(full_link)
                        processed_titles.add(text_content)
                        articles.append({
                            'title': text_content,
                            'time': published_time,
                            'img': img_url,
                            'url': full_link,
                            #'original_url': full_link,
                            'summary': summary
                        })
                        print(f"Article processed: {text_content} ({published_time})")
    except Exception as e:
        print(f"페이지 처리 실패 ({url}): {e}")
    return articles

# 5. save_to_json 함수 -> 공통 유틸리티 사용 (삭제됨)

# --- ⬇️ main 함수 (공통 유틸리티를 사용하도록 수정) ⬇️ ---

def main():
    global processed_links, processed_titles
    
    # 1. 공통 함수로 파일 생성 및 기존 링크 로드
    #crawler_utils.ensure_file_exists(result_filename)
    processed_links = crawler_utils.get_existing_links(result_filename)
    
    all_articles = []
    
    # 2. 고유한 스크래핑 로직 실행
    for url in urls:
        articles = scrape_page(url)
        all_articles.extend(articles)
    
    # 3. 공통 함수로 저장
    if all_articles:
        crawler_utils.save_articles_to_json(result_filename, all_articles, today)
    else:
        print("No new articles found")

if __name__ == "__main__":
    main()

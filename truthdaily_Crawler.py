# truthdaily_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os
import re
import time
import crawler_utils  # 👈 공통 유틸리티 임포트
import crawler_config # 👈 설정 파일 임포트

# --- ⬇️ 공통 코드 (삭제 및 utils로 대체) ⬇️ ---
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'truthdaily_News.json') # 👈 고유값

# 1. 공통 유틸리티에서 키워드와 날짜 가져오기
keywords, exclude_keywords = crawler_utils.load_keywords()
today = crawler_utils.get_today_string()

# 2. 고유한 URL 리스트
urls = [
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N1',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N2',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N3',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N4',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N5',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N6',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N7',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N8',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N9',
    'https://www.truthdaily.co.kr/news/articleList.html?sc_section_code=S1N10',
] # 👈 고유값

processed_links = set()
processed_titles = set()

# 3. is_relevant_article, get_existing_links, save_to_json 함수
# (이 파일에서 모두 삭제 -> crawler_utils가 대신 처리)

# --- ⬇️ 이 크롤러만의 '고유한' 로직 (그대로 둠) ⬇️ ---

def is_within_two_days(article_time_str):
    """(고유 로직) 기사 시간이 현재로부터 2일 이내인지 확인"""
    try:
        # "07-30 17:43" 형식을 파싱
        current_year = datetime.now().year
        article_datetime = datetime.strptime(f"{current_year}-{article_time_str}", "%Y-%m-%d %H:%M")
        
        # 현재 시간으로부터 2일 전 계산
        two_days_ago = datetime.now() - timedelta(days=2)
        
        return article_datetime >= two_days_ago
    except ValueError as e:
        print(f"시간 파싱 오류: {article_time_str}, {e}")
        return False

def extract_article_details(url):
    """(고유 로직) 개별 기사 페이지에서 상세 정보 추출"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 이미지 URL 추출
        img_element = soup.select_one('.article-body img')
        img_url = img_element.get('src', '') if img_element else ''
        if img_url and not img_url.startswith('http'):
            img_url = f"https://www.truthdaily.co.kr{img_url}"
        
        # 요약/본문 일부 추출
        content_element = soup.select_one('.article-body')
        summary = ''
        if content_element:
            paragraphs = content_element.find_all('p')
            if paragraphs:
                summary = paragraphs[0].get_text(strip=True)[:200] + "..." if len(paragraphs[0].get_text(strip=True)) > 200 else paragraphs[0].get_text(strip=True)
        
        return img_url, summary
    except Exception as e:
        print(f"기사 상세정보 추출 실패 ({url}): {e}")
        return '', ''

def load_more_articles(session, url, page_num):
    """(고유 로직) 더보기 버튼을 통해 추가 기사 로드"""
    try:
        base_url = url.split('?')[0]
        params = url.split('?')[1] if '?' in url else ''
        ajax_url = f"{base_url}?{params}&page={page_num}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': url
        }
        
        response = session.get(ajax_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"더보기 로드 실패 (페이지 {page_num}): {e}")
        return None

def scrape_page(url):
    """(고유 로직) 페이지별 기사 수집"""
    print(f"Scraping URL: {url}")
    articles = []
    session = requests.Session()
    page_num = 1
    
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        while True:
            sections_div = soup.select_one('#sections.altlist') # 👈 고유 선택자
            if not sections_div:
                print("sections div를 찾을 수 없습니다.")
                break
                
            article_elements = sections_div.select('li')
            print(f"페이지 {page_num}에서 {len(article_elements)}개 기사 발견")
            
            found_old_articles = False
            page_articles = []
            
            for element in article_elements:
                title_element = element.select_one('h2.altlist-subject a') # 👈 고유 선택자
                if not title_element:
                    continue
                    
                title = title_element.get_text(strip=True)
                href = title_element.get('href', '')
                full_link = href if href.startswith('http') else f'https://www.truthdaily.co.kr{href}'
                
                time_element = element.select_one('.altlist-info .altlist-info-item:last-child') # 👈 고유 선택자
                if not time_element:
                    continue
                    
                article_time = time_element.get_text(strip=True)
                
                if not is_within_two_days(article_time): # 👈 고유 시간 검사
                    print(f"2일 이전 기사 발견: {title} ({article_time})")
                    found_old_articles = True
                    break
                
                # 👈 공통 유틸리티 함수 사용
                is_relevant = crawler_utils.is_relevant(title, keywords, exclude_keywords)
                
                if full_link not in processed_links and is_relevant:
                    img_url, summary = extract_article_details(full_link)
                    
                    try:
                        current_year = datetime.now().year
                        dt = datetime.strptime(f"{current_year}-{article_time}", "%Y-%m-%d %H:%M")
                        published_time = dt.isoformat()
                    except ValueError:
                        published_time = article_time
                    
                    processed_links.add(full_link)
                    processed_titles.add(title)
                    
                    article_data = {
                        'title': title,
                        'time': published_time,
                        'img': img_url,
                        'url': full_link,
                        #'original_url': full_link,
                        'summary': summary
                    }
                    page_articles.append(article_data)
                    print(f"기사 처리 완료: {title} ({article_time})")
            
            articles.extend(page_articles)
            
            if found_old_articles or len(page_articles) == 0:
                print(f"수집 중단: {'2일 이전 기사 발견' if found_old_articles else '더 이상 기사 없음'}")
                break
            
            page_num += 1
            print(f"다음 페이지 {page_num} 로드 중...")
            soup = load_more_articles(session, url, page_num) # 👈 고유 AJAX 호출
            
            if not soup:
                print("더 이상 페이지를 로드할 수 없습니다.")
                break
            
            time.sleep(1)
            
    except Exception as e:
        print(f"페이지 처리 실패 ({url}): {e}")
    
    return articles

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
        time.sleep(2)  # 섹션 간 요청 간격 조절
    
    # 3. 공통 함수로 저장
    if all_articles:
        crawler_utils.save_articles_to_json(result_filename, all_articles, today)
        print(f"수집 완료: 총 {len(all_articles)}개의 새로운 기사")
    else:
        print("새로운 기사를 찾지 못했습니다.")

if __name__ == "__main__":
    main()

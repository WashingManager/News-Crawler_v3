# hanmiilbo_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os
import re
import time
import crawler_utils # 👈 공통 유틸리티 임포트

# --- ⬇️ 공통 코드 ⬇️ ---
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'hanmiilbo_News.json') # 👈 고유값

keywords, exclude_keywords = crawler_utils.load_keywords()
today = crawler_utils.get_today_string()

# --- ⬇️ 고유 로직 ⬇️ ---
urls = [
    'https://hanmiilbo.kr/news/list.php?mcode=m247tk9',
    'https://hanmiilbo.kr/news/list.php?mcode=m37525y',
    'https://hanmiilbo.kr/news/list.php?mcode=m38dz78',
    'https://hanmiilbo.kr/news/list.php?mcode=m39uqyj',
    'https://hanmiilbo.kr/news/list.php?mcode=m40weh7',
    'https://hanmiilbo.kr/news/list.php?mcode=m64aank',
] # 👈 고유값

processed_links = set()
processed_titles = set()

def is_within_two_days(article_date_str):
    """기사 날짜가 현재로부터 2일 이내인지 확인"""
    try:
        article_date = datetime.strptime(article_date_str, "%Y-%m-%d")
        two_days_ago = datetime.now() - timedelta(days=2)
        two_days_ago = two_days_ago.replace(hour=0, minute=0, second=0, microsecond=0)
        return article_date >= two_days_ago
    except ValueError as e:
        print(f"날짜 파싱 오류: {article_date_str}, {e}")
        return False

def extract_article_details(url):
    """개별 기사 페이지에서 상세 정보 추출"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        img_element = soup.select_one('.article_body img, .view_body img, .content img')
        img_url = img_element.get('src', '') if img_element else ''
        if img_url and not img_url.startswith('http'):
            img_url = f"https://hanmiilbo.kr{img_url}" if img_url.startswith('/') else f"https://hanmiilbo.kr/{img_url}"
        
        content_element = soup.select_one('.article_body, .view_body, .content')
        summary = ''
        if content_element:
            text_content = content_element.get_text(strip=True)
            summary = text_content[:200] + "..." if len(text_content) > 200 else text_content
        
        return img_url, summary
    except Exception as e:
        print(f"기사 상세정보 추출 실패 ({url}): {e}")
        return '', ''

def scrape_page(url, page_num=1):
    """페이지별 기사 수집 (페이지네이션 지원)"""
    print(f"Scraping URL: {url} (page {page_num})")
    articles = []
    
    try:
        if page_num > 1:
            separator = '&' if '?' in url else '?'
            page_url = f"{url}{separator}page={page_num}"
        else:
            page_url = url
            
        response = requests.get(page_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        basic_list = soup.select_one('div.basicList')
        if not basic_list:
            print("basicList div를 찾을 수 없습니다.")
            return articles, True # True to stop pagination
            
        article_elements = basic_list.select('dl')
        print(f"페이지 {page_num}에서 {len(article_elements)}개 기사 발견")
        
        if not article_elements:
            return articles, True # Stop if no articles found

        found_old_articles = False
        
        for element in article_elements:
            title_element = element.select_one('dt.title a')
            if not title_element:
                continue
                
            title = title_element.get_text(strip=True)
            href = title_element.get('href', '')
            
            if href.startswith('../'):
                full_link = f"https://hanmiilbo.kr/{href[3:]}"
            elif href.startswith('/'):
                full_link = f"https://hanmiilbo.kr{href}"
            elif not href.startswith('http'):
                full_link = f"https://hanmiilbo.kr/{href}"
            else:
                full_link = href
            
            date_element = element.select_one('dd.registDate')
            if not date_element:
                continue
                
            article_date = date_element.get_text(strip=True)
            
            if not is_within_two_days(article_date):
                print(f"2일 이전 기사 발견: {title} ({article_date})")
                found_old_articles = True
                continue # 2일 지난 기사는 건너뛰기
            
            # 👈 공통 유틸리티 함수 사용
            is_relevant = crawler_utils.is_relevant(title, keywords, exclude_keywords)
            
            if full_link not in processed_links and text_content not in processed_titles and is_relevant:
                img_url, summary = extract_article_details(full_link)
                
                try:
                    dt = datetime.strptime(article_date, "%Y-%m-%d")
                    published_time = dt.isoformat()
                except ValueError:
                    published_time = article_date
                
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
                
                articles.append(article_data)
                print(f"기사 처리 완료: {title} ({article_date})")
        
        return articles, found_old_articles # (articles_list, stop_crawling_flag)
            
    except Exception as e:
        print(f"페이지 처리 실패 ({url}, page {page_num}): {e}")
        return [], True # Stop on error

# --- ⬇️ main 함수 (공통 유틸리티를 사용하도록 수정) ⬇️ ---
def main():
    global processed_links, processed_titles
    
    #crawler_utils.ensure_file_exists(result_filename)
    processed_links = crawler_utils.get_existing_links(result_filename)
    
    all_articles = []
    
    for url in urls:
        page_num = 1
        while True:
            articles, stop = scrape_page(url, page_num)
            all_articles.extend(articles)
            
            if stop or page_num >= 10: # 10페이지 제한 또는 오래된 기사 발견 시 중지
                print(f"Scraping stopped for {url} at page {page_num}.")
                break
                
            page_num += 1
            time.sleep(2)  # 섹션 간 요청 간격 조절
    
    if all_articles:
        crawler_utils.save_articles_to_json(result_filename, all_articles, today)
    else:
        print("새로운 기사를 찾지 못했습니다.")

if __name__ == "__main__":
    main()

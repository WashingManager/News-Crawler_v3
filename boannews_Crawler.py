# boannews_Crawler.py
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
result_filename = os.path.join(NEWS_JSON_DIR, 'boannews_News.json') # 👈 고유값

keywords, exclude_keywords = crawler_utils.load_keywords()
today = crawler_utils.get_today_string()

# --- ⬇️ 고유 로직 ⬇️ ---
base_url = 'https://www.boannews.com/media/t_list.asp' # 👈 고유값

processed_links = set()
processed_titles = set()

def parse_article_datetime(datetime_str):
    """기사 날짜시간 파싱 ('2025년 07월 31일 13:44' 형식)"""
    try:
        dt = datetime.strptime(datetime_str, "%Y년 %m월 %d일 %H:%M")
        return dt
    except ValueError as e:
        print(f"날짜시간 파싱 오류: {datetime_str}, {e}")
        return None

def is_within_two_days(datetime_obj):
    """기사 날짜가 현재로부터 2일 이내인지 확인"""
    if not datetime_obj:
        return False
    two_days_ago = datetime.now() - timedelta(days=2)
    return datetime_obj >= two_days_ago

def extract_article_details(url):
    """개별 기사 페이지에서 상세 정보 추출"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        img_element = soup.select_one('.news_content img, .view_content img, #news_content img')
        img_url = img_element.get('src', '') if img_element else ''
        if img_url and not img_url.startswith('http'):
            img_url = f"https://www.boannews.com{img_url}" if img_url.startswith('/') else f"https://www.boannews.com/{img_url}"
        
        content_element = soup.select_one('.news_content, .view_content, #news_content')
        summary = ''
        if content_element:
            text_content = content_element.get_text(strip=True)
            summary = text_content[:200] + "..." if len(text_content) > 200 else text_content
        
        return img_url, summary
    except Exception as e:
        print(f"기사 상세정보 추출 실패 ({url}): {e}")
        return '', ''

def extract_article_link(news_txt_element):
    """news_txt 요소에서 기사 링크 추출"""
    try:
        if news_txt_element.name == 'a':
            return news_txt_element.get('href', '')
        
        link_element = news_txt_element.find('a')
        if link_element:
            return link_element.get('href', '')
        
        parent = news_txt_element.parent
        while parent:
            link_element = parent.find('a')
            if link_element:
                return link_element.get('href', '')
            parent = parent.parent
            
        return ''
    except Exception as e:
        print(f"링크 추출 실패: {e}")
        return ''

def scrape_page(page_num=1):
    """페이지별 기사 수집"""
    print(f"Scraping page: {page_num}")
    articles = []
    
    try:
        page_url = f"{base_url}?Page={page_num}" if page_num > 1 else base_url
            
        response = requests.get(page_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        media_div = soup.select_one('#media')
        if not media_div:
            print("media div를 찾을 수 없습니다.")
            return articles, True # Stop
            
        news_txt_elements = media_div.select('span.news_txt')
        print(f"페이지 {page_num}에서 {len(news_txt_elements)}개 기사 발견")
        
        if not news_txt_elements:
            return articles, True # Stop

        found_old_articles = False
        
        for news_txt_element in news_txt_elements:
            title = news_txt_element.get_text(strip=True)
            if not title:
                continue
            
            article_link = extract_article_link(news_txt_element)
            if not article_link:
                print(f"링크를 찾을 수 없음: {title}")
                continue
                
            if article_link.startswith('/'):
                full_link = f"https://www.boannews.com{article_link}"
            elif not article_link.startswith('http'):
                full_link = f"https://www.boannews.com/media/{article_link}"
            else:
                full_link = article_link
            
            writer_element = None
            current_element = news_txt_element.parent
            
            for _ in range(5):
                if current_element:
                    writer_element = current_element.find('span', class_='news_writer')
                    if writer_element:
                        break
                    current_element = current_element.parent
                else:
                    break
            
            if not writer_element:
                print(f"작성자 정보를 찾을 수 없음: {title}")
                continue
            
            writer_text = writer_element.get_text(strip=True)
            
            if '|' in writer_text:
                parts = writer_text.split('|')
                datetime_str = parts[1].strip() if len(parts) >= 2 else ''
            else:
                continue
            
            article_datetime = parse_article_datetime(datetime_str)
            if not article_datetime:
                continue
            
            if not is_within_two_days(article_datetime):
                print(f"2일 이전 기사 발견: {title} ({datetime_str})")
                found_old_articles = True
                continue # 2일 지난 기사 건너뛰기
            
            # 👈 공통 유틸리티 함수 사용
            is_relevant = crawler_utils.is_relevant(title, keywords, exclude_keywords)
            
            if full_link not in processed_links and text_content not in processed_titles and is_relevant:
                img_url, summary = extract_article_details(full_link)
                
                processed_links.add(full_link)
                processed_titles.add(title)
                
                article_data = {
                    'title': title,
                    'time': article_datetime.isoformat(),
                    'img': img_url,
                    'url': full_link,
                    #'original_url': full_link,
                    'summary': summary
                }
                
                articles.append(article_data)
                print(f"기사 처리 완료: {title} ({datetime_str})")
        
        return articles, found_old_articles # (articles_list, stop_crawling_flag)
            
    except Exception as e:
        print(f"페이지 처리 실패 (page {page_num}): {e}")
        return [], True # Stop on error

# --- ⬇️ main 함수 (공통 유틸리티를 사용하도록 수정) ⬇️ ---
def main():
    global processed_links, processed_titles
    
    #crawler_utils.ensure_file_exists(result_filename)
    processed_links = crawler_utils.get_existing_links(result_filename)
    
    all_articles = []
    page_num = 1
    
    while True:
        articles, stop = scrape_page(page_num)
        all_articles.extend(articles)
        
        if stop or page_num >= 10: # 10페이지 제한 또는 오래된 기사 발견 시 중지
            print(f"Scraping stopped at page {page_num}.")
            break
            
        page_num += 1
        time.sleep(2)
    
    if all_articles:
        crawler_utils.save_articles_to_json(result_filename, all_articles, today)
    else:
        print("새로운 기사를 찾지 못했습니다.")

if __name__ == "__main__":
    main()

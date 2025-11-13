# Daum_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import urllib.parse
import json
import crawler_utils # 👈 공통 유틸리티 임포트

# --- ⬇️ 공통 코드 ⬇️ ---
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR, 'daum_News.json') # 👈 고유값

keywords, exclude_keywords = crawler_utils.load_keywords()
today = crawler_utils.get_today_string()

# --- ⬇️ 고유 로직 ⬇️ ---
urls = [
    'https://news.daum.net/world',
    'https://news.daum.net/china',
    'https://news.daum.net/northamerica',
    'https://news.daum.net/japan',
    'https://news.daum.net/asia',
    'https://news.daum.net/arab',
    'https://news.daum.net/europe',
    'https://news.daum.net/southamerica',
    'https://news.daum.net/africa',
    'https://news.daum.net/topic',
    'https://news.daum.net/politics',
    'https://news.daum.net/society',
    'https://news.daum.net/economy',
    'https://news.daum.net/climate',
    'https://issue.daum.net/focus/241203'
] # 👈 고유값

result_set = set() # Daum은 set을 사용하므로 main에서 변환 필요
processed_links = set()

def extract_article_details(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        summary_element = soup.select_one('strong.summary_view')
        summary = summary_element.text.strip() if summary_element else ''
        
        img_element = soup.select_one('meta[property="og:image"]')
        img_url = img_element['content'] if img_element else ''
        if not img_url:
            img_element = soup.select_one('img[alt="thumbnail"]')
            img_url = img_element['src'] if img_element else ''
        
        return summary, img_url
    except Exception as e:
        print(f"요약/이미지 추출 실패 ({url}): {e}")
        return '', ''

def process_article(element, base_url, category):
    href_link = element.get('href')
    if not href_link or 'javascript' in href_link:
        return False
    
    if not href_link.startswith('http'):
        href_link = 'https://news.daum.net' + href_link
    
    title_element = element.find('span', class_='tit_txt')
    text_content = title_element.text.strip() if title_element else ''
    
    if not text_content:
        data_title = element.get('data-title')
        text_content = urllib.parse.unquote(data_title) if data_title else ''
    
    if not text_content:
        return False
    
    if href_link in processed_links:
        return False
    
    # 👈 공통 유틸리티 함수 사용
    if not crawler_utils.is_relevant(text_content, keywords, exclude_keywords):
        return False
    
    time_element = element.select_one('span.txt_info:last-of-type')
    summary, img_url = extract_article_details(href_link)
    
    formatted_time = ''
    if time_element:
        time_str = time_element.text.strip()
        try:
            published_time = datetime.strptime(time_str, '%Y.%m.%d. %H:%M:%S')
            formatted_time = published_time.strftime('%Y-%m-%d %H:%M')
        except ValueError:
            try:
                current_date = datetime.now().strftime('%Y-%m-%d')
                full_time_str = f'{current_date} {time_str}'
                published_time = datetime.strptime(full_time_str, '%Y-%m-%d %H:%M')
                formatted_time = published_time.strftime('%Y-%m-%d %H:%M')
            except ValueError:
                formatted_time = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    # Daum은 set에 튜플로 저장
    result_set.add((text_content, formatted_time, href_link, summary, img_url))
    processed_links.add(href_link)
    print(f"추출된 기사: {text_content} ({formatted_time})")
    return True

def get_news_from_page(url, page, category):
    try:
        full_url = f"{url}?page={page}" if 'breakingnews' in url else url
        response = requests.get(full_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        if category in ['politics', 'society', 'economy', 'climate']:
            selector = '.box_comp.box_news_headline2 .item_newsheadline2, .box_comp.box_news_block .item_newsblock'
        else:
            selector = '.list_newsheadline2 .item_newsheadline2, .list_newsbasic .item_newsbasic'
        
        relevant_elements = soup.select(selector)
        article_count = len(relevant_elements)

        print(f"URL: {full_url}, 기사 수: {article_count}")

        if article_count == 0:
            return False

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(process_article, element, url, category) for element in relevant_elements]
            results = [future.result() for future in as_completed(futures)]
        
        return any(results)
    except Exception as e:
        print(f"페이지 처리 실패 ({url}): {e}")
        return False

def scrape_category(url):
    category = url.split('/')[-1] if 'daum.net' in url else 'special'
    print(f"카테고리: {url}")
    
    if 'breakingnews' in url:
        page = 1
        while True:
            if not get_news_from_page(url, page, category):
                break
            page += 1
            time.sleep(2)
    else:
        get_news_from_page(url, 1, category)
        time.sleep(2)

# --- ⬇️ main 함수 (공통 유틸리티를 사용하도록 수정) ⬇️ ---
def main():
    global processed_links
    
    #crawler_utils.ensure_file_exists(result_filename)
    # Daum은 processed_links를 공통 유틸리티와 별개로 사용 (result_set 기준)
    # 따라서 get_existing_links는 save_to_json에서만 처리하도록 함
    # processed_links = crawler_utils.get_existing_links(result_filename) # 이 줄은 Daum에선 다르게 동작
    
    # Daum 크롤러는 기존 로직(set 사용)을 유지하되, 저장만 공통 모듈 사용
    for url in urls:
        scrape_category(url)

    # --- Daum 고유의 저장 방식 (set -> list 변환) ---
    print(f"최종 결과 수: {len(result_set)}")
    sorted_result = sorted(result_set, key=lambda x: x[1] if x[1] else '0000-00-00 00:00', reverse=True)

    all_articles = []
    for title, f_time, link, summary, img_url in sorted_result:
        try:
            # 시간 형식을 ISO로 통일
            iso_time = datetime.strptime(f_time, '%Y-%m-%d %H:%M').isoformat()
        except ValueError:
            iso_time = datetime.now().isoformat()
            
        all_articles.append({
            "title": title,
            "time": iso_time,
            "img": img_url,
            "url": link,
            #"original_url": link,
            "summary": summary
        })
    # --- 변환 완료 ---
    
    if all_articles:
        # 저장 시점의 processed_links를 전달하지 않고, 
        # save_articles_to_json 내부에서 기존 파일을 읽어 중복을 걸러내도록 함
        crawler_utils.save_articles_to_json(result_filename, all_articles, today)
    else:
        print("No new articles found")

if __name__ == "__main__":
    main()

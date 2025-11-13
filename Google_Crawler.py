# Google_Crawler.py
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import os
import re
from fuzzywuzzy import fuzz
from fake_useragent import UserAgent
import time
import random 
import crawler_utils # 👈 공통 유틸리티 임포트

# --- ⬇️ 공통 코드 ⬇️ ---
NEWS_JSON_DIR = 'news_json'
result_filename = os.path.join(NEWS_JSON_DIR,'google_News.json') # 👈 고유값

keywords, exclude_keywords = crawler_utils.load_keywords()
today = crawler_utils.get_today_string()

# --- ⬇️ 고유 로직 ⬇️ ---
urls = [
    'https://news.google.com/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNRFp4WkRNU0FtdHZLQUFQAQ?hl=ko&gl=KR&ceid=KR%3Ako', # 주요 뉴스
    'https://news.google.com/home?hl=ko&gl=KR&ceid=KR%3Ako', # 홈
    'https://news.google.com/topics/CAAqKAgKIiJDQkFTRXdvSkwyMHZNR1ptZHpWbUVnSnJieG9DUzFJb0FBUAE?hl=ko&gl=KR&ceid=KR%3Ako', # 과학/기술
    'https://news.google.com/search?q=%ED%99%94%EC%82%B0&hl=ko&gl=KR&ceid=KR%3Ako', # 화산
    'https://news.google.com/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FtdHZHZ0pMVWlnQVAB?hl=ko&gl=KR&ceid=KR%3Ako', #비즈니스
    'https://news.google.com/topics/CAAqIQgKIhtDQkFTRGdvSUwyMHZNR3QwTlRFU0FtdHZLQUFQAQ?hl=ko&gl=KR&ceid=KR%3Ako', #건강
    'https://news.google.com/search?q=%EB%B0%A9%EC%82%AC%EB%8A%A5&hl=ko&gl=KR&ceid=KR%3Ako', # 방사능
    'https://news.google.com/search?q=%EC%A0%84%EC%97%BC%EB%B3%91&hl=ko&gl=KR&ceid=KR%3Ako', # 전염병
    'https://news.google.com/search?q=%EC%84%B8%EA%B3%84%EC%9E%AC%EB%82%9C&hl=ko&gl=KR&ceid=KR%3Ako', # 세계재난
    'https://news.google.com/search?q=%EC%A7%80%EC%A7%84&hl=ko&gl=KR&ceid=KR%3Ako'  # 지진
] # 👈 고유값

processed_links = set()
ua = UserAgent()

def is_similar(title1, title2, threshold=35):
    # Compare titles ignoring case and whitespace
    t1 = re.sub(r'\s+', '', title1).lower()
    t2 = re.sub(r'\s+', '', title2).lower()
    return fuzz.ratio(t1, t2) >= threshold

def parse_google_time(time_str):
    """Parses Google News's datetime string and converts to timezone-aware datetime."""
    try:
        # Google uses ISO 8601 format with 'Z' for UTC
        dt_utc = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        # Convert to KST (UTC+9)
        dt_kst = dt_utc + timedelta(hours=9)
        return dt_kst
    except ValueError:
        print(f"Warning: Could not parse time string: {time_str}")
        return None
    except Exception as e:
        print(f"Error parsing time string {time_str}: {e}")
        return None

def is_within_last_days(article_dt, days=2):
    """Checks if the article datetime is within the last N days from now."""
    if not article_dt:
        return False
    # Make sure we compare timezone-aware with timezone-aware or naive with naive
    # Since article_dt is KST (aware), get current time in KST
    now_kst = datetime.now(article_dt.tzinfo) # Use the same timezone info
    cutoff_dt = now_kst - timedelta(days=days)
    return article_dt >= cutoff_dt

def scrape_page(url):
    print(f"Scraping URL: {url}")
    articles = []
    try:
        headers = {'User-Agent': ua.random}
        response = requests.get(url, headers=headers, timeout=20) # Increased timeout
        response.raise_for_status() # Check for HTTP errors
        response.encoding = response.apparent_encoding # Detect encoding

        soup = BeautifulSoup(response.text, 'html.parser')
        
        potential_articles = soup.find_all('article')
        if not potential_articles:
             # Fallback selector if <article> tag isn't used
             potential_articles = soup.select('div.XlKvRb, div.NiLAwe') # Adjust based on inspection

        print(f"Found {len(potential_articles)} potential article elements on {url}") # 👈 디버깅 코드

        processed_article_links_in_page = set() # Avoid duplicates within the same page scrape

        for item in potential_articles:
            link_element = item.find('a', href=True)
            if not link_element:
                continue

            href_link = link_element['href']
            # Resolve relative URLs
            if href_link.startswith('./'):
                href_link = href_link[1:] # Remove leading '.'
            if href_link.startswith('/'):
                full_link = f'https://news.google.com{href_link}'
            elif href_link.startswith('http'):
                 full_link = href_link # Already absolute (less common for main articles)
            else:
                 continue

            # Normalize URL for comparison
            full_link = full_link.replace('https://news.google.com./', 'https://news.google.com/')

            if full_link in processed_links or full_link in processed_article_links_in_page:
                continue

            title = link_element.get_text(strip=True)
            if not title: # Try finding title in another element if link text is empty/generic
                h_tag = item.find(['h3', 'h4']) # Common tags for titles
                if h_tag:
                    title = h_tag.get_text(strip=True)

            if not title: # Skip if no title found
                 continue

            print(f"Found potential title: {title}") # 👈 디버깅 코드

            # 👈 공통 유틸리티 함수 사용
            if not crawler_utils.is_relevant(title, keywords, exclude_keywords):
                print(f"SKIPPING (Irrelevant): {title}") # 👈 디버깅 코드
                continue

            time_element = item.find('time', datetime=True)
            if not time_element:
                 print(f"SKIPPING (No time element): {title}") # 👈 디버깅 코드
                 continue

            time_str = time_element['datetime']
            published_dt_kst = parse_google_time(time_str)

            if not published_dt_kst:
                 print(f"SKIPPING (Time parse fail): {title}") # 👈 디버깅 코드
                 continue # Skip if time couldn't be parsed

            if not is_within_last_days(published_dt_kst, days=2):
                print(f"SKIPPING (Old article): {title} ({published_dt_kst})") # 👈 디버깅 코드
                continue

            is_dup_title = False
            for existing_article in articles:
                if is_similar(title, existing_article['title']):
                    is_dup_title = True
                    break
            if is_dup_title:
                continue

            img_element = item.find('img', src=True)
            img_url = img_element['src'] if img_element else ''
            formatted_time = published_dt_kst.isoformat()

            print(f"  [+] Relevant Article Found: {title} ({formatted_time})")
            articles.append({
                'title': title,
                'time': formatted_time, 
                'img': img_url,
                'url': full_link,
                #'original_url': full_link 
            })
            processed_article_links_in_page.add(full_link)

        return articles

    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL {url}: {e}")
        return []
    except Exception as e:
        print(f"Error processing page {url}: {e}")
        import traceback
        traceback.print_exc() 
        return []

# --- ⬇️ main 함수 (공통 유틸리티를 사용하도록 수정) ⬇️ ---
def main():
    global processed_links
    
    #crawler_utils.ensure_file_exists(result_filename)
    processed_links = crawler_utils.get_existing_links(result_filename)
    print(f"Loaded {len(processed_links)} existing article URLs.")

    all_new_articles = []

    print(f"\n--- Starting Google News Scraping for {today} ---")
    if not keywords:
        print("Warning: No include keywords loaded. Relevance check might not work as expected.")

    for url in urls:
        articles = scrape_page(url)
        if articles: 
             all_new_articles.extend(articles)
        sleep_time = random.uniform(1.5, 4.0)
        print(f"Sleeping for {sleep_time:.1f} seconds...")
        time.sleep(sleep_time)

    print(f"\n--- Scraping Finished ---")
    print(f"Total potential new articles found across all sources: {len(all_new_articles)}")

    crawler_utils.save_articles_to_json(result_filename, all_new_articles, today)

    print(f"--- Process Completed ---")

if __name__ == "__main__":
    main()

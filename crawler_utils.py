import json
import os
import re
from datetime import datetime
import crawler_config  # 우리가 만든 설정 파일

# [!! Firebase Admin SDK 임포트 !!]
import firebase_admin
from firebase_admin import credentials, firestore

# [!! Firebase 초기화 플래그 !!]
# GitHub Action에서 스크립트가 여러 번 임포트되더라도
# Firebase 앱이 한 번만 초기화되도록 보장합니다.
_firebase_initialized = False

# 공통 기능 1: 키워드 로드 [!! 대폭 수정됨 !!]
def load_keywords():
    """
    [수정됨] News_keyword.json 로컬 파일 대신,
    Firebase Firestore의 'keywords/main' 문서에서 키워드를 직접 로드합니다.
    GitHub Action YML에 설정된 GOOGLE_APPLICATION_CREDENTIALS를 사용합니다.
    """
    global _firebase_initialized
    
    try:
        # 1. Firebase Admin SDK 초기화 (최초 1회만)
        if not _firebase_initialized:
            # GitHub Action YML에서 GOOGLE_APPLICATION_CREDENTIALS 환경 변수를
            # 설정했다면, cred=None (기본값)으로 자동 인증됩니다.
            firebase_admin.initialize_app()
            _firebase_initialized = True
            print("Firebase Admin SDK initialized.")
        
        # 2. Firestore 클라이언트 연결
        db = firestore.client()
        
        # 3. Firestore 문서 가져오기 (React 앱과 동일한 경로)
        doc_ref = db.collection("keywords").document("main")
        doc = doc_ref.get()

        if doc.exists:
            data = doc.to_dict()
            
            # 4. 키워드 목록 평탄화 (is_relevant 함수 호환성 유지)
            # Firestore 데이터: { "keywords": [ {"category": "A", "items": ["a1", "a2"]}, ... ] }
            # 변환된 데이터: ["a1", "a2", ...]
            keywords = [item for cat in data.get('keywords', []) for item in cat.get('items', [])]
            exclude_keywords = [item for cat in data.get('exclude_keywords', []) for item in cat.get('items', [])]
            
            print(f"Firestore loaded: {len(keywords)} keywords, {len(exclude_keywords)} exclude_keywords.")
            return keywords, exclude_keywords
        else:
            print("Error: Firestore document '/keywords/main' not found.")
            return [], []

    except Exception as e:
        print(f"Firestore 키워드 로드 중 치명적인 오류 발생: {e}")
        # Firestore가 실패하면 크롤링이 잘못될 수 있으므로, 비상용 로컬 파일을
        # 읽거나, 빈 리스트를 반환하여 크롤러를 안전하게 중지시킵니다.
        return [], []

# 공통 기능 2: 오늘 날짜 문자열 생성 (변경 없음)
def get_today_string():
    """'YYYY년 MM월 DD일 요일' 형식의 오늘 날짜 문자열을 반환합니다."""
    today_dt = datetime.now()
    day_map = {
        'Monday': '월요일', 'Tuesday': '화요일', 'Wednesday': '수요일',
        'Thursday': '목요일', 'Friday': '금요일', 'Saturday': '토요일', 'Sunday': '일요일'
    }
    eng_day = today_dt.strftime('%A')
    kor_day = day_map.get(eng_day, eng_day)
    return today_dt.strftime(f'%Y년 %m월 %d일 {kor_day}')

# 공통 기능 3: 기사 관련성 검사 (변경 없음)
def is_relevant(text_content, keywords, exclude_keywords):
    """
    기사 내용이 설정된 키워드(crawler_config)와 일치하는지, 
    제외 키워드에 포함되지 않는지 검사합니다.
    (load_keywords가 동일한 형식을 반환하므로 수정 필요 없음)
    """
    if not keywords:  # 키워드 파일이 없으면 True 반환 (모두 수집)
        return True
        
    text_lower = text_content.lower()
    
    # 1. 키워드 개수 확인
    matching_keywords_count = sum(1 for keyword in keywords if keyword.lower() in text_lower)
    
    if matching_keywords_count < crawler_config.MIN_KEYWORDS_REQUIRED:
        return False
        
    # 2. 제외 키워드 확인
    exclude_match = any(keyword.lower() in text_lower for keyword in exclude_keywords)
    if exclude_match:
        return False
        
    return True

# 공통 기능 4: 빈 JSON 파일 생성 (시작 시)
# (이 함수는 주석 처리되었거나 비어 있었으므로 그대로 둡니다)


# 공통 기능 5: 기존 링크 로드 (변경 없음)
def get_existing_links(result_filename):
    """
    기존 JSON 파일에서 모든 기사의 URL을 읽어와 Set으로 반환합니다.
    파일이 없거나 손상되었으면 빈 Set을 반환합니다.
    """
    links = set()
    try:
        # 파일이 비어있거나 존재하지 않으면 빈 Set 반환
        if not os.path.exists(result_filename) or os.stat(result_filename).st_size == 0:
            return links

        with open(result_filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        if not isinstance(data, list):
            print(f"Warning: {result_filename} 형식이 리스트가 아닙니다. 초기화합니다.")
            return links
            
        for day in data:
            if isinstance(day, dict) and 'articles' in day and isinstance(day['articles'], list):
                for article in day['articles']:
                    if isinstance(article, dict) and 'url' in article:
                        links.add(article['url'])
        return links

    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"{result_filename} 파일 읽기 오류 또는 없음: {e}. 새로 시작합니다.")
        return links # 손상되었거나 없는 경우에도 빈 Set 반환

# 공통 기능 6: JSON 파일 저장 (변경 없음)
def save_articles_to_json(result_filename, new_articles, today_string):
    """
    새 기사 목록을 기존 JSON 파일에 오늘 날짜로 추가하여 저장합니다.
    중복 URL은 자동으로 걸러냅니다.
    새 기사가 없더라도 오늘 날짜의 빈 항목을 생성/유지합니다.
    """
    
    existing_data = []
    
    # --- 파일/폴더 존재 여부 확인 및 초기화 (ensure_file_exists 로직 통합) ---
    if os.path.exists(result_filename) and os.stat(result_filename).st_size > 0:
        try:
            with open(result_filename, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    existing_data = []
        except json.JSONDecodeError:
            print(f"{result_filename} 파일이 손상됨. 새로 초기화합니다.")
            existing_data = []
    else:
        # 파일이 없거나 비어있으면 폴더 생성 보장
        # os.path.dirname이 비어있으면 (e.g., "file.json") 오류가 날 수 있으니 체크
        dir_name = os.path.dirname(result_filename)
        if dir_name: # dir_name이 'news_json' 같은 값일 때만
            os.makedirs(dir_name, exist_ok=True)
        print(f"{result_filename} 파일이 없거나 비어있음. 새로 시작합니다.")
    # --- 통합 완료 ---

    today_data = next((d for d in existing_data if d.get('date') == today_string), None)
    
    added_count = 0
    
    if today_data:
        # 오늘 날짜 항목이 있으면, 기존 URL Set을 만들어서 중복 제거
        existing_urls = {article['url'] for article in today_data.get('articles', [])}
        unique_new_articles = [
            article for article in new_articles if article['url'] not in existing_urls
        ]
        today_data['articles'].extend(unique_new_articles)
        added_count = len(unique_new_articles)
    else:
        # 오늘 날짜 항목이 없으면 새로 추가 (new_articles가 비어있어도 추가)
        existing_data.append({'date': today_string, 'articles': new_articles})
        added_count = len(new_articles)
    
    try:
        with open(result_filename, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        
        if added_count > 0:
            print(f"총 {added_count}개의 새 기사를 {result_filename}에 저장했습니다.")
        else:
            # 이 로그가 뜨면 성공입니다.
            print(f"새로운 기사는 없지만, {result_filename}의 오늘 날짜 항목을 생성/업데이트했습니다.")
    except Exception as e:
        print(f"JSON 저장 실패: {e}")

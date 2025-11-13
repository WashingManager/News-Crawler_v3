# clean_json.py
import os
import json

# 1. 기준이 되는 폴더 경로 설정
base_dir = os.path.dirname(os.path.abspath(__file__))
# 2. JSON 파일들이 있는 폴더 경로
target_dir = os.path.join(base_dir, 'news_json')

if not os.path.exists(target_dir):
    print(f"오류: '{target_dir}' 폴더를 찾을 수 없습니다.")
    exit()

print(f"'{target_dir}' 폴더에서 .json 파일 스캔을 시작합니다...")

# 3. news_json 폴더 내의 모든 파일 순회
for filename in os.listdir(target_dir):
    if filename.endswith('.json'):
        file_path = os.path.join(target_dir, filename)
        
        try:
            # 4. JSON 파일 읽기
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, list):
                print(f"[{filename}] 건너뛰기: 예상된 리스트 형식이 아닙니다.")
                continue

            changes_made = False
            
            # 5. 데이터 구조 순회 ( [ { "date": ..., "articles": [...] } ] )
            for day_entry in data:
                if isinstance(day_entry, dict) and 'articles' in day_entry:
                    articles = day_entry.get('articles', [])
                    
                    # 6. 'original_url' 삭제
                    for article in articles:
                        if isinstance(article, dict) and 'original_url' in article:
                            del article['original_url']
                            changes_made = True

            # 7. 변경된 경우에만 파일 덮어쓰기
            if changes_made:
                with open(file_path, 'w', encoding='utf-8') as f:
                    # indent=2를 사용해 "보기 좋게" 저장
                    json.dump(data, f, ensure_ascii=False, indent=2) 
                print(f"✅ [{filename}] 'original_url' 필드를 삭제하고 저장했습니다.")
            else:
                print(f"ℹ️ [{filename}] 이미 처리되었거나 'original_url' 필드가 없습니다.")

        except json.JSONDecodeError:
            print(f"❌ [{filename}] 오류: JSON 파일 형식이 손상되었습니다.")
        except Exception as e:
            print(f"❌ [{filename}] 처리 중 알 수 없는 오류 발생: {e}")

print("\n모든 JSON 파일 처리가 완료되었습니다.")

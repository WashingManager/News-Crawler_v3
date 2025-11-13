import os
import json

def clear_summary_in_json_files():
    # 현재 스크립트가 있는 폴더 기준
    folder = os.path.dirname(os.path.abspath(__file__))
    files = [f for f in os.listdir(folder) if f.lower().endswith(".json")]

    if not files:
        print("⚠️ JSON 파일이 없습니다.")
        return

    for filename in files:
        filepath = os.path.join(folder, filename)
        try:
            # JSON 파일 읽기
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # summary 비우기 (파일 구조에 따라 처리)
            def clear_summary(obj):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if key == "summary":
                            obj[key] = ""
                        else:
                            clear_summary(value)
                elif isinstance(obj, list):
                    for item in obj:
                        clear_summary(item)

            clear_summary(data)

            # 결과 덮어쓰기
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"✅ {filename} 처리 완료")

        except Exception as e:
            print(f"❌ {filename} 처리 실패: {e}")

if __name__ == "__main__":
    clear_summary_in_json_files()

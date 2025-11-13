import os
import re

# 현재 스크립트가 있는 디렉토리 기준
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

def comment_original_url_lines(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    modified = False
    new_lines = []
    # "original_url" 또는 'original_url' 포함 + 콜론(:) 매칭
    pattern = re.compile(r'["\']?original_url["\']?\s*:')

    for line in lines:
        if pattern.search(line) and not line.strip().startswith("#"):
            new_lines.append("#" + line)
            modified = True
        else:
            new_lines.append(line)

    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"✅ 수정됨: {os.path.basename(file_path)}")
    else:
        print(f"▶ 변경 없음: {os.path.basename(file_path)}")

def main():
    for file in os.listdir(CURRENT_DIR):
        # 대소문자 구분 없이 'crawler'가 파일명에 포함된 경우만
        if file.lower().endswith(".py") and "crawler" in file.lower():
            file_path = os.path.join(CURRENT_DIR, file)
            comment_original_url_lines(file_path)

if __name__ == "__main__":
    main()

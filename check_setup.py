import os
import cv2
import json
from ultralytics import YOLO

def check_files():
    print("----- 🏥 AI 스플렌더 진단 시작 -----")
    
    # 1. YOLO 모델 확인
    if os.path.exists("models/board_scanner.pt"):
        print("✅ [모델] board_scanner.pt 파일 있음")
        try:
            model = YOLO("models/board_scanner.pt")
            print("   -> YOLO 모델 로딩 성공!")
        except Exception as e:
            print(f"❌ [모델] 로딩 실패: {e}")
    else:
        print("❌ [모델] 'models/board_scanner.pt' 파일이 없습니다!")
        print("   -> 학습한 best.pt를 복사해서 이름을 바꿔 넣어주세요.")

    # 2. 원본 이미지 확인
    if os.path.exists("reference_imgs"):
        files = os.listdir("reference_imgs")
        img_count = len([f for f in files if f.endswith(('.jpg', '.png'))])
        if img_count > 0:
            print(f"✅ [원본] reference_imgs 폴더에 이미지 {img_count}장 있음")
        else:
            print("❌ [원본] reference_imgs 폴더가 비어있습니다!")
    else:
        print("❌ [원본] 'reference_imgs' 폴더가 없습니다!")

    # 3. DB 파일 확인
    if os.path.exists("card_database.json"):
        print("✅ [DB] card_database.json 파일 있음")
        try:
            with open("card_database.json", 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"   -> DB 데이터 로드 성공 (카드 {len(data['cards'])}개)")
        except:
            print("❌ [DB] JSON 파일 형식이 잘못되었습니다 (오타 확인).")
    else:
        print("❌ [DB] 'card_database.json' 파일이 없습니다!")

    print("---------------------------------------")

if __name__ == "__main__":
    check_files()
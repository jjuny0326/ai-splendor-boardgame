import cv2
import numpy as np
import os
import json
import uuid
from ultralytics import YOLO

class BoardRecognizer:
    def __init__(self):
        print("👁️ [인식기] AKAZE + 좌측하단(Left-Bottom) 집중 공략 모드 가동...")
        
        # 1. DB 로드
        with open('card_database.json', 'r', encoding='utf-8') as f:
            self.card_db = json.load(f)

        # 2. YOLO 로드
        try:
            self.yolo = YOLO('models/board_scanner.pt')
            print("✅ YOLO 모델 로드 완료")
        except:
            print("⚠️ 모델 파일 없음 (YOLO 건너뜀)")
            self.yolo = None

        # 3. AKAZE 알고리즘 (ORB보다 강력, SIFT보다 빠름)
        self.akaze = cv2.AKAZE_create()
        self.bf = cv2.BFMatcher(cv2.NORM_HAMMING)
        
        # 4. 참조 데이터 저장소 (카드용 / 귀족용 분리)
        self.card_refs = {}
        self.noble_refs = {}
        
        # 5. 원본 이미지 로드 및 전처리
        if os.path.exists('reference_imgs'):
            for f in os.listdir('reference_imgs'):
                if f.lower().endswith(('.jpg', '.png', '.jpeg')):
                    filename = os.path.splitext(f)[0] # ID (예: l1_01)
                    path = os.path.join('reference_imgs', f)
                    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                    
                    if img is not None:
                        # (1) 크기 표준화
                        img = self._resize_keeping_aspect_ratio(img, width=500)
                        
                        # (2) 타입별 처리
                        if filename.startswith('n'): 
                            # [귀족] 전체 이미지 사용 + 조명 보정
                            proc_img = self._enhance_image(img)
                            _, des = self.akaze.detectAndCompute(proc_img, None)
                            if des is not None: self.noble_refs[filename] = des
                        else: 
                            # [카드] 좌측 하단(비용)만 크롭 + 조명 보정
                            crop_img = self._get_card_roi(img)
                            proc_img = self._enhance_image(crop_img)
                            _, des = self.akaze.detectAndCompute(proc_img, None)
                            if des is not None: self.card_refs[filename] = des
                            
            print(f"✅ 참조 로드 완료: 카드 {len(self.card_refs)}장, 귀족 {len(self.noble_refs)}장")

    # -------------------------------------------------------------
    # [핵심] 이미지 처리 헬퍼 함수들
    # -------------------------------------------------------------
    
    def _resize_keeping_aspect_ratio(self, image, width=None):
        (h, w) = image.shape[:2]
        if width is None: return image
        r = width / float(w)
        dim = (width, int(h * r))
        return cv2.resize(image, dim, interpolation=cv2.INTER_AREA)

    def _enhance_image(self, img_gray):
        # CLAHE: 조명 반사 완화 및 대비 강조 (숫자 선명하게)
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8,8))
        return clahe.apply(img_gray)

    def _get_card_roi(self, img):
        """
        [전략] 카드의 '좌측 하단' 영역만 잘라냅니다.
        - 높이: 위에서 35% 지점부터 바닥까지 (하단 65%) -> 비용 4줄도 충분히 포함
        - 너비: 왼쪽에서 45% 지점까지 (우측 그림 제거) -> 그림 매칭 방해 요소 제거
        """
        h, w = img.shape[:2]
        start_y = int(h * 0.35)
        end_x = int(w * 0.45)
        return img[start_y:h, 0:end_x]

    # -------------------------------------------------------------
    # 매칭 함수
    # -------------------------------------------------------------
    def _match(self, crop, is_card=True, level_prefix=None):
        if crop is None: return None, 0
        
        # 1. 웹캠 이미지 전처리 (원본과 똑같은 과정 거침)
        # 크기 통일 -> (카드면 크롭) -> 흑백 -> 보정
        crop = self._resize_keeping_aspect_ratio(crop, width=500)
        
        if len(crop.shape) == 3:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = crop
            
        if is_card:
            # 카드면 좌측 하단만 자름
            roi = self._get_card_roi(gray)
            target_refs = self.card_refs
        else:
            # 귀족이면 전체 사용
            roi = gray
            target_refs = self.noble_refs
            
        # 조명 보정
        proc_img = self._enhance_image(roi)
        
        # 특징점 추출
        _, des = self.akaze.detectAndCompute(proc_img, None)
        if des is None: return None, 0

        best_id = None
        max_score = 0

        # 2. 비교 (KNN Match)
        for cid, rdes in target_refs.items():
            if level_prefix and not cid.startswith(level_prefix): continue
            
            try:
                matches = self.bf.knnMatch(des, rdes, k=2)
                good = []
                for m, n in matches:
                    if m.distance < 0.8 * n.distance: # Ratio Test
                        good.append(m)
                
                score = len(good)
                if score > max_score:
                    max_score = score
                    best_id = cid
            except: continue
        
        # 점수 기준 (AKAZE는 점수가 좀 더 잘 나옵니다)
        threshold = 12 if is_card else 8
        if max_score >= threshold:
            return best_id, max_score
        else:
            return None, 0

    # -------------------------------------------------------------
    # 메인 프로세스
    # -------------------------------------------------------------
    def process_image(self, path):
        img = cv2.imread(path)
        if img is None: return {"error": "이미지를 찾을 수 없습니다."}
        
        debug_img = img.copy()
        
        # 후보군 저장소
        card_candidates = []
        gems = {"ruby": 0, "sapphire": 0, "emerald": 0, "diamond": 0, "onyx": 0, "gold": 0}
        nobles = []
        
        if self.yolo:
            # 고화질 분석 (1280px)
            results = self.yolo(img, conf=0.1, imgsz=1280)
            
            for box in results[0].boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls = self.yolo.names[int(box.cls[0])]
                
                # --- A. 카드 처리 ---
                if "card" in cls.lower() or "l1" in cls or "l2" in cls or "l3" in cls:
                    crop = img[y1:y2, x1:x2]
                    prefix = "l1" if "l1" in cls else "l2" if "l2" in cls else "l3" if "l3" in cls else None
                    
                    # 카드 매칭 (is_card=True)
                    mid, score = self._match(crop, is_card=True, level_prefix=prefix)
                    
                    if mid:
                        card_candidates.append({
                            'box': (x1, y1, x2, y2),
                            'id': mid,
                            'score': score,
                            'level': prefix
                        })
                    else:
                        # 실패 시 빨간 박스
                        cv2.rectangle(debug_img, (x1, y1), (x2, y2), (0, 0, 255), 2)

                # --- B. 귀족 처리 ---
                elif "noble" in cls.lower():
                    mid, score = self._match(img[y1:y2, x1:x2], is_card=False)
                    if mid:
                        nobles.append({"id": mid})
                        cv2.rectangle(debug_img, (x1, y1), (x2, y2), (255, 0, 255), 2)
                        cv2.putText(debug_img, mid, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)

                # --- C. 보석 처리 ---
                elif "token_" in cls:
                    c_lower = cls.lower()
                    color = None
                    for g in gems.keys():
                        if g in c_lower: color = g; break
                    
                    if color:
                        gems[color] += 1
                        cv2.rectangle(debug_img, (x1, y1), (x2, y2), (0, 255, 255), 2)
                        cv2.putText(debug_img, color, (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

        # 2. 카드 중복 제거 및 상위 4장 선정
        card_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        final_cards = {"level_1": [], "level_2": [], "level_3": []}
        used_ids = set()

        for card in card_candidates:
            cid = card['id']
            score = card['score']
            x1, y1, x2, y2 = card['box']
            
            # 레벨 키
            if "l1" in cid: lv_key = "level_1"
            elif "l2" in cid: lv_key = "level_2"
            else: lv_key = "level_3"
            
            # 이미 등록된 ID면 패스
            if cid in used_ids:
                cv2.rectangle(debug_img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                continue
            # 해당 레벨 4장 찼으면 패스
            if len(final_cards[lv_key]) >= 4:
                cv2.rectangle(debug_img, (x1, y1), (x2, y2), (128, 0, 128), 2)
                continue

            # 최종 등록
            used_ids.add(cid)
            final_cards[lv_key].append({"id": cid})
            
            # 성공 박스 (초록)
            cv2.rectangle(debug_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(debug_img, f"{cid}({score})", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # 디버그 이미지 저장
        if not os.path.exists('static'): os.makedirs('static')
        filename = f"debug_{uuid.uuid4().hex[:8]}.jpg"
        
        # 기존 파일 정리
        for f in os.listdir('static'):
            if f.startswith('debug_'):
                try: os.remove(os.path.join('static', f))
                except: pass
                
        cv2.imwrite(os.path.join('static', filename), debug_img)

        print(f"📊 처리 완료: 카드 {len(used_ids)}장, 보석 {gems}")
        return {"gems": gems, "cards_open": final_cards, "nobles": nobles, "debug_file": filename}
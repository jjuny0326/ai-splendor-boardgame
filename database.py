import json
import os

class CardDatabase:
    def __init__(self, path='card_database.json'):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        else:
            # 파일이 없으면 빈 껍데기라도 만듦
            self.data = {"cards": {}, "nobles": {}}

    def get_card_info(self, card_id):
        """
        ID로 카드 정보를 가져오고, 
        ***데이터 안에 'id' 필드를 강제로 심어줍니다.*** (핵심!)
        """
        # 1. 개발 카드인지 귀족인지 확인해서 정보 가져오기
        info = self.data['cards'].get(card_id) or self.data['nobles'].get(card_id)
        
        # 2. 정보가 있다면, 'id'를 추가해서 반환 (이게 없으면 KeyError 발생!)
        if info:
            info = info.copy() # 원본 데이터 보호를 위해 복사
            info['id'] = card_id 
        
        return info
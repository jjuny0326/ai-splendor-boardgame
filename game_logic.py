from database import CardDatabase
import copy

class GameLogic:
    def __init__(self):
        self.db = CardDatabase()
        self.reset_game()

    def reset_game(self):
        # 2인플 보석 총량
        self.TOTAL_GEMS = {"ruby": 4, "sapphire": 4, "emerald": 4, "diamond": 4, "onyx": 4, "gold": 5}
        
        self.game_state = {
            "board": {
                "gems": self.TOTAL_GEMS.copy(),
                "cards_open": {"level_1": [], "level_2": [], "level_3": []},
                "nobles": [] 
            },
            "players": {
                "ai": {"points": 0, "gems": {k:0 for k in self.TOTAL_GEMS}, "cards_owned": [], "cards_reserved": []},
                "human": {"points": 0, "gems": {k:0 for k in self.TOTAL_GEMS}, "cards_owned": [], "cards_reserved": []}
            }
        }
        self.history = []
        print("🔄 게임이 초기화되었습니다.")

    def get_state(self):
        return self.game_state

    def save_state(self):
        self.history.append(copy.deepcopy(self.game_state))
        if len(self.history) > 20: self.history.pop(0)

    def undo_turn(self):
        if not self.history: return False, "되돌릴 기록이 없습니다."
        self.game_state = self.history.pop()
        return True, "이전 턴으로 되돌렸습니다."

    # --- 추론 ---
    def infer_human_turn(self, new_board_data):
        old_board = self.game_state['board']
        human = self.game_state['players']['human']
        ai = self.game_state['players']['ai'] # AI 정보도 필요
        
        changes = {"missing_cards": [], "gem_diff": {}, "action_type": "unknown"}

        gem_taken_count = 0
        gem_paid_count = 0
        gold_change = 0
        
        # 카메라 데이터 1차 검증 (물리적 한계 체크)
        # 카메라가 본 보석 개수가 (전체 - AI가 가진 것)보다 많으면 오인식임!
        for gem, count in new_board_data['gems'].items():
            ai_has = ai['gems'].get(gem, 0)
            max_possible = self.TOTAL_GEMS[gem] - ai_has
            
            if count > max_possible:
                # print(f"🛡️ [보정] {gem} 인식 오류 ({count} -> {max_possible}). AI가 {ai_has}개 보유 중.")
                new_board_data['gems'][gem] = max_possible # 강제 하향 조정

        # 1. 보석 변화 계산
        for gem in self.TOTAL_GEMS:
            old_cnt = old_board['gems'].get(gem, 0)
            new_cnt = new_board_data['gems'].get(gem, 0)
            diff = new_cnt - old_cnt
            
            if abs(diff) > 3: continue
            if diff != 0:
                changes["gem_diff"][gem] = diff
                if diff < 0: gem_taken_count += abs(diff)
                else: gem_paid_count += diff
                if gem == 'gold': gold_change = diff

        # 2. 카드 변화
        for level in ['level_1', 'level_2', 'level_3']:
            old_ids = [c.get('id') for c in old_board['cards_open'][level] if c.get('id')]
            new_ids = [c.get('id') for c in new_board_data['cards_open'][level] if c.get('id')]
            missing = list(set(old_ids) - set(new_ids))
            
            if len(missing) > 1: missing = missing[:1]
            
            valid = []
            for cid in missing:
                info = self.db.get_card_info(cid)
                if info and self._can_buy(human, info['cost']): valid.append(cid)
            changes["missing_cards"].extend(valid)

        # 3. 행동 판단
        if len(changes["missing_cards"]) == 1 and gold_change == -1:
            changes["action_type"] = "reserve"
        elif gem_taken_count > 0:
            changes["action_type"] = "take_gems"
            changes["missing_cards"] = []
            for k in list(changes["gem_diff"]): 
                if changes["gem_diff"][k] > 0: del changes["gem_diff"][k]
        elif gem_paid_count > 0:
            if changes["missing_cards"]:
                changes["action_type"] = "buy"
            else:
                changes["action_type"] = "buy_reserved"
                paid = {g: d for g, d in changes['gem_diff'].items() if d > 0}
                inferred = self._find_card_by_payment(human, paid, "reserved")
                if inferred: changes["missing_cards"] = [inferred]
            
            for k in list(changes["gem_diff"]): 
                if changes["gem_diff"][k] < 0: del changes["gem_diff"][k]
        
        return changes

    def confirm_human_turn(self, changes, new_board_data):
        self.save_state()
        human = self.game_state['players']['human']
        ai = self.game_state['players']['ai']
        action = changes.get("action_type")

        # 1. 보드판 보석 동기화 (여기서도 물리 한계 적용)
        for gem, count in new_board_data['gems'].items():
            ai_has = ai['gems'].get(gem, 0)
            max_possible = self.TOTAL_GEMS[gem] - ai_has
            # 카메라가 AI 보석까지 뺏어서 보드에 있다고 우기면 강제 수정
            if count > max_possible:
                new_board_data['gems'][gem] = max_possible
        
        self.game_state['board']['gems'] = new_board_data['gems']

        # 2. 행동 처리
        if action == "reserve":
            for cid in changes['missing_cards']:
                c = self.db.get_card_info(cid)
                if c and len(human['cards_reserved']) < 3: 
                    human['cards_reserved'].append(c)

        elif action == "buy_reserved":
            paid = {g: d for g, d in changes['gem_diff'].items() if d > 0}
            bid = self._find_card_by_payment(human, paid, "reserved")
            if bid:
                target = next((c for c in human['cards_reserved'] if c['id'] == bid), None)
                if target:
                    human['cards_reserved'].remove(target)
                    human['cards_owned'].append(target)
                    human['points'] += target['points']

        elif action == "buy":
            for cid in changes['missing_cards']:
                c = self.db.get_card_info(cid)
                if c:
                    human['cards_owned'].append(c)
                    human['points'] += c['points']
                    reserved_match = next((rc for rc in human['cards_reserved'] if rc['id'] == cid), None)
                    if reserved_match: human['cards_reserved'].remove(reserved_match)

        # 3. 보석 총량 법칙 (내 보석 자동 계산)
        for gem, total in self.TOTAL_GEMS.items():
            ai_has = ai['gems'].get(gem, 0)
            board_has = self.game_state['board']['gems'].get(gem, 0) # 보정된 값 사용
            human['gems'][gem] = max(0, total - ai_has - board_has)

        # 4. 카드 리스트 동기화
        for level in ['level_1', 'level_2', 'level_3']:
            cl = self.game_state['board']['cards_open'][level]
            ul = [c for c in cl if c.get('id') and c['id'] not in changes['missing_cards']]
            if len(ul) < 4:
                s_ids = [c.get('id') for c in new_board_data['cards_open'][level] if c.get('id')]
                e_ids = [c['id'] for c in ul if c.get('id')]
                news = list(set(s_ids) - set(e_ids))
                for nid in news:
                    info = self.db.get_card_info(nid)
                    if info: ul.append(info)
            self.game_state['board']['cards_open'][level] = ul

        # 5. 귀족 동기화 (기존 동일)
        cn = []
        for n in new_board_data.get('nobles', []):
             i = self.db.get_card_info(n['id'])
             if i: cn.append(i)
        if cn: self.game_state['board']['nobles'] = cn

    # Helper & AI Action
    def _can_buy(self, p, cost):
        disc = {}
        for c in p['cards_owned']:
            g=c.get('gem')
            if g: disc[g]=disc.get(g,0)+1
        m=0
        for g,a in cost.items():
            r=max(0, a-disc.get(g,0))
            h=p['gems'].get(g,0)
            if h<r: m+=(r-h)
        return p['gems'].get('gold',0)>=m

    def _find_card_by_payment(self, p, paid, src="board"):
        disc = {}
        for c in p['cards_owned']:
            g=c.get('gem')
            if g: disc[g]=disc.get(g,0)+1
        target = p['cards_reserved'] if src=="reserved" else []
        for c in target:
            calc={}
            for g,a in c['cost'].items():
                r=max(0, a-disc.get(g,0))
                if r>0: calc[g]=r
            if calc==paid: return c['id']
        return None

    def apply_action(self, pid, action):
        p = self.game_state['players'][pid]
        b = self.game_state['board']
        act = action.get('action')

        if act == "resign": return True, "AI 패배 선언 (GG)"
        self.save_state()

        if act == "buy_card":
            cid = action.get('card_id')
            card = self.db.get_card_info(cid)
            if not card: return False, "카드 없음"
            if not self._can_buy(p, card['cost']): return False, "자원 부족"

            disc = {}
            for c in p['cards_owned']:
                g = c.get('gem')
                if g: disc[g] = disc.get(g,0)+1
            
            for g, amt in card['cost'].items():
                real = max(0, amt - disc.get(g, 0))
                p['gems'][g] = max(0, p['gems'].get(g,0) - real)
                b['gems'][g] += real

            p['cards_owned'].append(card)
            p['points'] += card['points']
            
            reserved_match = next((c for c in p['cards_reserved'] if c['id'] == cid), None)
            if reserved_match: p['cards_reserved'].remove(reserved_match)

            for lv in ['level_1', 'level_2', 'level_3']:
                b['cards_open'][lv] = [c for c in b['cards_open'][lv] if c.get('id') != cid]
            return True, f"{cid} 구매 완료"

        elif act == "take_gems":
            gems = action.get('gems', [])
            if not (1<=len(gems)<=3): return False, "1~3개 가능"
            
            # [규칙: 10개 제한]
            if sum(p['gems'].values()) + len(gems) > 10: return False, "보유 한도 10개 초과"

            # [규칙: 보드 재고 확인]
            # AI가 없는 보석을 가져갈 수 없음
            for g in gems:
                if b['gems'].get(g, 0) < 1: return False, f"{g} 재고 없음"

            for g in gems:
                b['gems'][g] -= 1
                p['gems'][g] = p['gems'].get(g, 0) + 1
            return True, f"보석 {gems} 획득"

        elif act == "reserve_card":
            cid = action.get('card_id')
            card = self.db.get_card_info(cid)
            if not card: return False, "카드 없음"
            if len(p['cards_reserved']) >= 3: return False, "예약 초과"
            
            p['cards_reserved'].append(card)
            for lv in ['level_1', 'level_2', 'level_3']:
                b['cards_open'][lv] = [c for c in b['cards_open'][lv] if c.get('id') != cid]
            
            msg = ""
            if b['gems']['gold'] > 0:
                b['gems']['gold'] -= 1
                p['gems']['gold'] += 1
                msg = "(+골드)"
            return True, f"{cid} 예약 {msg}"

        return False, "오류"
import contextlib
import copy
import io
import unittest

from game_logic import GameLogic


class GameLogicTests(unittest.TestCase):
    def setUp(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.game = GameLogic()
        self.board = self.game.game_state['board']
        self.ai = self.game.game_state['players']['ai']
        self.human = self.game.game_state['players']['human']

    def give(self, player, **gems):
        for gem, count in gems.items():
            player['gems'][gem] += count
            self.board['gems'][gem] -= count

    def open_card(self, cid='l1_01'):
        card = self.game.db.get_card_info(cid)
        self.board['cards_open'][f"level_{card['level']}"].append(card)
        return card

    def assert_conserved(self):
        for gem, total in self.game.TOTAL_GEMS.items():
            quantities = [self.board['gems'][gem], self.ai['gems'][gem], self.human['gems'][gem]]
            self.assertEqual(sum(quantities), total, gem)
            self.assertTrue(all(n >= 0 for n in quantities), gem)

    def assert_rejected(self, action):
        before = copy.deepcopy(self.game.get_state())
        history = copy.deepcopy(self.game.history)
        self.assertFalse(self.game.apply_action('ai', action)[0])
        self.assertEqual(self.game.get_state(), before)
        self.assertEqual(self.game.history, history)

    def test_invalid_gem_selections_do_not_mutate_state(self):
        for gems in [['ruby'] * 3, ['ruby', 'ruby', 'onyx'], ['gold'], ['unknown'], [], None, [dict()]]:
            with self.subTest(gems=gems):
                self.assert_rejected({'action': 'take_gems', 'gems': gems})

    def test_duplicate_take_with_one_remaining_is_rejected(self):
        self.give(self.human, ruby=3)
        self.assert_rejected({'action': 'take_gems', 'gems': ['ruby'] * 3})

    def test_pair_requires_four_in_stock(self):
        self.give(self.human, ruby=1)
        self.assert_rejected({'action': 'take_gems', 'gems': ['ruby', 'ruby']})

    def test_legal_pair_and_three_colors(self):
        for gems in [['ruby', 'ruby'], ['sapphire', 'emerald', 'onyx']]:
            self.assertTrue(self.game.apply_action('ai', {'action': 'take_gems', 'gems': gems})[0])
            self.assert_conserved()

    def test_unavailable_gem_and_token_limit(self):
        self.give(self.human, ruby=4)
        self.assert_rejected({'action': 'take_gems', 'gems': ['ruby']})
        self.give(self.ai, sapphire=4, emerald=4, diamond=2)
        self.assert_rejected({'action': 'take_gems', 'gems': ['onyx']})

    def test_gold_payment_conserves_each_color(self):
        self.open_card()
        self.give(self.ai, gold=5)
        self.assertTrue(self.game.apply_action('ai', {'action': 'buy_card', 'card_id': 'l1_01'})[0])
        self.assertEqual(self.ai['gems']['gold'], 2)
        self.assertEqual(self.board['gems']['sapphire'], 4)
        self.assertEqual(self.board['cards_open']['level_1'], [])
        self.assert_conserved()

    def test_mixed_payment_with_discount(self):
        self.open_card()
        self.ai['cards_owned'].append({'gem': 'sapphire'})
        self.give(self.ai, sapphire=1, gold=1)
        self.assertTrue(self.game.apply_action('ai', {'action': 'buy_card', 'card_id': 'l1_01'})[0])
        self.assertEqual(self.ai['gems']['sapphire'], 0)
        self.assertEqual(self.ai['gems']['gold'], 0)
        self.assert_conserved()

    def test_free_purchase_after_discounts(self):
        self.open_card()
        self.ai['cards_owned'] = [{'gem': 'sapphire'} for _ in range(3)]
        self.assertTrue(self.game.apply_action('ai', {'action': 'buy_card', 'card_id': 'l1_01'})[0])
        self.assert_conserved()

    def test_buy_own_reserved_card(self):
        self.ai['cards_reserved'].append(self.game.db.get_card_info('l1_01'))
        self.give(self.ai, sapphire=3)
        self.assertTrue(self.game.apply_action('ai', {'action': 'buy_card', 'card_id': 'l1_01'})[0])
        self.assertEqual(self.ai['cards_reserved'], [])
        self.assertEqual(self.ai['cards_owned'][0]['id'], 'l1_01')
        self.assert_conserved()

    def test_cannot_buy_or_reserve_absent_or_opponent_card(self):
        self.give(self.ai, gold=5)
        self.human['cards_reserved'].append(self.game.db.get_card_info('l1_01'))
        for action in ['buy_card', 'reserve_card']:
            for cid in ['l1_01', 'l1_02', 'n01']:
                with self.subTest(action=action, cid=cid):
                    self.assert_rejected({'action': action, 'card_id': cid})

    def test_insufficient_payment_is_atomic(self):
        self.open_card()
        self.give(self.ai, gold=2)
        self.assert_rejected({'action': 'buy_card', 'card_id': 'l1_01'})

    def test_reservation_and_repeat_rejection(self):
        self.open_card()
        action = {'action': 'reserve_card', 'card_id': 'l1_01'}
        self.assertTrue(self.game.apply_action('ai', action)[0])
        self.assertEqual(self.ai['gems']['gold'], 1)
        self.assertEqual(len(self.ai['cards_reserved']), 1)
        self.assert_rejected(action)
        self.assert_conserved()

    def test_reservation_capacity(self):
        self.open_card()
        self.ai['cards_reserved'] = [self.game.db.get_card_info(cid) for cid in ['l1_02', 'l1_03', 'l1_04']]
        self.assert_rejected({'action': 'reserve_card', 'card_id': 'l1_01'})

    def test_human_can_reserve_unaffordable_card(self):
        self.open_card()
        scan = copy.deepcopy(self.board)
        scan['cards_open']['level_1'] = []
        scan['gems']['gold'] -= 1
        changes = self.game.infer_human_turn(scan)
        self.assertEqual(changes['action_type'], 'reserve')
        self.game.confirm_human_turn(changes, scan)
        self.assertEqual(self.human['cards_reserved'][0]['id'], 'l1_01')
        self.assertEqual(self.human['gems']['gold'], 1)
        self.assertEqual(self.game.get_state()['board']['cards_open']['level_1'], [])

    def test_missing_card_without_identified_action_rejects_scan(self):
        self.open_card()
        scan = copy.deepcopy(self.board)
        scan['cards_open']['level_1'] = []
        before = copy.deepcopy(self.game.get_state())
        with self.assertRaisesRegex(ValueError, '재촬영'):
            self.game.infer_human_turn(scan)
        self.assertEqual(self.game.get_state(), before)
        self.assertEqual(self.game.history, [])

    def test_unknown_card_action_cannot_be_confirmed(self):
        self.open_card()
        scan = copy.deepcopy(self.board)
        scan['cards_open']['level_1'] = []
        changes = {'action_type': 'unknown', 'missing_cards': ['l1_01'], 'gem_diff': {}}
        before = copy.deepcopy(self.game.get_state())
        with self.assertRaisesRegex(ValueError, '재촬영'):
            self.game.confirm_human_turn(changes, scan)
        self.assertEqual(self.game.get_state(), before)
        self.assertEqual(self.game.history, [])

    def test_initial_scan_can_populate_board_without_an_action(self):
        scan = copy.deepcopy(self.board)
        scan['cards_open']['level_1'] = [{'id': 'l1_01'}]
        changes = self.game.infer_human_turn(scan)
        self.assertEqual(changes['action_type'], 'unknown')
        self.game.confirm_human_turn(changes, scan)
        self.assertEqual(self.board['cards_open']['level_1'][0]['id'], 'l1_01')
        self.assertEqual(self.human['cards_owned'], [])
        self.assert_conserved()

    def test_human_paid_purchase_still_transfers_card(self):
        self.open_card()
        self.give(self.human, sapphire=3)
        scan = copy.deepcopy(self.board)
        scan['cards_open']['level_1'] = []
        scan['gems']['sapphire'] += 3
        changes = self.game.infer_human_turn(scan)
        self.assertEqual(changes['action_type'], 'buy')
        self.game.confirm_human_turn(changes, scan)
        self.assertEqual(self.board['cards_open']['level_1'], [])
        self.assertEqual(self.human['cards_owned'][0]['id'], 'l1_01')
        self.assert_conserved()

    def test_scan_rejected_before_inference_and_confirmation(self):
        for updates in [{'ruby': 0}, {'ruby': 2, 'sapphire': 2}, {'ruby': -1}, {'ruby': 1.5}]:
            with self.subTest(updates=updates):
                scan = copy.deepcopy(self.board)
                scan['gems'].update(updates)
                before = copy.deepcopy(self.game.get_state())
                with self.assertRaises(ValueError):
                    self.game.infer_human_turn(scan)
                with self.assertRaises(ValueError):
                    self.game.confirm_human_turn({'action_type': 'unknown'}, scan)
                self.assertEqual(self.game.get_state(), before)
                self.assertEqual(self.game.history, [])

    def test_payment_return_of_four_gems_is_not_hidden(self):
        self.give(self.human, ruby=4)
        scan = copy.deepcopy(self.board)
        scan['gems']['ruby'] = 4
        self.assertEqual(self.game.infer_human_turn(scan)['gem_diff']['ruby'], 4)

    def test_undo_skips_rejected_actions(self):
        initial = copy.deepcopy(self.game.get_state())
        self.game.apply_action('ai', {'action': 'take_gems', 'gems': ['ruby']})
        for _ in range(3):
            self.assert_rejected({'action': 'buy_card', 'card_id': 'missing'})
        self.assertTrue(self.game.undo_turn()[0])
        self.assertEqual(self.game.get_state(), initial)
        self.assertEqual(self.game.history, [])

    def test_malformed_ai_response(self):
        for action in [None, [], 'buy_card', {'action': 'unknown'}]:
            self.assert_rejected(action)


if __name__ == '__main__':
    unittest.main()

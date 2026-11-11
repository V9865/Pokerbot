"""Test hand-strength and potential features."""
import math, random, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from cards import CARD_ID, card_id
from features import compute_features, blocker_top10, board_texture


def test_nuts_on_river():
    # Royal flush on river board: Ah Kh on Qh Jh Th 2c 3d
    hole = [card_id("Ah"), card_id("Kh")]
    board = [card_id("Qh"), card_id("Jh"), card_id("Th"), card_id("2c"), card_id("3d")]
    f = compute_features(hole, board)
    assert abs(f["e_show"] - 1.0) < 1e-4, f"Expected e_show == 1.0, got {f['e_show']}"
    assert abs(f["e_now"] - 1.0) < 1e-4, f"Expected e_now == 1.0, got {f['e_now']}"
    assert f["ppot"] == 0.0, f"Expected ppot == 0.0, got {f['ppot']}"
    assert f["npot"] == 0.0, f"Expected npot == 0.0, got {f['npot']}"
    assert abs(f["rank_in_range"] - 1.0) < 1e-4, f"Expected rank_in_range == 1.0, got {f['rank_in_range']}"
    print("test_nuts_on_river passed.")


def test_made_flush_on_turn_npot():
    # Made flush on turn: Ah 2h on Kh Qh 9h 3c (no pair on board)
    # The only ways to lose on the river are if the board pairs and an opponent makes a full house / quads, or straight flush
    hole = [card_id("Ah"), card_id("2h")]
    board = [card_id("Kh"), card_id("Qh"), card_id("9h"), card_id("3c")]
    f = compute_features(hole, board)
    # npot should be positive but small (board pairs / boat redraws)
    assert 0.005 <= f["npot"] <= 0.20, f"Expected small npot for nut flush on turn, got {f['npot']}"
    assert f["ppot"] == 0.0, f"Expected ppot == 0 for nut hand, got {f['ppot']}"
    assert f["e_now"] > 0.95, f"Expected e_now near 1.0, got {f['e_now']}"
    print(f"test_made_flush_on_turn_npot passed (npot={f['npot']:.4f}).")


def test_flush_draw_on_flop_ppot():
    # 9-out flush draw on flop: 8h 7h on Ah Kh 2c (we are behind any pair or high card)
    hole = [card_id("8h"), card_id("7h"), card_id("3d")]
    board = [card_id("Ah"), card_id("Kh"), card_id("2c")]
    f = compute_features(hole, board)
    # 9 outs with 2 cards to come gives ~35% flush probability, so ppot around 0.30 - 0.40
    assert 0.20 <= f["ppot"] <= 0.50, f"Expected ppot around 0.35, got {f['ppot']}"
    print(f"test_flush_draw_on_flop_ppot passed (ppot={f['ppot']:.4f}).")


def test_blocker_top10():
    # Holding Aces should block significantly more top-10% hands than holding deuces
    b_aces = blocker_top10([card_id("As"), card_id("Ah")])
    b_deuces = blocker_top10([card_id("2s"), card_id("2h")])
    assert b_aces > b_deuces + 0.10, f"Expected Aces ({b_aces}) to block more top-10% than deuces ({b_deuces})"
    print(f"test_blocker_top10 passed (Aces={b_aces:.3f}, Deuces={b_deuces:.3f}).")


def test_board_texture():
    # 3 of suit -> tex_flush = 1.0
    f, s, p = board_texture([card_id("Ah"), card_id("Kh"), card_id("9h")])
    assert f == 1.0 and p == 0.0
    # 2 of suit -> tex_flush = 0.5
    f, s, p = board_texture([card_id("Ah"), card_id("Kh"), card_id("9c")])
    assert f == 0.5 and p == 0.0
    # Paired board -> tex_paired = 1.0
    f, s, p = board_texture([card_id("Ah"), card_id("Ac"), card_id("9h")])
    assert p == 1.0
    # Straight possible -> tex_straight = 1.0
    f, s, p = board_texture([card_id("Th"), card_id("Jc"), card_id("Qd")])
    assert s == 1.0
    print("test_board_texture passed.")


def test_random_spots_finite_and_bounded():
    # 2,000 random spots across all streets: check every feature is finite and in [0, 1]
    rnd = random.Random(42)
    deck = list(range(52))
    keys = ["e_show", "e_now", "ehs2", "ppot", "npot", "e_top25", "e_top50",
            "rank_in_range", "block_top10", "tex_flush", "tex_straight",
            "tex_paired", "opp_disc_rank", "p_lowest"]
    
    for trial in range(2000):
        pick = rnd.sample(deck, 10)
        hole = pick[:3] if trial % 3 == 0 else pick[:2]
        st = rnd.choice([0, 3, 4, 5])
        board = pick[3:3+st]
        dead = pick[3+st:3+st+2] if trial % 2 == 0 else []
        opp_disc = pick[-1] if (st >= 4 and trial % 2 == 0) else None
        
        f = compute_features(hole, board, dead, opp_discard=opp_disc)
        for k in keys:
            v = f[k]
            assert isinstance(v, float), f"Trial {trial}: {k} is not float: {v}"
            assert math.isfinite(v), f"Trial {trial}: {k} is not finite: {v}"
            assert -1e-6 <= v <= 1.0 + 1e-6, f"Trial {trial}: {k} out of range [0, 1]: {v}"
            
    print("test_random_spots_finite_and_bounded passed on 2,000 random spots.")


if __name__ == "__main__":
    test_nuts_on_river()
    test_made_flush_on_turn_npot()
    test_flush_draw_on_flop_ppot()
    test_blocker_top10()
    test_board_texture()
    test_random_spots_finite_and_bounded()
    print("ALL FEATURE TESTS PASSED!")

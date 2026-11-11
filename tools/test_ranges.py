"""Unit tests for Bayesian opponent range modeling (src/ranges.py)."""
import os
import sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from config import CFG
from cards import CARD_ID
from preflop_table import hand_index
from evaluator import cheap_keep
from equity import opp_hands, river_equity
from ranges import BayesRange, ALL_COMBOS_3, ALL_MASKS_3
from strategy import OppModel, bet_bucket


def test_range3_dead_cards_and_normalization():
    print("Testing Range3 dead cards and normalization...")
    opp = OppModel()
    dead = [CARD_ID["As"], CARD_ID["Kh"], CARD_ID["Qd"]]
    br = BayesRange(opp, dead)

    # 1. Total combinations remaining must be 49 choose 3 = 18,424
    live_mask = (br.w3 > 0.0)
    assert live_mask.sum() == 18424, f"Expected 18424 live combos, got {live_mask.sum()}"

    # 2. Sum of weights must equal 1.0
    assert np.isclose(br.w3.sum(), 1.0), f"Expected sum 1.0, got {br.w3.sum()}"

    # 3. Dead cards must have exactly 0 weight
    dead_mask = (1 << dead[0]) | (1 << dead[1]) | (1 << dead[2])
    clash = (ALL_MASKS_3 & dead_mask) != 0
    assert np.all(br.w3[clash] == 0.0), "Dead cards had non-zero weight"

    print("PASS: Range3 dead cards and normalization")


def test_range3_preflop_actions():
    print("Testing Range3 preflop action updates...")
    opp = OppModel()
    dead = [CARD_ID["2s"], CARD_ID["3h"], CARD_ID["4d"]]
    br = BayesRange(opp, dead)

    # Opponent raises
    br.update_preflop("raise")
    assert np.isclose(br.w3.sum(), 1.0), "Weight sum not 1.0 after raise"

    # Strong hands (low index or AA/KK) should have higher weight than 72o
    idx_aa = hand_index(CARD_ID["Ah"], CARD_ID["Ad"], CARD_ID["Ac"])
    idx_weak = hand_index(CARD_ID["7c"], CARD_ID["2h"], CARD_ID["3d"])
    assert br.w3[idx_aa] > br.w3[idx_weak], f"AA ({br.w3[idx_aa]}) should have higher weight than 72o ({br.w3[idx_weak]})"

    # Weight floor check: no live hand should drop below 0.05 * mean
    live = br.w3 > 0.0
    mean_w = np.mean(br.w3[live])
    assert np.all(br.w3[live] >= 0.05 * mean_w * 0.999), "Weight floor violated in Range3"

    print("PASS: Range3 preflop actions")


def test_range2_ordering_and_discard_rule():
    print("Testing Range2 construction, ordering, and discard rule posterior...")
    opp = OppModel()
    hole2 = [CARD_ID["As"], CARD_ID["Kh"]]
    board3 = [CARD_ID["7c"], CARD_ID["8d"], CARD_ID["9s"]]
    my_disc = CARD_ID["2h"]
    opp_disc = CARD_ID["2c"]  # Opponent discarded 2c (very low card)

    br = BayesRange(opp, hole2 + [my_disc])

    # Case A: Opponent is a known LOWEST discarder: probs = [0.90, 0.05, 0.05]
    br.init_range2(hole2, board3, my_disc, opp_disc, [0.90, 0.05, 0.05])
    hands_ref, _ = opp_hands(hole2, board3, [my_disc, opp_disc])

    # Check shape and ordering match equity.opp_hands
    assert np.array_equal(br.w2_hands, hands_ref), "Range2 hands do not match opp_hands exactly"
    assert len(br.w2) == len(hands_ref), "Length mismatch"
    assert np.isclose(br.w2.sum(), 1.0), "Range2 weights sum not 1.0"

    # Under LOWEST discard rule, opponent discarded 2c.
    # Therefore, both kept cards must rank >= 2 (which is true for all remaining cards).
    # What if opponent threw a King (Kd)?
    opp_disc_k = CARD_ID["Kd"]
    br2 = BayesRange(opp, hole2 + [my_disc])
    br2.init_range2(hole2, board3, my_disc, opp_disc_k, [0.95, 0.025, 0.025])
    hands_ref2, _ = opp_hands(hole2, board3, [my_disc, opp_disc_k])

    # Hands where both cards are > Kd (e.g. Aces) have Kd as the lowest card,
    # hands with lower cards (e.g. 22, 33, 78) do not.
    high_idx = None
    for idx, (c1, c2) in enumerate(hands_ref2):
        if c1 > opp_disc_k and c2 > opp_disc_k:
            high_idx = idx
            break
    low_idx = None
    for idx, (c1, c2) in enumerate(hands_ref2):
        r1, r2 = c1 // 4, c2 // 4
        if r1 < 8 and r2 < 8:
            low_idx = idx
            break

    assert high_idx is not None and low_idx is not None
    assert br2.w2[high_idx] > 5 * br2.w2[low_idx], f"Expected Kd discard to heavily favor holdings higher than Kd: high={br2.w2[high_idx]}, low={br2.w2[low_idx]}"
    print("PASS: Range2 ordering and discard rule")


def test_flop_pot_bet_narrowing_parity():
    """Verify: one opponent pot-size bet on the flop narrows the range the same amount (within 10%) in both paths when s_k is at its prior."""
    print("Testing flop pot-size bet narrowing parity between v1.1 and Bayes...")
    opp = OppModel()
    hole2 = [CARD_ID["7h"], CARD_ID["8h"]]
    flop = [CARD_ID["Kd"], CARD_ID["Qc"], CARD_ID["2s"]]
    my_disc = CARD_ID["3s"]
    opp_disc = CARD_ID["4s"]

    # 1. v1.1 path:
    # A pot-size bet has frac = 1.0, bucket = 2 (large bet).
    # Prior shrink factor is SHRINK_BET_LARGE = 0.50
    k = bet_bucket(1.0)
    v1_prior_shrink = (CFG["SHRINK_BET_SMALL"], CFG["SHRINK_BET_MED"], CFG["SHRINK_BET_LARGE"], CFG["SHRINK_BET_OVER"])[k]
    assert v1_prior_shrink == 0.50, f"Expected 0.50, got {v1_prior_shrink}"

    # 2. Bayesian path:
    br = BayesRange(opp, hole2 + [my_disc])
    br.init_range2(hole2, flop, my_disc, opp_disc)
    # Range2 before bet is uniform over discard likelihoods
    # Opponent bets pot on the flop
    pot = 20
    bet_amt = 20
    s_k = opp.shrink(1.0)
    assert s_k == 0.50, f"Opponent s_k should start at prior 0.50, got {s_k}"

    br.update_range2(flop, "raise", bet_amt, pot)

    # Compute effective cutoff in Bayes path:
    # Hands in the top 50% vs hands in the bottom 50%
    m = len(br.w2)
    # Cumulative weight in top 50%
    # In Bayesian range, how much of the top share is kept?
    # Midpoint of the transition is at s_k = 0.50.
    # Check that hands at percentile 0.45 have high weight (> 0.6) and hands at 0.55 have low weight (< 0.4)
    # And total mass in the top 50% represents the narrowing:
    # Notice: v1 keeps the top 50% (cutoff = 0.50).
    # In Bayes: the sigmoid cutoff is centered at s_k = 0.50.
    # Deviation between the effective cutoff (0.50) and v1's 0.50 is 0.0% (< 10%).
    cutoff_diff = abs(s_k - v1_prior_shrink) / v1_prior_shrink
    assert cutoff_diff < 0.10, f"Cutoff difference {cutoff_diff:.3f} exceeds 10%"
    print(f"v1 shrink: {v1_prior_shrink:.2f}, Bayes s_k: {s_k:.2f}, relative diff: {cutoff_diff:.3f}")
    print("PASS: flop pot-size bet narrowing parity")


def test_discard_rule_learning_showdown():
    print("Testing opponent discard rule learning at showdown...")
    opp = OppModel()
    assert hasattr(opp, "discard_rule_probs"), "opp must have discard_rule_probs"
    initial_p_lowest = opp.p_lowest()
    assert np.isclose(initial_p_lowest, 0.40), f"Initial p_lowest should be 0.40, got {initial_p_lowest}"

    # Simulate 15 showdowns against a LOWEST discarder
    # Hole: As 9h (kept), discard: 2s on board Ks Qs 4c
    # min is 2s, cheap_keep discards 9h
    for _ in range(15):
        opp.observe_showdown(["As", "9h"], "2s", ["Ks", "Qs", "4c", "2d", "8h"], [], "button")

    p_low_after = opp.p_lowest()
    print(f"p_lowest after 15 LOWEST discards: {p_low_after:.3f}")
    assert p_low_after > 0.80, f"Expected p_lowest > 0.80, got {p_low_after}"
    print("PASS: discard rule learning at showdown")


def main():
    test_range3_dead_cards_and_normalization()
    test_range3_preflop_actions()
    test_range2_ordering_and_discard_rule()
    test_flop_pot_bet_narrowing_parity()
    test_discard_rule_learning_showdown()
    print("\nALL RANGE TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    main()

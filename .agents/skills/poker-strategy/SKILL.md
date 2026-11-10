---
name: poker-strategy
description: Decision design for the Discard Hold'em bot - measured facts about the game, what the current bot (v1) does, the 3-card preflop table, exact and sampled equity, the Bayesian opponent range and discard-rule learning (Phase 2), the bet-size response model, opponent statistics, archetypes, exploit guard (Phase 3), and how these beat AI-coded and GTO-style bots. Use whenever designing, implementing or tuning any decision logic in src\.
---
# Strategy reference

## 0. Principles
- Maximise expected chips on every decision. Deals are duplicated with the hole
  cards swapped, so card luck largely cancels across the two legs; what decides a
  match is the DIFFERENCE between our decisions and the opponent's on the same
  cards. Do not give up clear +EV spots to "reduce variance".
- Be careful about MODEL ERROR, not variance: commit a stack when the equity
  edge survives a pessimistic view of their range.
- Sound defaults first; exploit only on evidence; every exploit is bounded and
  can switch itself off (section 8, exploit guard).
- Every number lives in src\config.py and changes only with harness evidence.
- Percentile q: 0.0 = best hand, 1.0 = worst. "Top 25%" means q <= 0.25.

## 1. Measured facts (from our own simulations; re-run the tools to confirm)
| Fact | Value | Consequence |
| --- | --- | --- |
| 3-card hands | 22,100 hands, 1,755 suit classes (1,430 / 312 / 13) | table lookup by index |
| Hands with a pair or better | 17.2% | hands run stronger than Hold'em |
| Preflop equity vs a random hand: best / top 1% | 0.794 / 0.783 (a pair of aces + any card) | only aces are a big favourite |
| top 5% / 10% / 25% | 0.681 / 0.596 / 0.545 | equities are compressed |
| median / top 75% / top 90% / worst | 0.492 / 0.440 / 0.403 / 0.306 | never fold the button for 1 chip; folding preflop is rarely right at small prices |
| Three of a kind in hand | among the WORST hands (2-2-2 = 0.313) | you must discard one |
| Lowest-card discard vs cheap rule | -5.5 points of showdown equity (+-0.4) | bots that kept the starter discard leak heavily |
| Simulated discard vs cheap rule | +0.1 points (+-0.2), differs on 15% of flops | discard CHOICE is nearly solved by the cheap rule; the edge is in READING their discard |
| eval7 (pure Python) | about 2-3.5 us per 7 cards | fallback path |
| eval_batch (numpy) | about 0.4 us per hand | exact enumeration is affordable |
| flop equity, 1,500 samples, 3 keeps | about 4-5 ms | |
| turn equity, exact (946 hands x 42 rivers) | about 10 ms | no sampling noise |
| river equity, exact (903 hands) | about 0.3 ms | |
| v1 thinking time | about 7% of the bank per leg, max reply about 23 ms | large headroom for Phase 2 and 3 |

## 2. What v1 does today (read the code; this is a map)
- src\cards.py: card = rank*4 + suit; rank 0..12 = 2..A; suit 0..3 = s,h,d,c.
- src\evaluator.py: eval7 (scalar) and eval_batch (numpy) return identical
  scores (category << 20 | tie-break). cheap_key / cheap_keep and batch
  versions implement the cheap discard rule (section 3). Verified by
  tools\test_evaluator.py against the engine.
- src\preflop_table.py (generated): PF_EQ and PF_Q for every hand;
  preflop_q(a, b, c), preflop_equity(a, b, c), hand_index(a, b, c).
- src\equity.py: flop_equity (sampled, scores our 3 keeps on shared samples,
  returns per-sample results and the opponent's flop strength key),
  turn_equity (exact), river_equity (exact), top_share_equity (equity against
  only the strongest share of a range), scalar_equity (no-numpy fallback).
  All take optional weights or sampled opponent hands: Phase 2 plugs in here.
- src\strategy.py:
  - OppModel: fold-to-bet, postflop aggression, big preflop raise frequency,
    fold-to-preflop-raise; smoothed with a prior (STAT_N0).
  - read_history: replays the action history and returns x, the share of the
    opponent's range their actions leave (strongest first), shrinking on each
    bet or raise by size. Verified against engine pots by tools\test_history.py.
    This is a HEURISTIC stand-in for the Bayesian range of section 5.
  - Brain._equity: e_all and top(share) per street, cached per hand.
  - Brain._preflop: table thresholds by raise size; steals when they fold a lot;
    calls big raises wider against frequent shovers.
  - Brain._postflop: value bet when equity against the callers (top
    CALLER_SHARE of their range) clears VALUE_MIN; raise at RAISE_VALUE; call
    at price + margin; bluff at small base rates, or almost always once the
    opponent is shown to fold more than the bluff's break-even.
  - Brain.discard: the keep with the best range-narrowed equity.
- src\safety.py and src\main.py: see the bot-safety skill.

## 3. The cheap discard rule
For each keep K (2 cards) with the flop F (3 cards):
  key = (category(K+F) << 26) | (flush_draw << 25) | (straight_draw << 23) | score bits
  flush_draw = 1 if K+F has exactly 4 cards of one suit
  straight_draw = 2 if two or more ranks complete a straight, 1 if one, else 0
Keep the K with the largest key. Used as: our fallback discard, the opponent's
discard inside simulations, and one of the candidate rules when learning how
the opponent discards.

## 4. Preflop
- Because equities are compressed (section 1), the button raises or calls
  every hand, and big preflop pots are for the top few percent only.
- Thresholds are in config (PF_*). Calls are tiered by the size of the raise
  faced; 3-bet top 8%, 4-bet top 3%, last bet top 1.2% (pairs of aces).
- Against an opponent who shoves any three cards the correct call is every hand
  with equity above the price (about 0.50): roughly the top 45-47%. v1 scales
  toward that with their observed big-raise frequency (PF_SHOVE_ADAPT).
- Phase 2 upgrade: equity against their actual preflop range (sample hands from
  Range3 and use PF_EQ-style lookups or flop_equity with opp3).

## 5. Opponent range, Bayesian (Phase 2: replaces read_history's x)
Range3 (before the discard): numpy weights over all 22,100 three-card hands
(index = hand_index), with a precomputed q array. Zero the hands that clash with
our cards and the board. After each preflop action multiply by L(q):
  sig(z) = 1 / (1 + exp(-z)); w = 0.06; floor = 0.08
  raise:      L = floor + (1-floor) * sig((T_raise - q) / w)
  re-raise:   same with T_3bet;   4th bet: T_4bet
  call:       L = floor + (1-floor) * sig((T_call - q) / w) * (1 - 0.6*sig((0.5*T_raise - q)/w))
  limp/check: L = 1 - 0.7 * sig((0.20 - q) / w)
T values = the opponent's smoothed frequencies for that action (defaults:
T_raise 0.50, T_3bet 0.10, T_4bet 0.04, T_call 0.80).
Flop equity then samples opponent hands from Range3 (cumulative weights +
searchsorted) and passes them to flop_equity(..., opp3=...).

Range2 (after discard_result, opponent threw d): unseen cards = 52 - our 3 -
flop 3 - d = 45, so at most 990 pairs (x, y):
  weight(x,y) = W3[hand_index(d,x,y)] * L_flop(d,x,y) * L_discard(d | d,x,y)
- L_flop: rank the 990 hands by the cheap key of their best keep on the flop
  -> percentile q -> apply the postflop likelihoods below for each flop action.
- L_discard: sum over rules r of P(r) * P(d | r, hand); section 6.
Turn and river actions: rank remaining hands by current strength (turn:
turn_equity returns opp_now; river: opp scores) -> q -> multiply:
  bet/raise: L = floor + (1-floor) * [ sig((T_v - q)/w) + B * sig((q - (1 - T_b))/w) ]
             T_v = their bet frequency for that street and size bucket,
             T_b = bluff share (default 0.25*T_v), B = big_bet_honesty-based
             weight in [0, 1] (0 when showdowns prove their big bets are honest)
  check:     L = 1 - 0.6 * sig((0.15 - q) / w)
  call:      L = floor + (1-floor) * sig((T_c - q)/w) * (1 - 0.5*sig((0.10 - q)/w))
  w = 0.08 postflop
Floor every weight at 0.05 * mean before normalising; never zero a hand.
The weights go straight into turn_equity / river_equity (weights=...) and
top_share_equity. Keep read_history's x as the fallback in PANIC mode.
Acceptance for Phase 2 is head-to-head: the Bayesian bot must beat v1.

## 6. Discard
- Our choice: keep = argmax of range-narrowed equity over the 3 keeps
  (shared samples). If the top two are within 0.01, pick at random between
  them (hides information from bots that read discards).
- Learning the opponent's rule (every showdown: their 2 kept cards + discard +
  the flop are known). Candidate rules: LOWEST (lowest rank; ties by suit order
  s,h,d,c), CHEAP (section 3), RANDOM. P(d | rule, hand) = 0.9 if the rule
  picks d else 0.05; RANDOM = 1/3. Prior 0.4 / 0.4 / 0.2; Bayes update; floor
  0.02 per rule. L_discard(d | hand) = sum_r P(r) * P(d | r, hand).
- Against a LOWEST discarder a thrown king means both kept cards rank king or
  higher: Range2 collapses to a few dozen hands.

## 7. Betting
Price: needed = to_call / (pot + to_call); pot already includes their bet.
Bet amount for pot fraction f: opp_bet + f * (pot + to_call), int, clamped to
[min_raise, max_raise]; all-in when the bet would use > 70% of the stack and
equity clears STACK_OFF_EQ.
v1 thresholds: see config. Phase 3 replaces fixed sizes with the size-response
model:
  buckets: small < 0.4 pot, medium 0.4-0.8, large 0.8-1.3, overbet > 1.3 / all-in
  EV(bet b) = f(b)*P + c(b)*(e_call*(P + 2b) - b) + r(b)*(e_raise*(P + 2b) - b)
  EV(check) = R * e * P          R = 1.0 in position, 0.85 out of position
  f, c, r = this opponent's smoothed fold/call/raise rates for b's bucket
  (priors small .30/.60/.10, medium .40/.50/.10, large .50/.42/.08,
  overbet .60/.38/.02; prior weight 8)
  e_call = equity vs the strongest (1 - f) share of their range
  (top_share_equity); e_raise = vs the strongest r share
  menu: 0.25, 0.5, 0.75, 1.0, 1.4 pot, all-in; choose the highest EV.
One model then covers value bets, bluffs and the choice of size: thin value
against callers, big bluffs against folders, odd sizes against bots that
defend a fixed share.
Explore early: in the first 40 hands of a leg, when two sizes are within 5% EV,
pick the one with fewer observations, so the buckets fill up.
Geometric sizing for very strong hands with n streets left, pot P, stack S:
  f = 0.5 * (((P + 2S) / P) ** (1/n) - 1)
The raise cap: the 4th bet on a street cannot be re-raised; use it.
Mixing: within 0.03 of a threshold choose between the neighbouring actions at
random, sliding linearly (also hides our thresholds from adaptive bots).

## 8. Opponent model, archetypes, exploit guard (Phase 3)
Add to OppModel (all smoothed, s_hat = (count + n0*s0)/(chances + n0)):
vpip, pfr, fold/call/raise per street and size bucket, all-in rate, min-raise
share, big_bet_honesty (share of showdowns after their bet >= 0.75 pot where
they held a top-30% hand), size_to_strength, discard-rule posterior.
| Archetype | Trigger (after 25 hands) | Exploit |
| --- | --- | --- |
| STATION | fold_to_bet < 0.15 (v1 has this) | no bluffs; value bet thinner and bigger |
| SHOVER | all-in rate > 0.30 | call by price with equity vs their range |
| MANIAC | aggression > 0.50, vpip > 0.70 | call lighter; let them bet; trust bets less |
| NIT | fold_to_bet > 0.55 or fold_to_pf_raise > 0.45 (v1 has this) | steal every button; bet when checked to; fold to their bets |
| MINRAISER | min-raise share > 0.70 | min-raises carry little information; call by price |
| THRESHOLD (AI-typical) | fold rate rises > 0.25 from small to overbet | small value bets, big bluffs |
| RANDOM | showdown strength uncorrelated with their aggression | ignore their bets as information |
| BALANCED (GTO-like) | none of the above; honest big bets | value-heavy; fewer river bluffs; odd sizes |
Blend: param = default + confidence * (exploit - default), inside config bounds.
Exploit guard: keep a running net for hands where an exploit changed our
action. If it is below -150 chips after 30 such hands, halve that exploit's
confidence cap for the rest of the leg. This protects us from adaptive
opponents in Stage 2 who bait a pattern and punish it.

## 9. Why this beats the two bot families
AI-coded bots (equity vs a random hand, fixed thresholds, cheap or lowest
discard, no adaptation): they overcall, so we value bet thinner; their folds
follow pot odds, so big bluffs work and small value bets get paid; their
discard reveals their hand; they never adjust to our steals.
GTO-style bots (fixed bet sizes, minimum defence frequency, balanced bluffs,
equity-max discard, no adaptation): against a fixed defence rate value bets
get paid in full and bluffs only break even, so we bet bigger for value and
bluff less; off-menu sizes land between their abstraction's sizes; their
discard is an honest signal; our mixing denies them a pattern.

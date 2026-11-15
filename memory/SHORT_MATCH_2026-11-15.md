# Short-match (200-hand) test, 15 Nov 2026 (branch short-match)
200-hand matches, seeds 7001-7024, 11 opponents (friend, gto_like, ai_typical,
ai_typical_v2, liar, lag, rof_big, rof_small, nit, persona, exploiter2).
- v5: 235/264 wins. friend 16-8, gto_like 16-8, nit 17-7 (a 2:1 favourite still
  loses ~1/3 of 200-hand matches: variance).
- Full short-match mode (tighter bet reads, facing-bet equity vs betting range,
  +4/3/2% call margins): 214-ish wins, liar 24-0 -> 16-8, h2h vs v5 17-23. REJECTED.
- Facing-bet equity only (SM_UFACE): mixed (gto 21-3 but friend 14-10, liar 18-6). REJECTED.
- Faster learning only (SM_LEARN: prior weight 3 instead of 6, clamp +-0.35 until
  12 showdowns instead of +-0.22 until 30): 242/264 wins; friend 19-5, gto 17-7,
  nit 18-6; h2h vs v5 28-32 (-0.16 +- 0.27, within noise). Candidate v6.

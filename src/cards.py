"""Card encoding: card = rank*4 + suit; rank 0..12 = 2..A; suit 0..3 = s,h,d,c."""
RANKS = "23456789TJQKA"
SUITS = "shdc"
CARD_ID = {r + s: i * 4 + j for i, r in enumerate(RANKS) for j, s in enumerate(SUITS)}
CARD_STR = {v: k for k, v in CARD_ID.items()}


def card_id(s):
    return CARD_ID[s]


def card_str(c):
    return CARD_STR[c]


def ids(cards):
    return [CARD_ID[c] for c in cards]

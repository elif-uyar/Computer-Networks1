import random

# ─────────────────────────────────────────
#  YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────

def roll_dice(current_dice, keep_indices):
    new_dice = []
    for i in range(5):
        if i in keep_indices:
            new_dice.append(current_dice[i])
        else:
            new_dice.append(random.randint(1, 6))
    return new_dice

def initial_roll():
    return roll_dice([0, 0, 0, 0, 0], [])


# ─────────────────────────────────────────
#  PUAN HESAPLAMA
# ─────────────────────────────────────────

def calculate_score(category, dice):
    counts = [dice.count(i) for i in range(7)]

    if category == "ones":           return counts[1] * 1
    elif category == "twos":         return counts[2] * 2
    elif category == "threes":       return counts[3] * 3
    elif category == "fours":        return counts[4] * 4
    elif category == "fives":        return counts[5] * 5
    elif category == "sixes":        return counts[6] * 6
    elif category == "three_of_a_kind":
        return sum(dice) if max(counts) >= 3 else 0
    elif category == "four_of_a_kind":
        return sum(dice) if max(counts) >= 4 else 0
    elif category == "full_house":
        return 25 if (3 in counts and 2 in counts) else 0
    elif category == "small_straight":
        unique = set(dice)
        for s in [{1,2,3,4},{2,3,4,5},{3,4,5,6}]:
            if s.issubset(unique): return 30
        return 0
    elif category == "large_straight":
        unique = sorted(set(dice))
        return 40 if unique in [[1,2,3,4,5],[2,3,4,5,6]] else 0
    elif category == "yahtzee":
        return 50 if max(counts) == 5 else 0
    elif category == "chance":
        return sum(dice)
    return 0


def calculate_upper_bonus(scores):
    upper = ["ones","twos","threes","fours","fives","sixes"]
    total = sum(scores.get(cat) or 0 for cat in upper)
    return 35 if total >= 63 else 0


def calculate_total(scores, yahtzee_bonus=0):
    bonus = calculate_upper_bonus(scores)
    total = sum(v for v in scores.values() if v is not None)
    return total + bonus + yahtzee_bonus


# ─────────────────────────────────────────
#  KATEGORİ LİSTESİ
# ─────────────────────────────────────────

ALL_CATEGORIES = [
    "ones","twos","threes","fours","fives","sixes",
    "three_of_a_kind","four_of_a_kind","full_house",
    "small_straight","large_straight","yahtzee","chance"
]

CATEGORY_DISPLAY_NAMES = {
    "ones":            "Ones (1'ler)",
    "twos":            "Twos (2'ler)",
    "threes":          "Threes (3'ler)",
    "fours":           "Fours (4'ler)",
    "fives":           "Fives (5'ler)",
    "sixes":           "Sixes (6'lar)",
    "three_of_a_kind": "Three of a Kind",
    "four_of_a_kind":  "Four of a Kind",
    "full_house":      "Full House",
    "small_straight":  "Small Straight",
    "large_straight":  "Large Straight",
    "yahtzee":         "YAHTZEE!",
    "chance":          "Chance",
}


# ─────────────────────────────────────────
#  OYUN DURUMU
# ─────────────────────────────────────────

class GameState:

    def __init__(self):
        self.reset()

    def reset(self):
        self.dice            = [0, 0, 0, 0, 0]
        self.rolls_left      = 3
        self.current_player  = 0
        self.turn_number     = 1          # 1-13 arası
        self.scores          = [
            {cat: None for cat in ALL_CATEGORIES},
            {cat: None for cat in ALL_CATEGORIES},
        ]
        self.yahtzee_bonus   = [0, 0]     # Her oyuncunun ekstra yahtzee bonusu
        self.game_over       = False
        self._player_turns   = [0, 0]     # Her oyuncunun kaç tur oynadığı

    def roll(self, keep_indices):
        if self.rolls_left <= 0:
            return False, "Atış hakkınız kalmadı!"
        if self.rolls_left == 3:
            self.dice = initial_roll()
        else:
            self.dice = roll_dice(self.dice, keep_indices)
        self.rolls_left -= 1
        return True, self.dice

    def score_category(self, category):
        player = self.current_player
        if self.scores[player][category] is not None:
            return False, "Bu kategori zaten dolu!"
        if self.rolls_left == 3:
            return False, "Önce en az bir kez zar atmalısınız!"

        points = calculate_score(category, self.dice)

        # Ekstra Yahtzee bonusu: Yahtzee kutusu zaten doluysa +100
        if category == "yahtzee" and points == 0:
            pass  # Yahtzee kutusu boşsa normal puan
        counts = [self.dice.count(i) for i in range(7)]
        is_yahtzee_roll = (max(counts) == 5)
        if (is_yahtzee_roll and
                self.scores[player]["yahtzee"] is not None and
                self.scores[player]["yahtzee"] == 50):
            self.yahtzee_bonus[player] += 100

        self.scores[player][category] = points
        self._player_turns[player] += 1
        self._next_turn()
        return True, points

    def _next_turn(self):
        self.current_player = 1 - self.current_player
        self.rolls_left     = 3
        self.dice           = [0, 0, 0, 0, 0]

        # Tur sayacı: her iki oyuncu da oynadıysa tur artar
        self.turn_number = min(self._player_turns) + 1

        filled = sum(1 for p in self.scores for v in p.values() if v is not None)
        if filled >= 26:
            self.game_over = True

    def get_totals(self):
        return [
            calculate_total(self.scores[i], self.yahtzee_bonus[i])
            for i in range(2)
        ]

    def get_winner(self):
        totals = self.get_totals()
        if totals[0] > totals[1]:   return 0
        elif totals[1] > totals[0]: return 1
        else:                        return -1

    def get_available_categories(self, player_index):
        return [cat for cat, val in self.scores[player_index].items() if val is None]

    def to_dict(self):
        return {
            "dice":           self.dice,
            "rolls_left":     self.rolls_left,
            "current_player": self.current_player,
            "turn_number":    self.turn_number,
            "scores":         [{k: v for k, v in self.scores[i].items()} for i in range(2)],
            "yahtzee_bonus":  self.yahtzee_bonus,
            "game_over":      self.game_over,
            "totals":         self.get_totals(),
        }


if __name__ == "__main__":
    print("=== GAME LOGIC TEST ===")
    gs = GameState()
    ok, dice = gs.roll([])
    print(f"Zarlar: {dice}")
    for cat in ALL_CATEGORIES:
        pts = calculate_score(cat, dice)
        print(f"  {CATEGORY_DISPLAY_NAMES[cat]:<25} → {pts}")
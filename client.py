"""
CLIENT.PY — Yahtzee PyQt5 istemci uygulaması.
UI tanımları ui/ klasöründeki .ui dosyalarından yüklenir.
"""

import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget,
    QWidget, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5 import uic

from network import NetworkClient
from game_logic import ALL_CATEGORIES, CATEGORY_DISPLAY_NAMES, calculate_score
from widgets import DiceWidget

# ─────────────────────────────────────────
#  YARDIMCILAR
# ─────────────────────────────────────────

_UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
_STYLES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "styles.qss")

def _ui_path(name):
    return os.path.join(_UI_DIR, name)

def _load_styles():
    """Dış QSS dosyasından stilleri yükle."""
    try:
        with open(_STYLES_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ""

STYLE = _load_styles()

RED   = "#e94560"
BLUE  = "#0f3460"
GOLD  = "#f5a623"
GREEN = "#27ae60"
DARK  = "#16213e"


# ─────────────────────────────────────────
#  KURALLAR PENCERESİ
# ─────────────────────────────────────────

class RulesWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi(_ui_path("rules_window.ui"), self)
        self._populate()
        self.closeBtn.clicked.connect(self.close)

    def _populate(self):
        cl = self.scrollContents.layout()

        cl.addWidget(self._stitle("Oyunun Amacı"))
        cl.addWidget(self._text(
            "13 tur boyunca zar atarak kategorileri doldurun. "
            "En yüksek toplam puanı alan oyuncu kazanır."
        ))

        cl.addWidget(self._stitle("Zar Atma"))
        for item in [
            "Her turda en fazla 3 kez zar atabilirsiniz.",
            "1. atışta tüm 5 zar atılır.",
            "2. ve 3. atışlarda tutmak istediğiniz zarları tıklayın (sarı = tutuldu), kalanları yeniden atın.",
            "İstediğiniz zaman atışı durdurup kategori seçebilirsiniz.",
        ]:
            cl.addWidget(self._bullet(item))

        cl.addWidget(self._stitle("Üst Bölüm (Upper Section)"))
        cl.addWidget(self._text("Sadece ilgili sayıdaki zarları toplarsınız."))

        upper_table = QTableWidget(6, 3)
        upper_table.setHorizontalHeaderLabels(["Kategori", "Kural", "Örnek"])
        upper_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        upper_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        upper_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        upper_table.setColumnWidth(0, 120); upper_table.setColumnWidth(2, 160)
        upper_table.verticalHeader().setVisible(False)
        upper_table.setEditTriggers(QTableWidget.NoEditTriggers)
        upper_table.setSelectionMode(QTableWidget.NoSelection)
        upper_table.setFixedHeight(168)
        for i, (cat, rule, ex) in enumerate([
            ("Ones (1'ler)",  "Tüm 1'leri topla",  "[1,1,3,4,1] → 3"),
            ("Twos (2'ler)",  "Tüm 2'leri topla",  "[2,2,5,2,1] → 6"),
            ("Threes (3'ler)","Tüm 3'leri topla",  "[3,1,3,2,6] → 6"),
            ("Fours (4'ler)", "Tüm 4'leri topla",  "[4,4,4,2,1] → 12"),
            ("Fives (5'ler)", "Tüm 5'leri topla",  "[5,5,1,2,3] → 10"),
            ("Sixes (6'lar)", "Tüm 6'ları topla",  "[6,6,6,1,2] → 18"),
        ]):
            upper_table.setItem(i, 0, self._ti(cat, "#ccc"))
            upper_table.setItem(i, 1, self._ti(rule, "#aaa"))
            upper_table.setItem(i, 2, self._ti(ex, GREEN))
            upper_table.setRowHeight(i, 26)
        cl.addWidget(upper_table)

        bonus_lbl = QLabel(
            "Üst bölüm toplamı ≥ 63 olursa +35 Bonus puan! "
            "(Her kategoriye ortalama 3 aynı zar yeterli)"
        )
        bonus_lbl.setWordWrap(True)
        bonus_lbl.setStyleSheet(
            f"font-size:12px;color:{GOLD};border:1px solid {GOLD};border-radius:6px;padding:8px;"
        )
        cl.addWidget(bonus_lbl)

        cl.addWidget(self._stitle("Alt Bölüm (Lower Section)"))
        lower_table = QTableWidget(7, 3)
        lower_table.setHorizontalHeaderLabels(["Kategori", "Kural", "Puan"])
        lower_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        lower_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        lower_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        lower_table.setColumnWidth(0, 140); lower_table.setColumnWidth(2, 140)
        lower_table.verticalHeader().setVisible(False)
        lower_table.setEditTriggers(QTableWidget.NoEditTriggers)
        lower_table.setSelectionMode(QTableWidget.NoSelection)
        lower_table.setFixedHeight(196)
        for i, (cat, rule, pts) in enumerate([
            ("Three of a Kind", "En az 3 aynı zar",         "Tüm zarların toplamı"),
            ("Four of a Kind",  "En az 4 aynı zar",         "Tüm zarların toplamı"),
            ("Full House",      "3 aynı + 2 aynı",           "Sabit 25 puan"),
            ("Small Straight",  "4 ardışık sayı",            "Sabit 30 puan"),
            ("Large Straight",  "5 ardışık sayı",            "Sabit 40 puan"),
            ("YAHTZEE!",        "5 zarın hepsi aynı",        "Sabit 50 puan"),
            ("Chance",          "Herhangi kombinasyon",       "Tüm zarların toplamı"),
        ]):
            lower_table.setItem(i, 0, self._ti(cat, "#ccc"))
            lower_table.setItem(i, 1, self._ti(rule, "#aaa"))
            lower_table.setItem(i, 2, self._ti(pts, GOLD))
            lower_table.setRowHeight(i, 26)
        cl.addWidget(lower_table)

        cl.addWidget(self._stitle("Önemli Kurallar"))
        for item in [
            "Her kategori yalnızca bir kez doldurulabilir.",
            "Uygun kombinasyon olmasa bile bir kategoriyi 0 yazarak kapatabilirsiniz.",
            "Sıra dışında oynamak yasaktır.",
            "İkinci bir YAHTZEE yaparsanız +100 bonus puan kazanırsınız!",
            "Oyun 13 tur sonunda sona erer.",
        ]:
            cl.addWidget(self._bullet(item))

        cl.addStretch()

    def _stitle(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"font-size:14px;font-weight:bold;color:{GOLD};border:none;margin-top:4px;")
        return l

    def _text(self, text):
        l = QLabel(text); l.setWordWrap(True)
        l.setStyleSheet("font-size:12px;color:#ccc;border:none;")
        return l

    def _bullet(self, text):
        l = QLabel(f"  -  {text}"); l.setWordWrap(True)
        l.setStyleSheet("font-size:12px;color:#ccc;border:none;")
        return l

    def _ti(self, text, color):
        it = QTableWidgetItem(text)
        it.setForeground(QColor(color))
        return it

    def _setup_title(self):
        self.titleLabel.setStyleSheet(
            f"font-size:22px;font-weight:bold;color:{GOLD};border:none;"
        )


# ─────────────────────────────────────────
#  BAŞLANGIÇ EKRANI
# ─────────────────────────────────────────

class StartScreen(QWidget):
    connect_requested = pyqtSignal(str, int, str)

    def __init__(self):
        super().__init__()
        uic.loadUi(_ui_path("start_screen.ui"), self)
        self._build_rules()
        self.connect_btn.clicked.connect(self._on_connect)


    def _build_rules(self):
        items_layout = self.rulesItemsContainer.layout()
        for icon, text in [
            ("🎲", "5 zar ve 13 kategori vardır."),
            ("🔄", "Her turda en fazla 3 kez zar atabilirsin."),
            ("📌", "Tutmak istediğin zarları tıkla, kalanları yeniden at."),
            ("✅", "Her tur sonunda bir kategori seçerek puan kazan."),
            ("🏆", "13 tur sonunda en yüksek puan kazanır!"),
            ("⭐", "Üst bölüm toplamı ≥ 63 → +35 Bonus puan!"),
            ("💥", "5 aynı zar = YAHTZEE → 50 puan!"),
            ("🌟", "İkinci YAHTZEE → +100 bonus puan!"),
        ]:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setSpacing(8)
            rl.setContentsMargins(0, 0, 0, 0)
            ico = QLabel(icon)
            ico.setFixedWidth(22)
            ico.setStyleSheet("border:none;font-size:14px;")
            txt = QLabel(text)
            txt.setStyleSheet("font-size:12px;color:#ccc;border:none;")
            txt.setWordWrap(True)
            rl.addWidget(ico)
            rl.addWidget(txt, 1)
            items_layout.addWidget(row)

    def _on_connect(self):
        name = self.name_input.text().strip() or "Oyuncu"
        host = self.host_input.text().strip() or "127.0.0.1"
        try:
            port = int(self.port_input.text().strip())
        except ValueError:
            port = 5555
        self.status_label.setText("⏳ Bağlanıyor...")
        self.connect_btn.setEnabled(False)
        self.connect_requested.emit(host, port, name)

    def reset(self):
        self.connect_btn.setEnabled(True)
        self.status_label.setText("")


# ─────────────────────────────────────────
#  BEKLEME EKRANI
# ─────────────────────────────────────────

class WaitingScreen(QWidget):
    def __init__(self):
        super().__init__()
        uic.loadUi(_ui_path("waiting_screen.ui"), self)
        self._ds = 0
        t = QTimer(self)
        t.timeout.connect(self._anim)
        t.start(500)


    def _anim(self):
        self._ds = (self._ds + 1) % 3
        self.dots.setText(["●  ○  ○", "○  ●  ○", "○  ○  ●"][self._ds])


# ─────────────────────────────────────────
#  OYUN EKRANI
# ─────────────────────────────────────────

class GameScreen(QWidget):
    def __init__(self, net):
        super().__init__()
        self.net = net
        self.dice_values    = [1, 1, 1, 1, 1]
        self.my_index       = -1
        self.current_player = 0
        self.rolls_left     = 3
        self.scores         = [{}, {}]
        self.names          = ["Oyuncu 1", "Oyuncu 2"]
        self.turn_number    = 1
        self._prev_dice     = [0, 0, 0, 0, 0]

        uic.loadUi(_ui_path("game_screen.ui"), self)
        self._build_dice()
        self._build_score_table()
        self._build_category_buttons()
        self._connect_buttons()


    def _build_dice(self):
        self.dice_widgets = []
        layout = self.diceRowWidget.layout()
        for i in range(5):
            dw = DiceWidget(i)
            dw.clicked.connect(self._on_dice_click)
            self.dice_widgets.append(dw)
            layout.addWidget(dw)

    def _build_score_table(self):
        self.score_table.setRowCount(len(ALL_CATEGORIES) + 1)
        self.score_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.score_table.setColumnWidth(1, 52)
        self.score_table.setColumnWidth(2, 52)

        for i, cat in enumerate(ALL_CATEGORIES):
            self.score_table.setItem(i, 0, self._cell(CATEGORY_DISPLAY_NAMES[cat], "#ccc"))
            self.score_table.setItem(i, 1, self._cell("—", "#555", center=True))
            self.score_table.setItem(i, 2, self._cell("—", "#555", center=True))
            self.score_table.setRowHeight(i, 22)

        tr = len(ALL_CATEGORIES)
        self.score_table.setItem(tr, 0, self._cell("TOPLAM", GOLD, bold=True))
        self.total_my  = self._cell("0", GREEN, center=True, bold=True)
        self.total_opp = self._cell("0", GREEN, center=True, bold=True)
        self.score_table.setItem(tr, 1, self.total_my)
        self.score_table.setItem(tr, 2, self.total_opp)
        self.score_table.setRowHeight(tr, 26)

    def _build_category_buttons(self):
        self.cat_buttons = {}
        layout = self.catScrollContents.layout()
        for cat in ALL_CATEGORIES:
            btn = QPushButton(CATEGORY_DISPLAY_NAMES[cat])
            btn.setFixedHeight(32)
            btn.clicked.connect(lambda checked, c=cat: self._on_score(c))
            self.cat_buttons[cat] = btn
            layout.addWidget(btn)

    def _connect_buttons(self):
        self.roll_btn.clicked.connect(self._on_roll)
        self.rules_btn.clicked.connect(self._show_rules)

    # ── Yardımcılar ────────────────────────────────────

    def _cell(self, text, color, center=False, bold=False):
        it = QTableWidgetItem(text)
        it.setForeground(QColor(color))
        if center:
            it.setTextAlignment(Qt.AlignCenter)
        if bold:
            it.setFont(QFont("", -1, QFont.Bold))
        return it

    # ── Kullanıcı Eylemleri ────────────────────────────

    def _on_dice_click(self, i):
        pass  # DiceWidget kendi held durumunu yönetiyor

    def _on_roll(self):
        if self.current_player != self.my_index:
            self.info_label.setText("Sıra sizde değil!")
            return
        if self.rolls_left <= 0:
            self.info_label.setText("Atış hakkınız bitti! Kategori seçin.")
            return
        keep = [] if self.rolls_left == 3 else [
            i for i, dw in enumerate(self.dice_widgets) if dw.held
        ]
        self.net.send_roll(keep)

    def _on_score(self, cat):
        if self.current_player != self.my_index:
            self.info_label.setText("Sıra sizde değil!")
            return
        if self.rolls_left == 3:
            self.info_label.setText("Önce en az bir kez zar atın!")
            return
        self.net.send_score(cat)

    # ── Durum Güncelleme ───────────────────────────────

    def update_state(self, state):
        new_dice            = state.get("dice", [1, 1, 1, 1, 1])
        self.rolls_left     = state.get("rolls_left", 3)
        self.current_player = state.get("current_player", 0)
        self.scores         = state.get("scores", [{}, {}])
        self.names          = state.get("names", ["Oyuncu 1", "Oyuncu 2"])
        totals              = state.get("totals", [0, 0])
        self.turn_number    = state.get("turn_number", 1)
        yb                  = state.get("yahtzee_bonus", [0, 0])

        dice_changed    = (new_dice != self._prev_dice)
        self._prev_dice = new_dice[:]
        self.dice_values = new_dice

        my_turn = (self.current_player == self.my_index)
        first   = (self.rolls_left == 3)

        self.turn_badge.setText(f"TUR {min(self.turn_number, 13)}/13")

        p_my  = self.my_index
        p_opp = 1 - self.my_index
        if len(self.names) > p_my:
            self._update_avatar(self.avatar_my,  self.names[p_my],  p_my)
            self._update_avatar(self.avatar_opp, self.names[p_opp], p_opp)
            self.name_my.setText(self.names[p_my])
            self.name_opp.setText(self.names[p_opp])

        for i, dw in enumerate(self.dice_widgets):
            dw.set_value(new_dice[i], animate=(dice_changed and not dw.held and not first))
            if first:
                dw.set_held(False)
            dw.set_enabled_click(my_turn and not first)

        if my_turn:
            self.turn_label.setText("🎯  Sizin Sıranız!")
        else:
            curr = self.names[self.current_player]
            self.turn_label.setText(f"⏳  {curr} oynuyor...")

        self.rolls_label.setText(
            f"Kalan atış: {'●' * self.rolls_left}{'○' * (3 - self.rolls_left)}"
        )
        self.roll_btn.setEnabled(my_turn and self.rolls_left > 0)

        my_sc  = self.scores[p_my]  if len(self.scores) > p_my  else {}
        opp_sc = self.scores[p_opp] if len(self.scores) > p_opp else {}

        upper = ["ones", "twos", "threes", "fours", "fives", "sixes"]
        us = sum(my_sc.get(c) or 0 for c in upper)
        self.bonus_label.setText(
            f"Üst bölüm: {us}/63" +
            ("  ✅ +35 bonus!" if us >= 63 else f"  ({max(0, 63 - us)} kaldı)")
        )

        for i, cat in enumerate(ALL_CATEGORIES):
            mv = my_sc.get(cat)
            ov = opp_sc.get(cat)
            mi = self.score_table.item(i, 1)
            oi = self.score_table.item(i, 2)
            if mi:
                mi.setText(str(mv) if mv is not None else "—")
                mi.setForeground(QColor(GREEN if mv is not None else "#555"))
            if oi:
                oi.setText(str(ov) if ov is not None else "—")
                oi.setForeground(QColor("#aaa" if ov is not None else "#555"))

        yb_my  = yb[p_my]  if len(yb) > p_my  else 0
        yb_opp = yb[p_opp] if len(yb) > p_opp else 0
        self.total_my.setText(
            f"{totals[p_my]}" + (f" (+{yb_my}🌟)" if yb_my else "")
        )
        self.total_opp.setText(
            f"{totals[p_opp]}" + (f" (+{yb_opp}🌟)" if yb_opp else "")
        )

        for cat, btn in self.cat_buttons.items():
            filled = (my_sc.get(cat) is not None)
            btn.setEnabled(my_turn and not filled and not first)
            if filled:
                btn.setText(f"✓ {CATEGORY_DISPLAY_NAMES[cat]}")
                btn.setStyleSheet(
                    "background:#1a1a1a;color:#444;border:1px solid #333;border-radius:6px;padding:4px;"
                )
            elif my_turn and not first:
                pts = calculate_score(cat, self.dice_values)
                col = GREEN if pts > 0 else "#aaa"
                btn.setText(f"{CATEGORY_DISPLAY_NAMES[cat]}  (+{pts})")
                btn.setStyleSheet(
                    f"background:{DARK};color:{col};border:1px solid {BLUE};border-radius:6px;padding:4px;"
                )
            else:
                btn.setText(CATEGORY_DISPLAY_NAMES[cat])
                btn.setStyleSheet(
                    f"background:{DARK};color:#777;border:1px solid #333;border-radius:6px;padding:4px;"
                )

        self.info_label.setText("")

    def _update_avatar(self, lbl, name, color_index):
        from widgets import AVATAR_COLORS
        initial = name[0].upper() if name else "?"
        bg, fg = AVATAR_COLORS[color_index % len(AVATAR_COLORS)]
        lbl.setText(initial)
        r = lbl.width() // 2
        lbl.setStyleSheet(f"""
            QLabel{{background-color:{bg};color:{fg};border-radius:{r}px;border:none;
                    font-size:{lbl.width()//2}px;font-weight:bold;}}
        """)

    def _show_rules(self):
        self._rules_win = RulesWindow()
        self._rules_win.show()

    def show_error(self, msg):
        self.info_label.setText(f"⚠️  {msg}")

    def show_opponent_disconnected(self, msg):
        self.info_label.setStyleSheet(f"color:{GOLD};font-size:13px;border:none;")
        self.info_label.setText(f"🔌  {msg}")
        self.roll_btn.setEnabled(False)
        for btn in self.cat_buttons.values():
            btn.setEnabled(False)


# ─────────────────────────────────────────
#  BİTİŞ EKRANI
# ─────────────────────────────────────────

class EndScreen(QWidget):
    rematch_requested = pyqtSignal()
    quit_requested    = pyqtSignal()

    def __init__(self):
        super().__init__()
        uic.loadUi(_ui_path("end_screen.ui"), self)
        self.rematch_btn.clicked.connect(self._on_rematch_click)
        self.quit_btn.clicked.connect(self.quit_requested.emit)


    def show_result(self, data, my_index):
        totals      = data.get("totals", [0, 0])
        winner      = data.get("winner", -1)
        winner_name = data.get("winner_name", "?")
        names       = data.get("names", ["Oyuncu 1", "Oyuncu 2"])
        scores      = data.get("scores", [{}, {}])
        yb          = data.get("yahtzee_bonus", [0, 0])

        self.rematch_btn.setEnabled(True)
        self.rematch_btn.setText("🔄  Tekrar Oyna")
        self.rematch_status.setText("")

        if winner == -1:
            self.result_label.setText("🤝  Beraberlik!")
        elif winner == my_index:
            self.result_label.setText("🏆  KAZANDINIZ!")
        else:
            self.result_label.setText(f"😞  {winner_name} Kazandı")

        self._update_avatar(self.end_avatar0, names[0], 0)
        self._update_avatar(self.end_avatar1, names[1], 1)
        self.end_name0.setText(names[0])
        self.end_name1.setText(names[1])

        s0 = str(totals[0]) + (f" (+{yb[0]}🌟)" if yb[0] else "")
        s1 = str(totals[1]) + (f" (+{yb[1]}🌟)" if yb[1] else "")
        self.end_score0.setText(s0)
        self.end_score1.setText(s1)

        self.detail_table.setRowCount(len(ALL_CATEGORIES) + 2)
        self.detail_table.setHorizontalHeaderItem(1, QTableWidgetItem(names[0]))
        self.detail_table.setHorizontalHeaderItem(2, QTableWidgetItem(names[1]))

        for i, cat in enumerate(ALL_CATEGORIES):
            n = QTableWidgetItem(CATEGORY_DISPLAY_NAMES[cat])
            n.setForeground(QColor("#ccc"))
            self.detail_table.setItem(i, 0, n)
            self.detail_table.setRowHeight(i, 22)
            for pi in range(2):
                v = scores[pi].get(cat) if pi < len(scores) else None
                it = QTableWidgetItem(str(v) if v is not None else "—")
                it.setTextAlignment(Qt.AlignCenter)
                it.setForeground(QColor(GREEN if v and v > 0 else "#555"))
                self.detail_table.setItem(i, pi + 1, it)

        br = len(ALL_CATEGORIES)
        bi = QTableWidgetItem("Üst Bölüm Bonusu (+35)")
        bi.setForeground(QColor(GOLD))
        self.detail_table.setItem(br, 0, bi)
        self.detail_table.setRowHeight(br, 24)
        upper = ["ones", "twos", "threes", "fours", "fives", "sixes"]
        for pi in range(2):
            sc = scores[pi] if pi < len(scores) else {}
            us = sum(sc.get(c) or 0 for c in upper)
            bv = 35 if us >= 63 else 0
            bit = QTableWidgetItem(f"+{bv}" if bv else "—")
            bit.setTextAlignment(Qt.AlignCenter)
            bit.setForeground(QColor(GOLD if bv else "#555"))
            self.detail_table.setItem(br, pi + 1, bit)

        tr2 = len(ALL_CATEGORIES) + 1
        ti = QTableWidgetItem("TOPLAM")
        ti.setForeground(QColor(GOLD))
        ti.setFont(QFont("", -1, QFont.Bold))
        self.detail_table.setItem(tr2, 0, ti)
        self.detail_table.setRowHeight(tr2, 26)
        for pi in range(2):
            tv = QTableWidgetItem(str(totals[pi]))
            tv.setTextAlignment(Qt.AlignCenter)
            tv.setForeground(QColor(GREEN if winner == pi else "#e0e0e0"))
            tv.setFont(QFont("", -1, QFont.Bold))
            self.detail_table.setItem(tr2, pi + 1, tv)

    def _update_avatar(self, lbl, name, color_index):
        from widgets import AVATAR_COLORS
        initial = name[0].upper() if name else "?"
        bg, fg = AVATAR_COLORS[color_index % len(AVATAR_COLORS)]
        lbl.setText(initial)
        r = lbl.width() // 2
        lbl.setStyleSheet(f"""
            QLabel{{background-color:{bg};color:{fg};border-radius:{r}px;border:none;
                    font-size:{lbl.width()//2}px;font-weight:bold;}}
        """)

    def _on_rematch_click(self):
        self.rematch_btn.setEnabled(False)
        self.rematch_status.setText("⏳ Rakibin onayı bekleniyor...")
        self.rematch_requested.emit()

    def opponent_wants_rematch(self):
        self.rematch_status.setText("🔔 Rakip tekrar oynamak istiyor!")
        self.rematch_btn.setEnabled(True)
        self.rematch_btn.setText("✅  Kabul Et")


# ─────────────────────────────────────────
#  ANA PENCERE
# ─────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎲 Yahtzee — Çok Oyunculu")
        self.setMinimumSize(1060, 700)
        self.net = NetworkClient()

        self.stack        = QStackedWidget()
        self.start_screen = StartScreen()
        self.wait_screen  = WaitingScreen()
        self.game_screen  = GameScreen(self.net)
        self.end_screen   = EndScreen()

        for s in [self.start_screen, self.wait_screen, self.game_screen, self.end_screen]:
            self.stack.addWidget(s)

        self.setCentralWidget(self.stack)
        self.setStyleSheet(STYLE)
        self._connect_signals()
        self._show_start()

    def _connect_signals(self):
        self.net.signal_welcome.connect(self._on_welcome)
        self.net.signal_waiting.connect(self._on_waiting)
        self.net.signal_game_start.connect(self._on_game_start)
        self.net.signal_state_update.connect(self._on_state_update)
        self.net.signal_game_over.connect(self._on_game_over)
        self.net.signal_error.connect(self._on_error)
        self.net.signal_disconnected.connect(self._on_disconnect)
        self.net.signal_rematch.connect(self._on_rematch)
        self.net.signal_opponent_disconnected.connect(self._on_opponent_disconnected)

    def _show_start(self):
        self.start_screen.reset()
        try:
            self.start_screen.connect_requested.disconnect()
        except Exception:
            pass
        self.start_screen.connect_requested.connect(self._on_connect_requested)
        self.stack.setCurrentIndex(0)

    def _show_end(self):
        self.stack.setCurrentIndex(3)
        try:
            self.end_screen.rematch_requested.disconnect()
            self.end_screen.quit_requested.disconnect()
        except Exception:
            pass
        self.end_screen.rematch_requested.connect(self._on_rematch_btn)
        self.end_screen.quit_requested.connect(self.close)

    def _on_connect_requested(self, host, port, name):
        ok = self.net.connect(host, port, name)
        if not ok:
            self.start_screen.reset()

    def _on_welcome(self, msg):
        self.game_screen.my_index = msg.get("player_index", 0)

    def _on_waiting(self, msg):
        self.stack.setCurrentIndex(1)

    def _on_game_start(self, msg):
        self.stack.setCurrentIndex(2)

    def _on_state_update(self, state):
        self.game_screen.update_state(state)
        if self.stack.currentIndex() != 2:
            self.stack.setCurrentIndex(2)

    def _on_game_over(self, data):
        self.end_screen.show_result(data, self.game_screen.my_index)
        self._show_end()

    def _on_error(self, msg):
        if self.stack.currentIndex() == 2:
            self.game_screen.show_error(msg)
        else:
            QMessageBox.warning(self, "Hata", msg)
            self.start_screen.reset()
            self._show_start()

    def _on_disconnect(self):
        if self.net._opponent_disconnected:
            return
        QMessageBox.warning(self, "Bağlantı Kesildi", "Sunucu bağlantısı kesildi.")
        self.net = NetworkClient()
        self._connect_signals()
        self.game_screen.net = self.net
        self._show_start()

    def _on_opponent_disconnected(self, msg):
        QMessageBox.information(self, "Bilgi", msg)
        self.net.disconnect()
        self.net = NetworkClient()
        self._connect_signals()
        self.game_screen.net = self.net
        self._show_start()

    def _on_rematch(self):
        self.stack.setCurrentIndex(2)

    def _on_rematch_btn(self):
        self.net.send_rematch()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

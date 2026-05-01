"""
CLIENT.PY — Yahtzee PyQt5 istemci uygulaması.
Yenilikler: Zar animasyonu, oyuncu avatarı, tur sayacı, rakip çıkınca bildirim
"""

import sys
import random
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QStackedWidget,
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame,
    QMessageBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from network import NetworkClient
from game_logic import ALL_CATEGORIES, CATEGORY_DISPLAY_NAMES, calculate_score

# ─────────────────────────────────────────
#  RENKLER & STİL
# ─────────────────────────────────────────

STYLE = """
QMainWindow, QWidget {
    background-color: #1a1a2e; color: #e0e0e0;
    font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
}
QPushButton {
    background-color: #16213e; color: #e0e0e0;
    border: 2px solid #0f3460; border-radius: 8px;
    padding: 8px 16px; font-size: 13px;
}
QPushButton:hover   { background-color: #0f3460; border-color: #e94560; }
QPushButton:pressed { background-color: #e94560; }
QPushButton:disabled{ background-color: #111; color: #555; border-color: #333; }
QLineEdit {
    background-color: #16213e; color: #e0e0e0;
    border: 2px solid #0f3460; border-radius: 6px;
    padding: 6px 12px; font-size: 13px;
}
QLineEdit:focus { border-color: #e94560; }
QLabel { color: #e0e0e0; }
QFrame { border: 1px solid #0f3460; border-radius: 8px; }
QTableWidget {
    background-color: #16213e; color: #e0e0e0;
    border: 1px solid #0f3460; gridline-color: #0f3460; font-size: 12px;
}
QHeaderView::section {
    background-color: #0f3460; color: #f5a623;
    padding: 4px; border: none; font-size: 12px; font-weight: bold;
}
QTableWidget::item:selected { background-color: #0f3460; }
"""

RED   = "#e94560"
BLUE  = "#0f3460"
GOLD  = "#f5a623"
GREEN = "#27ae60"
DARK  = "#16213e"

AVATAR_COLORS = [
    ("#e94560", "#fff"),   # kırmızı
    ("#0f3460", "#f5a623"),# mavi-altın
    ("#27ae60", "#fff"),   # yeşil
    ("#8e44ad", "#fff"),   # mor
]


# ─────────────────────────────────────────
#  AVATAR WİDGET'İ
# ─────────────────────────────────────────

class AvatarLabel(QLabel):
    """İsmin baş harfini renkli daire içinde gösteren widget."""
    def __init__(self, name="?", color_index=0, size=38, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.set_name(name, color_index)

    def set_name(self, name, color_index=0):
        initial = name[0].upper() if name else "?"
        bg, fg  = AVATAR_COLORS[color_index % len(AVATAR_COLORS)]
        self.setText(initial)
        self.setAlignment(Qt.AlignCenter)
        r = self.width() // 2
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg}; color: {fg};
                border-radius: {r}px; border: none;
                font-size: {self.width()//2}px; font-weight: bold;
            }}
        """)


# ─────────────────────────────────────────
#  ZAR WİDGET'İ (animasyonlu)
# ─────────────────────────────────────────

class DiceWidget(QLabel):
    clicked = pyqtSignal(int)
    FACES   = {1:"⚀",2:"⚁",3:"⚂",4:"⚃",5:"⚄",6:"⚅"}

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index   = index
        self.value   = 1
        self.held    = False
        self.enabled = False
        self._animating = False
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._anim_step)
        self._anim_count = 0
        self._final_value = 1
        self.setFixedSize(72, 72)
        self.setAlignment(Qt.AlignCenter)
        self._update()

    def set_value(self, v, animate=False):
        if animate and not self.held and not self._animating:
            self._final_value = v
            self._animating   = True
            self._anim_count  = 0
            self._anim_timer.start(60)
        else:
            self.value = v
            self._update()

    def _anim_step(self):
        self._anim_count += 1
        self.value = random.randint(1, 6)
        self._update()
        if self._anim_count >= 8:
            self._anim_timer.stop()
            self._animating = False
            self.value      = self._final_value
            self._update()

    def set_held(self, h):    self.held = h;    self._update()
    def set_enabled_click(self, e): self.enabled = e; self._update()

    def mousePressEvent(self, event):
        if self.enabled and not self._animating:
            self.held = not self.held
            self._update()
            self.clicked.emit(self.index)

    def _update(self):
        self.setText(self.FACES.get(self.value, "?"))
        bg   = "#2a2a4a" if self.held else DARK
        col  = GOLD      if self.held else "#e0e0e0"
        bord = GOLD      if self.held else BLUE
        self.setStyleSheet(
            f"QLabel{{font-size:38px;background:{bg};color:{col};"
            f"border:3px solid {bord};border-radius:12px;}}"
        )
        self.setToolTip("Tutuldu ✓" if self.held else "Tıkla → Tut")


# ─────────────────────────────────────────
#  BAŞLANGIÇ EKRANI
# ─────────────────────────────────────────

class StartScreen(QWidget):
    connect_requested = pyqtSignal(str, int, str)

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(40,30,40,30); root.setSpacing(40)

        # ── Sol: Kurallar ────────────────────────
        left = QVBoxLayout(); left.setSpacing(14)

        title = QLabel("🎲 YAHTZEE")
        title.setStyleSheet(f"font-size:54px;font-weight:bold;color:{RED};border:none;")
        left.addWidget(title)

        tagline = QLabel("Çok Oyunculu Ağ Oyunu")
        tagline.setStyleSheet("font-size:15px;color:#aaa;border:none;")
        left.addWidget(tagline)
        left.addSpacing(8)

        rf = QFrame()
        rf.setStyleSheet(f"background:{DARK};border:1px solid {BLUE};border-radius:12px;")
        rl = QVBoxLayout(rf); rl.setContentsMargins(20,16,20,16); rl.setSpacing(10)

        rt = QLabel("📖  Nasıl Oynanır?")
        rt.setStyleSheet(f"font-size:14px;font-weight:bold;color:{GOLD};border:none;")
        rl.addWidget(rt)

        for icon, text in [
            ("🎲","5 zar ve 13 kategori vardır."),
            ("🔄","Her turda en fazla 3 kez zar atabilirsin."),
            ("📌","Tutmak istediğin zarları tıkla, kalanları yeniden at."),
            ("✅","Her tur sonunda bir kategori seçerek puan kazan."),
            ("🏆","13 tur sonunda en yüksek puan kazanır!"),
            ("⭐","Üst bölüm toplamı ≥ 63 → +35 Bonus puan!"),
            ("💥","5 aynı zar = YAHTZEE → 50 puan!"),
            ("🌟","İkinci YAHTZEE → +100 bonus puan!"),
        ]:
            row = QHBoxLayout(); row.setSpacing(8)
            ico = QLabel(icon); ico.setFixedWidth(22)
            ico.setStyleSheet("border:none;font-size:14px;")
            txt = QLabel(text)
            txt.setStyleSheet("font-size:12px;color:#ccc;border:none;")
            txt.setWordWrap(True)
            row.addWidget(ico); row.addWidget(txt,1)
            rl.addLayout(row)

        left.addWidget(rf); left.addStretch()
        root.addLayout(left, stretch=1)

        # ── Sağ: Form ────────────────────────────
        right = QVBoxLayout(); right.setAlignment(Qt.AlignCenter)

        card = QFrame(); card.setFixedWidth(360)
        card.setStyleSheet(f"background:{DARK};border:2px solid {BLUE};border-radius:16px;")
        cl = QVBoxLayout(card); cl.setSpacing(14); cl.setContentsMargins(28,28,28,28)

        ct = QLabel("🔗  Sunucuya Bağlan")
        ct.setStyleSheet(f"font-size:16px;font-weight:bold;color:{GOLD};border:none;")
        cl.addWidget(ct); cl.addSpacing(4)

        for attr, lbl_t, ph, default in [
            ("name_input","Oyuncu Adı","Adınızı girin...",""),
            ("host_input","Sunucu IP Adresi","örn: 54.123.45.67","127.0.0.1"),
            ("port_input","Port","5555","5555"),
        ]:
            lbl = QLabel(lbl_t); lbl.setStyleSheet("font-size:12px;color:#aaa;border:none;")
            cl.addWidget(lbl)
            inp = QLineEdit(); inp.setPlaceholderText(ph); inp.setText(default)
            setattr(self, attr, inp); cl.addWidget(inp)

        cl.addSpacing(8)
        self.connect_btn = QPushButton("SUNUCUYA BAĞLAN")
        self.connect_btn.setFixedHeight(46)
        self.connect_btn.setStyleSheet(f"""
            QPushButton{{background:{RED};color:white;border:none;border-radius:8px;font-size:15px;font-weight:bold;}}
            QPushButton:hover{{background:#c0392b;}}
        """)
        self.connect_btn.clicked.connect(self._on_connect)
        cl.addWidget(self.connect_btn)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"color:{GOLD};border:none;font-size:12px;")
        cl.addWidget(self.status_label)

        right.addWidget(card, alignment=Qt.AlignCenter)
        root.addLayout(right, stretch=1)

    def _on_connect(self):
        name = self.name_input.text().strip() or "Oyuncu"
        host = self.host_input.text().strip() or "127.0.0.1"
        try:    port = int(self.port_input.text().strip())
        except: port = 5555
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
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter); layout.setSpacing(16)

        lbl = QLabel("⏳  İkinci oyuncu bekleniyor...")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(f"font-size:22px;color:{GOLD};border:none;")
        layout.addWidget(lbl)

        hint = QLabel("Arkadaşınızın sunucuya bağlanması yeterli.")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("font-size:14px;color:#aaa;border:none;")
        layout.addWidget(hint)

        self.dots = QLabel("●  ●  ●")
        self.dots.setAlignment(Qt.AlignCenter)
        self.dots.setStyleSheet(f"font-size:20px;color:{BLUE};border:none;")
        layout.addWidget(self.dots)

        self._ds = 0
        t = QTimer(self); t.timeout.connect(self._anim); t.start(500)

    def _anim(self):
        self._ds = (self._ds + 1) % 3
        self.dots.setText(["●  ○  ○","○  ●  ○","○  ○  ●"][self._ds])


# ─────────────────────────────────────────
#  OYUN EKRANI
# ─────────────────────────────────────────

class GameScreen(QWidget):
    def __init__(self, net):
        super().__init__()
        self.net = net
        self.dice_values    = [1,1,1,1,1]
        self.my_index       = -1
        self.current_player = 0
        self.rolls_left     = 3
        self.scores         = [{},{}]
        self.names          = ["Oyuncu 1","Oyuncu 2"]
        self.turn_number    = 1
        self._prev_dice     = [0,0,0,0,0]
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setSpacing(12); root.setContentsMargins(12,12,12,12)

        # ── Sol: Skor tablosu ─────────────────────
        left = QFrame(); left.setFixedWidth(300)
        ll = QVBoxLayout(left); ll.setSpacing(4); ll.setContentsMargins(8,8,8,8)
        ll.addWidget(self._hdr("📋  SKOR TABLOSU"))

        self.score_table = QTableWidget(len(ALL_CATEGORIES)+1, 3)
        self.score_table.setHorizontalHeaderLabels(["Kategori","Sen","Rakip"])
        self.score_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.score_table.setColumnWidth(1,52); self.score_table.setColumnWidth(2,52)
        self.score_table.verticalHeader().setVisible(False)
        self.score_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.score_table.setSelectionMode(QTableWidget.NoSelection)

        for i, cat in enumerate(ALL_CATEGORIES):
            self.score_table.setItem(i, 0, self._cell(CATEGORY_DISPLAY_NAMES[cat],"#ccc"))
            self.score_table.setItem(i, 1, self._cell("—","#555",center=True))
            self.score_table.setItem(i, 2, self._cell("—","#555",center=True))
            self.score_table.setRowHeight(i,22)

        tr = len(ALL_CATEGORIES)
        self.score_table.setItem(tr,0,self._cell("TOPLAM",GOLD,bold=True))
        self.total_my  = self._cell("0",GREEN,center=True,bold=True)
        self.total_opp = self._cell("0",GREEN,center=True,bold=True)
        self.score_table.setItem(tr,1,self.total_my)
        self.score_table.setItem(tr,2,self.total_opp)
        self.score_table.setRowHeight(tr,26)
        ll.addWidget(self.score_table)

        self.bonus_label = QLabel("Üst bölüm: 0/63  (63 kaldı)")
        self.bonus_label.setStyleSheet("font-size:11px;color:#aaa;border:none;")
        ll.addWidget(self.bonus_label)
        root.addWidget(left)

        # ── Orta: Oyun alanı ──────────────────────
        mid = QWidget()
        ml = QVBoxLayout(mid); ml.setAlignment(Qt.AlignTop|Qt.AlignHCenter); ml.setSpacing(14)

        # Oyuncu avatarları + tur sayacı
        header_row = QHBoxLayout(); header_row.setAlignment(Qt.AlignCenter); header_row.setSpacing(20)

        self.avatar_my  = AvatarLabel("?", 0, 42)
        self.avatar_opp = AvatarLabel("?", 1, 42)
        self.name_my    = QLabel("Sen")
        self.name_my.setStyleSheet(f"font-size:12px;color:{GREEN};border:none;font-weight:bold;")
        self.name_opp   = QLabel("Rakip")
        self.name_opp.setStyleSheet("font-size:12px;color:#aaa;border:none;")

        my_col  = QVBoxLayout(); my_col.setAlignment(Qt.AlignCenter); my_col.setSpacing(2)
        my_col.addWidget(self.avatar_my, alignment=Qt.AlignCenter)
        my_col.addWidget(self.name_my,   alignment=Qt.AlignCenter)

        self.turn_badge = QLabel("TUR 1/13")
        self.turn_badge.setAlignment(Qt.AlignCenter)
        self.turn_badge.setFixedWidth(90)
        self.turn_badge.setStyleSheet(f"""
            QLabel{{background:{BLUE};color:{GOLD};border:2px solid {GOLD};
            border-radius:10px;font-size:13px;font-weight:bold;padding:6px;}}
        """)

        opp_col = QVBoxLayout(); opp_col.setAlignment(Qt.AlignCenter); opp_col.setSpacing(2)
        opp_col.addWidget(self.avatar_opp, alignment=Qt.AlignCenter)
        opp_col.addWidget(self.name_opp,   alignment=Qt.AlignCenter)

        header_row.addLayout(my_col)
        header_row.addWidget(self.turn_badge)
        header_row.addLayout(opp_col)
        ml.addLayout(header_row)

        # Sıra göstergesi
        self.turn_label = QLabel("Sıra: —")
        self.turn_label.setAlignment(Qt.AlignCenter)
        self.turn_label.setStyleSheet(f"font-size:17px;font-weight:bold;color:{GOLD};border:none;")
        ml.addWidget(self.turn_label)

        self.rolls_label = QLabel("Kalan atış: ●●●")
        self.rolls_label.setAlignment(Qt.AlignCenter)
        self.rolls_label.setStyleSheet("font-size:13px;color:#aaa;border:none;")
        ml.addWidget(self.rolls_label)

        # Zarlar
        dice_row = QWidget()
        dl = QHBoxLayout(dice_row); dl.setSpacing(10); dl.setAlignment(Qt.AlignCenter)
        self.dice_widgets = []
        for i in range(5):
            dw = DiceWidget(i); dw.clicked.connect(self._on_dice_click)
            self.dice_widgets.append(dw); dl.addWidget(dw)
        ml.addWidget(dice_row)

        self.hold_hint = QLabel("Tıklayarak tutmak istediğin zarları seç")
        self.hold_hint.setAlignment(Qt.AlignCenter)
        self.hold_hint.setStyleSheet("font-size:11px;color:#555;border:none;")
        ml.addWidget(self.hold_hint)

        self.roll_btn = QPushButton("🎲  ZAR AT")
        self.roll_btn.setFixedSize(200,46)
        self.roll_btn.setStyleSheet(f"""
            QPushButton{{background:{GREEN};color:white;border:none;border-radius:8px;font-size:15px;font-weight:bold;}}
            QPushButton:hover{{background:#1e8449;}}
            QPushButton:disabled{{background:#2a2a2a;color:#555;border:none;}}
        """)
        self.roll_btn.clicked.connect(self._on_roll)
        ml.addWidget(self.roll_btn, alignment=Qt.AlignCenter)

        self.info_label = QLabel("")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet(f"color:{RED};font-size:13px;border:none;")
        ml.addWidget(self.info_label)
        root.addWidget(mid, stretch=1)

        # ── Sağ: Kategoriler ──────────────────────
        right = QFrame(); right.setFixedWidth(230)
        rl = QVBoxLayout(right); rl.setSpacing(4); rl.setContentsMargins(8,8,8,8)
        rl.addWidget(self._hdr("✅  KATEGORİ SEÇ"))

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border:none;")
        container = QWidget()
        self.cat_layout = QVBoxLayout(container); self.cat_layout.setSpacing(3)
        self.cat_buttons = {}
        for cat in ALL_CATEGORIES:
            btn = QPushButton(CATEGORY_DISPLAY_NAMES[cat])
            btn.setFixedHeight(32)
            btn.clicked.connect(lambda checked, c=cat: self._on_score(c))
            self.cat_buttons[cat] = btn; self.cat_layout.addWidget(btn)
        scroll.setWidget(container); rl.addWidget(scroll)
        root.addWidget(right)

    def _hdr(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"font-size:13px;font-weight:bold;color:{GOLD};border:none;")
        return l

    def _cell(self, text, color, center=False, bold=False):
        it = QTableWidgetItem(text)
        it.setForeground(QColor(color))
        if center: it.setTextAlignment(Qt.AlignCenter)
        if bold:   it.setFont(QFont("",-1,QFont.Bold))
        return it

    def _on_dice_click(self, i): pass

    def _on_roll(self):
        if self.current_player != self.my_index:
            self.info_label.setText("Sıra sizde değil!"); return
        if self.rolls_left <= 0:
            self.info_label.setText("Atış hakkınız bitti! Kategori seçin."); return
        keep = [] if self.rolls_left == 3 else [i for i,dw in enumerate(self.dice_widgets) if dw.held]
        self.net.send_roll(keep)

    def _on_score(self, cat):
        if self.current_player != self.my_index:
            self.info_label.setText("Sıra sizde değil!"); return
        if self.rolls_left == 3:
            self.info_label.setText("Önce en az bir kez zar atın!"); return
        self.net.send_score(cat)

    def update_state(self, state):
        new_dice        = state.get("dice",[1,1,1,1,1])
        self.rolls_left = state.get("rolls_left",3)
        self.current_player = state.get("current_player",0)
        self.scores     = state.get("scores",[{},{}])
        self.names      = state.get("names",["Oyuncu 1","Oyuncu 2"])
        totals          = state.get("totals",[0,0])
        self.turn_number= state.get("turn_number",1)
        yb              = state.get("yahtzee_bonus",[0,0])

        dice_changed = (new_dice != self._prev_dice)
        self._prev_dice = new_dice[:]
        self.dice_values = new_dice

        my_turn = (self.current_player == self.my_index)
        first   = (self.rolls_left == 3)

        # Tur sayacı güncelle
        self.turn_badge.setText(f"TUR {min(self.turn_number,13)}/13")

        # Avatarlar güncelle
        p_my  = self.my_index
        p_opp = 1 - self.my_index
        if len(self.names) > p_my:
            self.avatar_my.set_name(self.names[p_my],  p_my)
            self.avatar_opp.set_name(self.names[p_opp], p_opp)
            self.name_my.setText(self.names[p_my])
            self.name_opp.setText(self.names[p_opp])

        # Zarlar — animasyonla güncelle
        for i, dw in enumerate(self.dice_widgets):
            dw.set_value(new_dice[i], animate=(dice_changed and not dw.held and not first))
            if first: dw.set_held(False)
            dw.set_enabled_click(my_turn and not first)

        # Tur / sıra etiketi
        if my_turn:
            self.turn_label.setText("🎯  Sizin Sıranız!")
            self.turn_label.setStyleSheet(f"font-size:17px;font-weight:bold;color:{GREEN};border:none;")
            self.avatar_my.setStyleSheet(
                self.avatar_my.styleSheet().replace("border:none","border:3px solid "+GREEN)
            )
        else:
            curr = self.names[self.current_player]
            self.turn_label.setText(f"⏳  {curr} oynuyor...")
            self.turn_label.setStyleSheet(f"font-size:17px;font-weight:bold;color:{GOLD};border:none;")

        self.rolls_label.setText(f"Kalan atış: {'●'*self.rolls_left}{'○'*(3-self.rolls_left)}")
        self.roll_btn.setEnabled(my_turn and self.rolls_left > 0)

        # Skor tablosu
        my_sc  = self.scores[p_my]  if len(self.scores)>p_my  else {}
        opp_sc = self.scores[p_opp] if len(self.scores)>p_opp else {}

        upper = ["ones","twos","threes","fours","fives","sixes"]
        us = sum(my_sc.get(c) or 0 for c in upper)
        self.bonus_label.setText(
            f"Üst bölüm: {us}/63" + ("  ✅ +35 bonus!" if us>=63 else f"  ({max(0,63-us)} kaldı)")
        )

        for i, cat in enumerate(ALL_CATEGORIES):
            mv = my_sc.get(cat); ov = opp_sc.get(cat)
            mi = self.score_table.item(i,1); oi = self.score_table.item(i,2)
            if mi:
                mi.setText(str(mv) if mv is not None else "—")
                mi.setForeground(QColor(GREEN if mv is not None else "#555"))
            if oi:
                oi.setText(str(ov) if ov is not None else "—")
                oi.setForeground(QColor("#aaa" if ov is not None else "#555"))

        # Yahtzee bonusu toplamı göster
        my_total  = totals[p_my]
        opp_total = totals[p_opp]
        yb_my     = yb[p_my]  if len(yb)>p_my  else 0
        yb_opp    = yb[p_opp] if len(yb)>p_opp else 0
        self.total_my.setText(f"{my_total}" + (f" (+{yb_my}🌟)" if yb_my else ""))
        self.total_opp.setText(f"{opp_total}" + (f" (+{yb_opp}🌟)" if yb_opp else ""))

        # Kategori butonları
        for cat, btn in self.cat_buttons.items():
            filled = (my_sc.get(cat) is not None)
            btn.setEnabled(my_turn and not filled and not first)
            if filled:
                btn.setText(f"✓ {CATEGORY_DISPLAY_NAMES[cat]}")
                btn.setStyleSheet("background:#1a1a1a;color:#444;border:1px solid #333;border-radius:6px;padding:4px;")
            elif my_turn and not first:
                pts = calculate_score(cat, self.dice_values)
                col = GREEN if pts > 0 else "#aaa"
                btn.setText(f"{CATEGORY_DISPLAY_NAMES[cat]}  (+{pts})")
                btn.setStyleSheet(f"background:{DARK};color:{col};border:1px solid {BLUE};border-radius:6px;padding:4px;")
            else:
                btn.setText(CATEGORY_DISPLAY_NAMES[cat])
                btn.setStyleSheet(f"background:{DARK};color:#777;border:1px solid #333;border-radius:6px;padding:4px;")

        self.info_label.setText("")

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
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(14); layout.setContentsMargins(40,24,40,24)

        self.result_label = QLabel("Oyun Bitti!")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setStyleSheet(f"font-size:38px;font-weight:bold;color:{GOLD};border:none;")
        layout.addWidget(self.result_label)

        # Avatar + toplam skor satırı
        self.avatar_row = QHBoxLayout()
        self.avatar_row.setAlignment(Qt.AlignCenter); self.avatar_row.setSpacing(30)
        self.end_avatar0 = AvatarLabel("?",0,52)
        self.end_avatar1 = AvatarLabel("?",1,52)
        self.end_score0  = QLabel("0")
        self.end_score1  = QLabel("0")
        for lbl in [self.end_score0, self.end_score1]:
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"font-size:26px;font-weight:bold;color:{GREEN};border:none;")
        self.end_name0 = QLabel("Oyuncu 1"); self.end_name0.setAlignment(Qt.AlignCenter)
        self.end_name1 = QLabel("Oyuncu 2"); self.end_name1.setAlignment(Qt.AlignCenter)
        for n in [self.end_name0, self.end_name1]:
            n.setStyleSheet("font-size:13px;color:#aaa;border:none;")

        col0 = QVBoxLayout(); col0.setAlignment(Qt.AlignCenter); col0.setSpacing(3)
        col0.addWidget(self.end_avatar0,alignment=Qt.AlignCenter)
        col0.addWidget(self.end_name0, alignment=Qt.AlignCenter)
        col0.addWidget(self.end_score0,alignment=Qt.AlignCenter)

        vs = QLabel("VS"); vs.setStyleSheet(f"font-size:20px;color:#555;border:none;")

        col1 = QVBoxLayout(); col1.setAlignment(Qt.AlignCenter); col1.setSpacing(3)
        col1.addWidget(self.end_avatar1,alignment=Qt.AlignCenter)
        col1.addWidget(self.end_name1, alignment=Qt.AlignCenter)
        col1.addWidget(self.end_score1,alignment=Qt.AlignCenter)

        self.avatar_row.addLayout(col0); self.avatar_row.addWidget(vs)
        self.avatar_row.addLayout(col1)
        layout.addLayout(self.avatar_row)

        # Detaylı skor tablosu
        self.detail_table = QTableWidget(len(ALL_CATEGORIES)+2, 3)
        self.detail_table.setHorizontalHeaderLabels(["Kategori","Oyuncu 1","Oyuncu 2"])
        self.detail_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.detail_table.setColumnWidth(1,100); self.detail_table.setColumnWidth(2,100)
        self.detail_table.verticalHeader().setVisible(False)
        self.detail_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.detail_table.setSelectionMode(QTableWidget.NoSelection)
        self.detail_table.setFixedHeight(340)
        layout.addWidget(self.detail_table)

        self.rematch_status = QLabel("")
        self.rematch_status.setAlignment(Qt.AlignCenter)
        self.rematch_status.setStyleSheet(f"font-size:13px;color:{GOLD};border:none;")
        layout.addWidget(self.rematch_status)

        btn_row = QHBoxLayout(); btn_row.setAlignment(Qt.AlignCenter); btn_row.setSpacing(16)
        self.rematch_btn = QPushButton("🔄  Tekrar Oyna")
        self.rematch_btn.setFixedSize(180,46)
        self.rematch_btn.setStyleSheet(f"""
            QPushButton{{background:{GREEN};color:white;border:none;border-radius:8px;font-size:14px;font-weight:bold;}}
            QPushButton:hover{{background:#1e8449;}}
            QPushButton:disabled{{background:#333;color:#666;border:none;}}
        """)
        self.rematch_btn.clicked.connect(self._on_rematch_click)
        self.quit_btn = QPushButton("❌  Çıkış")
        self.quit_btn.setFixedSize(130,46)
        self.quit_btn.clicked.connect(self.quit_requested.emit)
        btn_row.addWidget(self.rematch_btn); btn_row.addWidget(self.quit_btn)
        layout.addLayout(btn_row)

    def show_result(self, data, my_index):
        totals      = data.get("totals",[0,0])
        winner      = data.get("winner",-1)
        winner_name = data.get("winner_name","?")
        names       = data.get("names",["Oyuncu 1","Oyuncu 2"])
        scores      = data.get("scores",[{},{}])
        yb          = data.get("yahtzee_bonus",[0,0])

        self.rematch_btn.setEnabled(True)
        self.rematch_btn.setText("🔄  Tekrar Oyna")
        self.rematch_status.setText("")

        if winner == -1:
            self.result_label.setText("🤝  Beraberlik!")
            self.result_label.setStyleSheet(f"font-size:38px;font-weight:bold;color:{GOLD};border:none;")
        elif winner == my_index:
            self.result_label.setText("🏆  KAZANDINIZ!")
            self.result_label.setStyleSheet(f"font-size:38px;font-weight:bold;color:{GREEN};border:none;")
        else:
            self.result_label.setText(f"😞  {winner_name} Kazandı")
            self.result_label.setStyleSheet(f"font-size:38px;font-weight:bold;color:{RED};border:none;")

        # Avatarlar
        self.end_avatar0.set_name(names[0], 0)
        self.end_avatar1.set_name(names[1], 1)
        self.end_name0.setText(names[0]); self.end_name1.setText(names[1])
        s0 = str(totals[0]) + (f" (+{yb[0]}🌟)" if yb[0] else "")
        s1 = str(totals[1]) + (f" (+{yb[1]}🌟)" if yb[1] else "")
        self.end_score0.setText(s0); self.end_score1.setText(s1)
        win_col0 = GREEN if winner==0 else "#aaa"
        win_col1 = GREEN if winner==1 else "#aaa"
        self.end_score0.setStyleSheet(f"font-size:26px;font-weight:bold;color:{win_col0};border:none;")
        self.end_score1.setStyleSheet(f"font-size:26px;font-weight:bold;color:{win_col1};border:none;")

        # Tablo başlıkları
        self.detail_table.setHorizontalHeaderItem(1, QTableWidgetItem(names[0]))
        self.detail_table.setHorizontalHeaderItem(2, QTableWidgetItem(names[1]))

        for i, cat in enumerate(ALL_CATEGORIES):
            n = QTableWidgetItem(CATEGORY_DISPLAY_NAMES[cat])
            n.setForeground(QColor("#ccc")); self.detail_table.setItem(i,0,n)
            self.detail_table.setRowHeight(i,22)
            for pi in range(2):
                v = scores[pi].get(cat) if pi<len(scores) else None
                it = QTableWidgetItem(str(v) if v is not None else "—")
                it.setTextAlignment(Qt.AlignCenter)
                it.setForeground(QColor(GREEN if v and v>0 else "#555"))
                self.detail_table.setItem(i,pi+1,it)

        # Bonus satırı
        br = len(ALL_CATEGORIES)
        bi = QTableWidgetItem("Üst Bölüm Bonusu (+35)")
        bi.setForeground(QColor(GOLD)); self.detail_table.setItem(br,0,bi)
        self.detail_table.setRowHeight(br,24)
        upper = ["ones","twos","threes","fours","fives","sixes"]
        for pi in range(2):
            sc = scores[pi] if pi<len(scores) else {}
            us = sum(sc.get(c) or 0 for c in upper); bv = 35 if us>=63 else 0
            bit = QTableWidgetItem(f"+{bv}" if bv else "—")
            bit.setTextAlignment(Qt.AlignCenter)
            bit.setForeground(QColor(GOLD if bv else "#555"))
            self.detail_table.setItem(br,pi+1,bit)

        # Toplam satırı
        tr2 = len(ALL_CATEGORIES)+1
        ti = QTableWidgetItem("TOPLAM")
        ti.setForeground(QColor(GOLD)); ti.setFont(QFont("",-1,QFont.Bold))
        self.detail_table.setItem(tr2,0,ti); self.detail_table.setRowHeight(tr2,26)
        for pi in range(2):
            tv = QTableWidgetItem(str(totals[pi]))
            tv.setTextAlignment(Qt.AlignCenter)
            tv.setForeground(QColor(GREEN if winner==pi else "#e0e0e0"))
            tv.setFont(QFont("",-1,QFont.Bold))
            self.detail_table.setItem(tr2,pi+1,tv)

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
        self._connect_signals()

        self.stack        = QStackedWidget()
        self.start_screen = StartScreen()
        self.wait_screen  = WaitingScreen()
        self.game_screen  = GameScreen(self.net)
        self.end_screen   = EndScreen()

        for s in [self.start_screen,self.wait_screen,self.game_screen,self.end_screen]:
            self.stack.addWidget(s)

        self.setCentralWidget(self.stack)
        self.setStyleSheet(STYLE)
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
        try: self.start_screen.connect_requested.disconnect()
        except: pass
        self.start_screen.connect_requested.connect(self._on_connect_requested)
        self.stack.setCurrentIndex(0)

    def _show_end(self):
        self.stack.setCurrentIndex(3)
        try:
            self.end_screen.rematch_requested.disconnect()
            self.end_screen.quit_requested.disconnect()
        except: pass
        self.end_screen.rematch_requested.connect(self._on_rematch_btn)
        self.end_screen.quit_requested.connect(self.close)

    def _on_connect_requested(self, host, port, name):
        ok = self.net.connect(host, port, name)
        if not ok: self.start_screen.reset()

    def _on_welcome(self, msg):
        self.game_screen.my_index = msg.get("player_index",0)

    def _on_waiting(self, msg):    self.stack.setCurrentIndex(1)
    def _on_game_start(self, msg): self.stack.setCurrentIndex(2)

    def _on_state_update(self, state):
        self.game_screen.update_state(state)
        if self.stack.currentIndex() != 2: self.stack.setCurrentIndex(2)

    def _on_game_over(self, data):
        self.end_screen.show_result(data, self.game_screen.my_index)
        self._show_end()

    def _on_error(self, msg):
        if self.stack.currentIndex() == 2:
            self.game_screen.show_error(msg)
        else:
            QMessageBox.warning(self, "Hata", msg)
            self.start_screen.reset(); self._show_start()

    def _on_disconnect(self):
        QMessageBox.warning(self, "Bağlantı Kesildi", "Sunucu bağlantısı kesildi.")
        self.net = NetworkClient(); self._connect_signals()
        self.game_screen.net = self.net; self._show_start()

    def _on_opponent_disconnected(self, msg):
        if self.stack.currentIndex() == 2:
            self.game_screen.show_opponent_disconnected(msg)
        else:
            QMessageBox.information(self, "Bilgi", msg)

    def _on_rematch(self):        self.stack.setCurrentIndex(2)
    def _on_rematch_btn(self):    self.net.send_rematch()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow(); win.show()
    sys.exit(app.exec_())
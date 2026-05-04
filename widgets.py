import random
from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt, QTimer, pyqtSignal

AVATAR_COLORS = [
    ("#e94560", "#fff"),
    ("#0f3460", "#f5a623"),
    ("#27ae60", "#fff"),
    ("#8e44ad", "#fff"),
]

DARK = "#16213e"
BLUE = "#0f3460"
GOLD = "#f5a623"


class AvatarLabel(QLabel):
    def __init__(self, name="?", color_index=0, size=38, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.set_name(name, color_index)

    def set_name(self, name, color_index=0):
        initial = name[0].upper() if name else "?"
        bg, fg = AVATAR_COLORS[color_index % len(AVATAR_COLORS)]
        self.setText(initial)
        self.setAlignment(Qt.AlignCenter)
        r = self.width() // 2
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg}; color: {fg};
                border-radius: {r}px; border: none;
                font-size: {self.width() // 2}px; font-weight: bold;
            }}
        """)


class DiceWidget(QLabel):
    clicked = pyqtSignal(int)
    FACES = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.value = 1
        self.held = False
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
            self._animating = True
            self._anim_count = 0
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
            self.value = self._final_value
            self._update()

    def set_held(self, h):
        self.held = h
        self._update()

    def set_enabled_click(self, e):
        self.enabled = e
        self._update()

    def mousePressEvent(self, event):
        if self.enabled and not self._animating:
            self.held = not self.held
            self._update()
            self.clicked.emit(self.index)

    def _update(self):
        self.setText(self.FACES.get(self.value, "?"))
        bg = "#2a2a4a" if self.held else DARK
        col = GOLD if self.held else "#e0e0e0"
        bord = GOLD if self.held else BLUE
        self.setStyleSheet(
            f"QLabel{{font-size:38px;background:{bg};color:{col};"
            f"border:3px solid {bord};border-radius:12px;}}"
        )
        self.setToolTip("Tutuldu ✓" if self.held else "Tıkla → Tut")

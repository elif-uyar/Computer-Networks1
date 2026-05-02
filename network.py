"""
NETWORK.PY
----------
İstemci tarafı ağ katmanı.
Sunucuya bağlanır, mesaj alıp gönderir.
PyQt sinyalleri ile GUI'yi günceller.
"""

import socket
import json
import threading
from PyQt5.QtCore import QObject, pyqtSignal

BUFFER_SIZE = 4096


class NetworkClient(QObject):
    # ── Sunucudan gelen olaylar için sinyaller ──
    signal_welcome               = pyqtSignal(dict)
    signal_waiting               = pyqtSignal(dict)
    signal_game_start            = pyqtSignal(dict)
    signal_state_update          = pyqtSignal(dict)
    signal_game_over             = pyqtSignal(dict)
    signal_error                 = pyqtSignal(str)
    signal_disconnected          = pyqtSignal()
    signal_rematch               = pyqtSignal()
    signal_opponent_disconnected = pyqtSignal(str)  # Rakip ayrıldı

    def __init__(self):
        super().__init__()
        self.sock          = None
        self.connected     = False
        self.player_index  = -1
        self._recv_thread  = None

    # ─────────────────────────────
    #  BAĞLANTI
    # ─────────────────────────────

    def connect(self, host: str, port: int, player_name: str) -> bool:
        """Sunucuya bağlan ve isim gönder."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((host, port))
            self.sock.settimeout(None)
            self.connected = True

            # İlk mesaj: isim bildirimi
            self._send({"name": player_name})

            # Arka planda mesaj dinle
            self._recv_thread = threading.Thread(
                target=self._listen, daemon=True
            )
            self._recv_thread.start()
            return True

        except Exception as e:
            self.signal_error.emit(f"Bağlantı hatası: {e}")
            return False

    def disconnect(self):
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass

    # ─────────────────────────────
    #  MESAJ GÖNDERME
    # ─────────────────────────────

    def _send(self, data: dict):
        try:
            msg = json.dumps(data) + "\n"
            self.sock.sendall(msg.encode("utf-8"))
        except Exception as e:
            self.signal_error.emit(f"Gönderme hatası: {e}")

    def send_roll(self, keep_indices: list):
        """Zar at isteği gönder."""
        self._send({"action": "roll", "keep": keep_indices})

    def send_score(self, category: str):
        """Kategori seç isteği gönder."""
        self._send({"action": "score", "category": category})

    def send_rematch(self):
        """Tekrar oyna isteği gönder."""
        self._send({"action": "rematch"})

    # ─────────────────────────────
    #  MESAJ ALMA (arka plan thread)
    # ─────────────────────────────

    def _listen(self):
        buffer = b""
        try:
            while self.connected:
                chunk = self.sock.recv(BUFFER_SIZE)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    try:
                        msg = json.loads(line.decode("utf-8"))
                        self._dispatch(msg)
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass
        finally:
            self.connected = False
            self.signal_disconnected.emit()

    def _dispatch(self, msg: dict):
        """Gelen mesajı tipine göre ilgili sinyale ilet."""
        msg_type = msg.get("type")
        if msg_type == "welcome":
            self.player_index = msg.get("player_index", -1)
            self.signal_welcome.emit(msg)
        elif msg_type == "waiting":
            self.signal_waiting.emit(msg)
        elif msg_type == "game_start":
            self.signal_game_start.emit(msg)
        elif msg_type == "state_update":
            self.signal_state_update.emit(msg)
        elif msg_type == "game_over":
            self.signal_game_over.emit(msg)
        elif msg_type == "error":
            self.signal_error.emit(msg.get("message", "Bilinmeyen hata"))
        elif msg_type == "rematch_start":
            self.signal_rematch.emit()
        elif msg_type == "opponent_disconnected":
            self.signal_opponent_disconnected.emit(msg.get("message","Rakip ayrıldı."))
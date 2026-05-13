
import socket
import json
import threading
from PyQt5.QtCore import QObject, pyqtSignal

BUFFER_SIZE = 4096


class NetworkClient(QObject):
    signal_welcome               = pyqtSignal(dict)
    signal_waiting               = pyqtSignal(dict)
    signal_game_start            = pyqtSignal(dict)
    signal_state_update          = pyqtSignal(dict)
    signal_game_over             = pyqtSignal(dict)
    signal_error                 = pyqtSignal(str)
    signal_disconnected          = pyqtSignal()
    signal_rematch               = pyqtSignal()
    signal_opponent_disconnected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.sock                   = None
        self.connected              = False
        self.player_index           = -1
        self._recv_thread           = None
        self._opponent_disconnected = False

    def connect(self, host, port, player_name):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((host, port))
            self.sock.settimeout(None)
            self.connected = True
            self._opponent_disconnected = False
            self._send({"name": player_name})
            self._recv_thread = threading.Thread(target=self._listen, daemon=True)
            self._recv_thread.start()
            return True
        except Exception as e:
            self.signal_error.emit(f"Baglanti hatasi: {e}")
            return False

    def disconnect(self):
        self.connected = False
        self._opponent_disconnected = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass

    def _send(self, data):
        try:
            self.sock.sendall((json.dumps(data) + "\n").encode("utf-8"))
        except Exception as e:
            self.signal_error.emit(f"Gonderme hatasi: {e}")

    def send_roll(self, keep_indices):
        self._send({"action": "roll", "keep": keep_indices})

    def send_score(self, category):
        self._send({"action": "score", "category": category})

    def send_rematch(self):
        self._send({"action": "rematch"})

    def _listen(self):
        buffer = b""
        opponent_left = False
        try:
            while self.connected:
                try:
                    chunk = self.sock.recv(BUFFER_SIZE)
                except Exception:
                    break
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    try:
                        msg = json.loads(line.decode("utf-8"))
                        if msg.get("type") == "opponent_disconnected":
                            opponent_left = True
                            self._opponent_disconnected = True
                        self._dispatch(msg)
                    except json.JSONDecodeError:
                        pass
                if opponent_left:
                    return
        except Exception:
            pass
        finally:
            self.connected = False
            if not self._opponent_disconnected:
                self.signal_disconnected.emit()

    def _dispatch(self, msg):
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
            self.signal_opponent_disconnected.emit(msg.get("message", "Rakip ayrildi."))
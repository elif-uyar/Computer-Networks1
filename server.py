"""
YAHTZEE SERVER — AWS'de çalışacak konsol uygulaması.
Çalıştırma: python server.py  |  python server.py --port 5555
"""

import socket
import threading
import json
import sys
import argparse
from game_logic import GameState, ALL_CATEGORIES, CATEGORY_DISPLAY_NAMES

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5555
BUFFER_SIZE  = 4096


# ─────────────────────────────────────────
#  MESAJ YARDIMCILARI
# ─────────────────────────────────────────

def send_msg(conn, data: dict):
    try:
        conn.sendall((json.dumps(data) + "\n").encode("utf-8"))
    except Exception as e:
        print(f"[SEND ERROR] {e}")

def recv_msg(conn):
    try:
        buffer = b""
        while True:
            chunk = conn.recv(BUFFER_SIZE)
            if not chunk:
                return None
            buffer += chunk
            if b"\n" in buffer:
                line, _ = buffer.split(b"\n", 1)
                return json.loads(line.decode("utf-8"))
    except:
        return None


# ─────────────────────────────────────────
#  OYUN ODASI
# ─────────────────────────────────────────

class GameRoom:

    def __init__(self, room_id):
        self.room_id  = room_id
        self.players  = [None, None]
        self.names    = ["Oyuncu 1", "Oyuncu 2"]
        self.state    = GameState()
        self.lock     = threading.Lock()
        self.active   = [True, True]   # Bağlantı durumu
        print(f"[ROOM {room_id}] Oluşturuldu.")

    def add_player(self, conn, addr, idx, name):
        self.players[idx] = conn
        self.names[idx]   = name
        print(f"[ROOM {self.room_id}] {name} bağlandı ({addr}), slot {idx+1}")

    def broadcast(self, data):
        for i, conn in enumerate(self.players):
            if conn and self.active[i]:
                send_msg(conn, data)

    def send_to(self, idx, data):
        conn = self.players[idx]
        if conn and self.active[idx]:
            send_msg(conn, data)

    def send_state(self):
        d = self.state.to_dict()
        d["type"]  = "state_update"
        d["names"] = self.names
        self.broadcast(d)

    def handle_message(self, player_index, msg):
        with self.lock:
            action = msg.get("action")
            state  = self.state

            if state.current_player != player_index:
                self.send_to(player_index, {"type":"error","message":"Sıra sizde değil!"})
                return

            if action == "roll":
                keep = msg.get("keep", [])
                ok, result = state.roll(keep)
                if ok:
                    self.send_state()
                else:
                    self.send_to(player_index, {"type":"error","message":result})

            elif action == "score":
                category = msg.get("category")
                if category not in ALL_CATEGORIES:
                    self.send_to(player_index, {"type":"error","message":"Geçersiz kategori!"})
                    return
                ok, result = state.score_category(category)
                if ok:
                    if state.game_over:
                        self._finish_game()
                    else:
                        self.send_state()
                else:
                    self.send_to(player_index, {"type":"error","message":result})

            elif action == "rematch":
                if not all(self.active):
                    self.send_to(player_index, {"type":"error","message":"Rakip oyundan ayrıldı. Tekrar oynayamazsınız."})
                    return
                state.reset()
                self.active = [True, True]
                self.broadcast({"type":"rematch_start"})
                self.send_state()
                print(f"[ROOM {self.room_id}] Rematch başladı.")

    def handle_disconnect(self, player_index):
        """Bir oyuncu baglantıyı kesince diğerine bildir."""
        self.active[player_index] = False
        other = 1 - player_index
        other_conn = self.players[other]
        print(f"[ROOM {self.room_id}] {self.names[player_index]} ayrildi.")
        if self.active[other] and other_conn:
            send_msg(other_conn, {
                "type":    "opponent_disconnected",
                "message": f"{self.names[player_index]} oyundan ayrildi.",
            })
            print(f"[ROOM {self.room_id}] Bildirim gonderildi.")

    def _finish_game(self):
        totals  = self.state.get_totals()
        winner  = self.state.get_winner()
        winner_name = "Beraberlik!" if winner == -1 else self.names[winner]
        result = {
            "type":           "game_over",
            "totals":         totals,
            "winner":         winner,
            "winner_name":    winner_name,
            "scores":         [{k:v for k,v in self.state.scores[i].items()} for i in range(2)],
            "yahtzee_bonus":  self.state.yahtzee_bonus,
            "names":          self.names,
        }
        self.broadcast(result)
        print(f"[ROOM {self.room_id}] Oyun bitti. Kazanan: {winner_name} ({totals[0]}-{totals[1]})")


# ─────────────────────────────────────────
#  OYUNCU THREAD
# ─────────────────────────────────────────

def player_thread(room: GameRoom, player_index: int):
    conn = room.players[player_index]
    name = room.names[player_index]
    print(f"[THREAD] {name} için thread başladı.")
    try:
        while True:
            msg = recv_msg(conn)
            if msg is None:
                break
            print(f"[MSG] {name}: {msg}")
            room.handle_message(player_index, msg)
    except Exception as e:
        print(f"[ERROR] {name}: {e}")
    finally:
        room.handle_disconnect(player_index)
        try: conn.close()
        except: pass


# ─────────────────────────────────────────
#  ANA SUNUCU
# ─────────────────────────────────────────

class YahtzeeServer:

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.room_counter = 0

    def start(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen(10)

        print(f"╔══════════════════════════════════════╗")
        print(f"║   YAHTZEE SERVER — {self.host}:{self.port}   ║")
        print(f"║   İki oyuncu bekleniyor...           ║")
        print(f"╚══════════════════════════════════════╝")

        while True:
            self.room_counter += 1
            room = GameRoom(self.room_counter)

            for slot in range(2):
                print(f"[SERVER] Oyuncu {slot+1} bekleniyor...")
                conn, addr = server_sock.accept()
                hello = recv_msg(conn)
                name  = hello.get("name", f"Oyuncu {slot+1}") if hello else f"Oyuncu {slot+1}"
                room.add_player(conn, addr, slot, name)
                send_msg(conn, {
                    "type":         "welcome",
                    "player_index": slot,
                    "name":         name,
                    "message":      f"Hoş geldin {name}! Sen Oyuncu {slot+1} olarak atandın."
                })
                if slot == 0:
                    send_msg(conn, {"type":"waiting","message":"İkinci oyuncu bekleniyor..."})

            room.broadcast({
                "type":    "game_start",
                "message": "Her iki oyuncu bağlandı! Oyun başlıyor...",
                "names":   room.names,
            })
            room.send_state()

            for slot in range(2):
                t = threading.Thread(target=player_thread, args=(room, slot), daemon=True)
                t.start()

            print(f"[SERVER] Oda {self.room_counter} aktif.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()
    server = YahtzeeServer(host=args.host, port=args.port)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[SERVER] Kapatılıyor...")
        sys.exit(0)
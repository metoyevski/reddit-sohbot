import json
import os
import time
from config import USER_ARCHIVE_FILE, ARCHIVE_SAVE_INTERVAL

class UserArchiveManager:
    def __init__(self, archive_file_path=USER_ARCHIVE_FILE):
        self.archive_file_path = archive_file_path
        self.user_messages = self._load_archive()
        self.unsaved_message_count = 0
        print(f"[{time.strftime('%H:%M:%S')}] Kullanıcı mesaj arşivi yüklendi/oluşturuldu: {self.archive_file_path}")

    def _load_archive(self):
        if os.path.exists(self.archive_file_path):
            try:
                with open(self.archive_file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[{time.strftime('%H:%M:%S')}] Arşiv dosyası okuma hatası ({self.archive_file_path}): {e}. Yeni arşiv oluşturuluyor.")
                return {}
        return {}

    def _save_archive(self):
        try:
            with open(self.archive_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.user_messages, f, ensure_ascii=False, indent=4)
            self.unsaved_message_count = 0
            return True
        except IOError as e:
            print(f"[{time.strftime('%H:%M:%S')}] Arşiv dosyasına yazma hatası ({self.archive_file_path}): {e}")
            return False

    def log_message(self, username, message_content, timestamp_str):
        if not username or username == "BilinmeyenKullanici":
            return

        if username not in self.user_messages:
            self.user_messages[username] = []
        
        self.user_messages[username].append({
            'timestamp': timestamp_str,
            'content': message_content
        })
        self.unsaved_message_count += 1
        if self.unsaved_message_count >= ARCHIVE_SAVE_INTERVAL:
            if self._save_archive():
                 print(f"[{time.strftime('%H:%M:%S')}] Kullanıcı mesaj arşivi periyodik olarak kaydedildi.")

    def force_save(self):
        if self.unsaved_message_count > 0:
            print(f"[{time.strftime('%H:%M:%S')}] Kalan {self.unsaved_message_count} mesaj için arşiv kaydediliyor...")
            self._save_archive()
        else:
            pass
# --- START OF FILE config.py ---

# ======= KULLANICI AYARLARI =======
CHAT_LINK = "https://chat.reddit.com/room/!6o33yjMRTLajji5deGy62g%3Areddit.com" # ÖRNEK LİNK

# --- Chat Relay Ayarları (YENİ) ---
# Bu ayarlar, bot.py'nin yerel chat-relay sunucusuna bağlanmasını sağlar.
CHAT_RELAY_BASE_URL = "http://localhost:3003/v1/chat/completions"
# AI Studio ile çalışmak için 'gemini-pro' kullanıyoruz. ChatGPT için 'chatgpt' kullanabilirsiniz.
CHAT_RELAY_MODEL_ID = "chatgpt"
# Sunucudan yanıt beklerken zaman aşımı süresi (saniye cinsinden).
CHAT_RELAY_TIMEOUT_SECONDS = 180

# --- Diğer Bot Ayarları ---
BOT_OWN_USERNAME = "arkadasimoIamazsin"  # BOTUNUZUN REDDIT KULLANICI ADINI GİRİN (Büyük/küçük harf önemli olabilir)

CONTEXT_WINDOW_SIZE = 400  # 420 * 1.5 = 630
CONTEXT_PROMPT_USER_MESSAGES = 66  # 60 * 1.5 = 90
CONTEXT_PROMPT_AI_RESPONSES = 23  # 15 * 1.5 = 22.5 ≈ 23

MAX_RESPONSE_WORDS = 400 # Bu hala botun kendi içindeki kısaltma mekanizması için geçerli
INITIAL_MESSAGES_TO_READ = 40 # 50 * 1.5 = 75, daha sağlam bir başlangıç için artırıldı

USER_ARCHIVE_FILE = "user_message_archive.json"
ARCHIVE_SAVE_INTERVAL = 10

# Selenium Ayarları
LOGIN_WAIT_TIME = 15
PAGE_LOAD_TIMEOUT = 30
ELEMENT_WAIT_TIMEOUT = 25  # Timeout for finding individual elements
DOM_REINITIALIZE_WAIT = 5 # DOM'un oturması için bekleme süresi artırıldı
MESSAGE_TEXT_WAIT = 0.5 # Yeni mesaj okuma metodunda bu daha az kritik olacak
INITIAL_SCAN_MAX_WAIT = 20
INITIAL_SCAN_INTERVAL = 1.5
MAIN_LOOP_SLEEP = 0.2  # 0.5'ten 0.2'ye düşürüldü - daha responsive real-time
PERIODIC_DOM_CHECK_INTERVAL_LOOPS = 120

# === ESKİ AYARLAR (Artık Aktif Kullanılmıyor) ===
# Shadow root bulma denemeleri artık message_manager'ın esnek yapısı içinde ele alınıyor.
# SHADOW_ROOT_MAX_ATTEMPTS = 12
# SHADOW_ROOT_RETRY_INTERVAL = 0.75
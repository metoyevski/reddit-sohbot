import time
import traceback
from bot import RedditChatBot
from config import BOT_OWN_USERNAME, CHAT_RELAY_BASE_URL, CHAT_RELAY_MODEL_ID

if __name__ == "__main__":
    valid_config = True
    if not BOT_OWN_USERNAME or BOT_OWN_USERNAME == "arkada2simoIamazsin": # Placeholder kontrolü
        print("LÜTFEN 'config.py' DOSYASINDAKİ BOT_OWN_USERNAME DEĞİŞKENİNİ BOTUNUZUN REDDIT KULLANICI ADIYLA GÜNCELLEYİN.")
        valid_config = False
    
    if not CHAT_RELAY_BASE_URL:
        print("LÜTFEN 'config.py' DOSYASINDAKİ CHAT_RELAY_BASE_URL DEĞİŞKENİNİ AYARLAYIN.")
        valid_config = False
    if not CHAT_RELAY_MODEL_ID:
        print("LÜTFEN 'config.py' DOSYASINDAKİ CHAT_RELAY_MODEL_ID DEĞİŞKENİNİ AYARLAYIN (örn: 'gemini-pro').")
        valid_config = False

    if not valid_config:
        print("Yapılandırma eksik veya hatalı. Program sonlandırılıyor.")
    else:
        bot_instance = None
        try:
            bot_instance = RedditChatBot()
            if bot_instance.initialize():
                bot_instance.run()
            else:
                print(f"[{time.strftime('%H:%M:%S')}] Bot başlatılamadı! Lütfen hata mesajlarını kontrol edin.")
        except KeyboardInterrupt:
            print(f"\n[{time.strftime('%H:%M:%S')}] Program kullanıcı tarafından durduruldu.")
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Genel program hatası: {e}")
            print(traceback.format_exc())
        finally:
            if bot_instance:
                bot_instance.cleanup()
            print(f"[{time.strftime('%H:%M:%S')}] Program sonlandı.")
import time
import traceback
from datetime import datetime
import requests
import json

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException, NoSuchWindowException, TimeoutException
)

from config import (
    CHAT_RELAY_BASE_URL,
    CHAT_RELAY_MODEL_ID,
    CHAT_RELAY_TIMEOUT_SECONDS,
    CHAT_LINK, BOT_OWN_USERNAME, MAX_RESPONSE_WORDS,
    CONTEXT_WINDOW_SIZE,
    INITIAL_MESSAGES_TO_READ, LOGIN_WAIT_TIME, PAGE_LOAD_TIMEOUT,
    MAIN_LOOP_SLEEP, PERIODIC_DOM_CHECK_INTERVAL_LOOPS
)
from archive_manager import UserArchiveManager
from context_manager import ContextManager
from dom_manager import ChatDOMManager
from message_manager import MessageManager

class RedditChatBot:
    def __init__(self):
        self.chat_relay_url = CHAT_RELAY_BASE_URL
        self.chat_relay_model = CHAT_RELAY_MODEL_ID
        self.chat_relay_timeout = CHAT_RELAY_TIMEOUT_SECONDS
        
        self.chat_link = CHAT_LINK
        self.bot_username = BOT_OWN_USERNAME
        self.driver = None
        self.dom_manager = None
        self.message_manager = None
        self.context_manager_instance = ContextManager(max_size=CONTEXT_WINDOW_SIZE)
        self.user_archive_manager = UserArchiveManager()
        self.initial_scan_complete_time = None
        self.MESSAGE_SEND_DELAY = 2.5 # Hafifçe ayarlandı
        self.DAN_SYSTEM_PROMPT = f"""Eleştirel ve sorgulayıcı bir yapay zekâ asistanısın. Bu bağlamda, sana /ai ile yazılan promptları alacaksın ve u/username (mesela u/birbenimiunuttalar) diyerek kim yazdıysa onun sorusuna düzgünce, felsefî temellendirilmiş yanıt vereceksin. Yanıtlarında her daim bir taraf tutacaksın ve hangi taraf daha rasyonelse, felsefÎ bir biçimde gerekçelendirerek onun neden haklı olduğunu söyleyeceksin. Asla tarafsız olmayacaksın:"""

    def initialize(self):
        try:
            print(f"[{time.strftime('%H:%M:%S')}] Yapay Zeka Modu: Chat Relay (Model: {self.chat_relay_model})")
            options = webdriver.ChromeOptions()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            options.add_argument('--log-level=3')
            # options.add_argument("--headless") # Gerekirse açılabilir
            self.driver = webdriver.Chrome(options=options)
            self.driver.maximize_window()
            
            # Login sayfasına git
            self.driver.get("https://www.reddit.com/login/")
            print(f"[{time.strftime('%H:%M:%S')}] Lütfen Reddit'e giriş yapın...")
            print(f"[{time.strftime('%H:%M:%S')}] Giriş için {LOGIN_WAIT_TIME} saniye bekleniyor...")
            time.sleep(LOGIN_WAIT_TIME)
            
            print(f"[{time.strftime('%H:%M:%S')}] Chat linkine gidiliyor: {self.chat_link}")
            self.driver.get(self.chat_link)
            WebDriverWait(self.driver, PAGE_LOAD_TIMEOUT).until(EC.url_contains("chat.reddit.com"))
            print(f"[{time.strftime('%H:%M:%S')}] Chat sayfasına başarıyla gidildi.")

            # Sayfanın tam yüklenmesi için ekstra bekleme
            print(f"[{time.strftime('%H:%M:%S')}] Chat arayüzünün yüklenmesi için bekleniliyor...")
            time.sleep(5)

            # DOM Manager'ı initialize et
            self.dom_manager = ChatDOMManager(self.driver)
            
            # İlk olarak sayfa durumunu debug et
            print(f"[{time.strftime('%H:%M:%S')}] Sayfa durumu kontrol ediliyor...")
            self.dom_manager.debug_current_page()
            
            # URL kontrolü: Eğer hala login sayfasındaysa, chat'e gitmek için alternatif strateji
            current_url = self.driver.current_url
            if 'login' in current_url:
                print(f"[{time.strftime('%H:%M:%S')}] UYARI: Hala login sayfasındasınız! Chat linkine yönlendirme deneniyor...")
                # Doğrudan chat linkine gitmeyi dene
                self.driver.get(self.chat_link)
                time.sleep(10)  # Chat arayüzünün yüklenmesini bekle
                current_url = self.driver.current_url
                print(f"[{time.strftime('%H:%M:%S')}] Yeni URL: {current_url}")
                
                if 'login' in current_url:
                    print(f"[{time.strftime('%H:%M:%S')}] ⚠️ HALA LOGIN SAYFASINDA! Manuel giriş gerekebilir.")
                    print(f"[{time.strftime('%H:%M:%S')}] Lütfen tarayıcıda Reddit'e giriş yapın ve chat sayfasına gidin.")
                    input("Giriş yaptıktan sonra Enter'a basın...")
                    # Kullanıcının giriş yapmasını bekle
                    time.sleep(5)
            
            # DOM elementlerini initialize etmeyi dene, başarısız olursa alternatif stratejiler uygula
            max_dom_retries = 2  # Daha az deneme, daha hızlı
            dom_retry_count = 0
            dom_initialization_successful = False
            
            while dom_retry_count < max_dom_retries:
                print(f"[{time.strftime('%H:%M:%S')}] DOM initialize denemesi {dom_retry_count + 1}/{max_dom_retries}...")
                
                if self.dom_manager.reinitialize_dom_elements():
                    print(f"[{time.strftime('%H:%M:%S')}] DOM başarıyla initialize edildi!")
                    dom_initialization_successful = True
                    break
                else:
                    dom_retry_count += 1
                    if dom_retry_count < max_dom_retries:
                        print(f"[{time.strftime('%H:%M:%S')}] DOM initialize başarısız. 5s sonra tekrar deneniyor...")
                        time.sleep(5)
                    
            # Eğer DOM initialize başarısız olursa, sadece mesaj okumayı test et
            if not dom_initialization_successful:
                print(f"[{time.strftime('%H:%M:%S')}] ⚠️ DOM initialization başarısız oldu.")
                print(f"[{time.strftime('%H:%M:%S')}] 📖 SADECE MESAJ OKUMA MOD'UNA geçiliyor...")
                print(f"[{time.strftime('%H:%M:%S')}] (Mesaj gönderme çalışmayacak, sadece mesaj okuma test edilecek)")
                
                # Sadece mesaj okuma için minimal DOM manager oluştur
                self.dom_manager.dom_elements = {}  # Boş dict, mesaj gönderme çalışmayacak
            
            # Her şey yolundaysa veya read-only modda, MessageManager'ı initialize et
            self.message_manager = MessageManager(self.dom_manager, self.context_manager_instance, self.bot_username)
            print(f"[{time.strftime('%H:%M:%S')}] Bot başarıyla initialize edildi! Bot adı: {self.bot_username}")
            return True
            
        except TimeoutException as te:
            print(f"[{time.strftime('%H:%M:%S')}] Bot initialize hatası (TimeoutException): Sayfa yüklenirken zaman aşımı. {te}")
            print(f"[{time.strftime('%H:%M:%S')}] OLASI ÇÖZÜMLER:")
            print(f"[{time.strftime('%H:%M:%S')}] 1. İnternet bağlantınızı kontrol edin")
            print(f"[{time.strftime('%H:%M:%S')}] 2. config.py'deki PAGE_LOAD_TIMEOUT değerini artırın")
            print(f"[{time.strftime('%H:%M:%S')}] 3. Chat linkinin doğru olduğundan emin olun")
            print(traceback.format_exc())
            return False
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Bot initialize genel hatası: {e}")
            print(traceback.format_exc())
            return False

    def populate_initial_context(self):
        print(f"[{time.strftime('%H:%M:%S')}] Başlangıç bağlamı toplanıyor (yeni akıllı yöntemle)...")
        try:
            # Yeni yöntemle başlangıç mesajlarını al
            initial_messages = self.message_manager.get_last_n_messages(n=INITIAL_MESSAGES_TO_READ, initial_scan=True)
            if not initial_messages:
                 print(f"[{time.strftime('%H:%M:%S')}] Başlangıç taramasında hiç mesaj bulunamadı.")
                 return

            print(f"[{time.strftime('%H:%M:%S')}] Başlangıç için {len(initial_messages)} mesaj işleniyor...")
            # Mesajlar zaten eskiden yeniye doğru geliyor, bu yüzden ters çevirmemize gerek yok.
            for msg_data in reversed(initial_messages): # En yeniden eskiye doğru işleyerek bağlamı doldur
                text, user, msg_id, timestamp = msg_data['text'], msg_data['user'], msg_data['id'], msg_data['timestamp']
                
                if msg_id in self.message_manager.processed_event_ids: continue
                
                # Botun kendi mesajlarını kendi bağlamına ekle
                if user.lower() == self.bot_username.lower():
                    self.context_manager_instance.add_my_response(text, self.create_response_summary(text), timestamp)
                else: # Diğer kullanıcıların mesajları
                    self.context_manager_instance.add_user_message(user, text, timestamp)
                    if user != "BilinmeyenKullanici":
                        self.user_archive_manager.log_message(user, text, timestamp)
                
                self.message_manager.processed_event_ids.add(msg_id)

            # Son görülen mesajı ayarla (listeyi ters çevirdiğimiz için ilki en yeniydi)
            self.message_manager.last_seen_message_content = initial_messages[0]['text']
            self.message_manager.last_seen_message_user = initial_messages[0]['user']
            
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Başlangıç bağlamı toplama hatası: {e}")
            print(traceback.format_exc())
        finally:
            self.initial_scan_complete_time = datetime.now()
            print(f"[{time.strftime('%H:%M:%S')}] Başlangıç taraması tamamlandı.")
            self.user_archive_manager.force_save()

    # Bu yardımcı fonksiyonlar değişmedi
    def filter_non_bmp_chars(self, text):
        if not text: return ""
        return "".join(char for char in text if ord(char) <= 0xFFFF)

    def shorten_reply(self, text, max_words=MAX_RESPONSE_WORDS):
        if not text: return ""
        words = text.split()
        if len(words) > max_words: return " ".join(words[:max_words]) + "..."
        return text

    def create_response_summary(self, response):
        words = response.split();
        if len(words) <= 30: return response
        else: summary = " ".join(words[:25]); return f"{summary}... (detaylı yanıt verildi)"
    
    def generate_ai_response(self, prompt_from_message_manager):
        try:
            payload = {
                "model": self.chat_relay_model,
                "messages": [
                    {"role": "system", "content": self.DAN_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_from_message_manager}
                ], "temperature": 0.7,
            }
            headers = {"Content-Type": "application/json"}
            response = requests.post(self.chat_relay_url, headers=headers, json=payload, timeout=self.chat_relay_timeout)

            if response.status_code != 200:
                print(f"[{time.strftime('%H:%M:%S')}] HATA: Sunucu yanıtı {response.status_code}. Yanıt: {response.text[:500]}")
                return f"Üzgünüm, AI servisinden bir hata alındı (Kod: {response.status_code})."

            response_data = json.loads(response.content.decode('utf-8'))
            if not response_data.get('choices') or not response_data['choices'][0].get('message') or not response_data['choices'][0]['message'].get('content'):
                 print(f"[{time.strftime('%H:%M:%S')}] HATA: Yanıt beklenen formatta değil. Yanıt: {response_data}")
                 return "Üzgünüm, yanıt formatı geçersiz."
            
            raw_reply_from_api = response_data['choices'][0]['message']['content']
            filtered_reply_chars = self.filter_non_bmp_chars(raw_reply_from_api)
            summary_for_context = self.create_response_summary(filtered_reply_chars)
            self.context_manager_instance.add_my_response(filtered_reply_chars, summary_for_context)
            
            return filtered_reply_chars

        except requests.exceptions.Timeout:
            return f"Üzgünüm, AI yanıtı zaman aşımına uğradı ({self.chat_relay_timeout}s)."
        except requests.exceptions.ConnectionError:
            return "Üzgünüm, Chat Relay sunucusuna bağlanılamadı."
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] AI yanıt oluşturma hatası: {e}")
            print(traceback.format_exc())
            return "Üzgünüm, yanıt oluştururken beklenmedik bir sorun oluştu."

    def run(self):
        print("\n" + "="*50)
        print(f"[{time.strftime('%H:%M:%S')}] BOT ÇALIŞMAYA BAŞLADI!")
        print(f"[{time.strftime('%H:%M:%S')}] Mesajlar arası bekleme: {self.MESSAGE_SEND_DELAY} saniye.")
        print("="*50 + "\n")

        self.populate_initial_context()
        
        consecutive_dom_failures = 0
        max_consecutive_failures = 5
        
        while True:
            try:
                # DOM sağlığı artık sadece mesaj gönderme yeteneğini kontrol ediyor.
                if not self.dom_manager.is_dom_healthy():
                    consecutive_dom_failures += 1
                    print(f"[{time.strftime('%H:%M:%S')}] Ana döngü: DOM sağlıksız ({consecutive_dom_failures}/{max_consecutive_failures}). Mesaj gönderme alanı kayıp.")
                    
                    if consecutive_dom_failures >= max_consecutive_failures:
                        print(f"[{time.strftime('%H:%M:%S')}] KRİTİK: {max_consecutive_failures} ardışık DOM hatası. Bot durdurulacak.")
                        print(f"[{time.strftime('%H:%M:%S')}] OLASI NEDENLER:")
                        print(f"[{time.strftime('%H:%M:%S')}] 1. Reddit'in arayüzü değişti")
                        print(f"[{time.strftime('%H:%M:%S')}] 2. Sohbet oturumunuz sona erdi")
                        print(f"[{time.strftime('%H:%M:%S')}] 3. İnternet bağlantısı sorunları")
                        break
                    
                    print(f"[{time.strftime('%H:%M:%S')}] Yeniden initialize deneniyor...")
                    if not self.dom_manager.reinitialize_dom_elements():
                        print(f"[{time.strftime('%H:%M:%S')}] DOM yeniden initialize edilemedi. 10s sonra tekrar denenecek.")
                        time.sleep(10)
                        continue
                    else:
                        consecutive_dom_failures = 0  # Başarılı olunca counter'ı sıfırla
                        print(f"[{time.strftime('%H:%M:%S')}] DOM başarıyla yeniden initialize edildi!")
                else:
                    consecutive_dom_failures = 0  # DOM sağlıklıysa counter'ı sıfırla
                
                # Yeni ve güçlü mesaj alma fonksiyonumuzu kullanıyoruz.
                current_message_content, current_username, current_msg_id, current_msg_timestamp = self.message_manager.get_last_message_with_user()

                if not current_msg_id: 
                    time.sleep(MAIN_LOOP_SLEEP)
                    continue

                # Yeni bir mesaj olup olmadığını kontrol et
                is_new_message = current_msg_id not in self.message_manager.processed_event_ids

                if is_new_message:
                    # Botun kendi mesajını görmezden gel
                    if current_username.lower() == self.bot_username.lower():
                        self.message_manager.processed_event_ids.add(current_msg_id)
                        continue

                    print(f"[{time.strftime('%H:%M:%S')}] YENİ MESAJ - {current_username}: {current_message_content[:70]}...")

                    # Arşive ve bağlama ekle
                    if current_username != "BilinmeyenKullanici":
                        self.user_archive_manager.log_message(current_username, current_message_content, current_msg_timestamp)

                    # handle_message_for_context şimdi daha önemli, çünkü /ai komutlarını ayıklıyor
                    ai_prompt_for_model = self.message_manager.handle_message_for_context(
                        current_message_content, current_username, current_msg_id, 
                        current_msg_timestamp, self.initial_scan_complete_time, False
                    )

                    # Eğer bir /ai komutu varsa ve yanıtlanması gerekiyorsa
                    if ai_prompt_for_model:
                        ai_response_full = self.generate_ai_response(ai_prompt_for_model)
                        if ai_response_full and ai_response_full.strip():
                            # Paragraflara ayırıp gönderme mantığı aynı kaldı
                            paragraphs = [p.strip() for p in ai_response_full.split('\n') if p.strip()]
                            if not paragraphs:
                                paragraphs = [ai_response_full.strip()]

                            print(f"[{time.strftime('%H:%M:%S')}] Yanıt {len(paragraphs)} parçaya bölündü.")
                            for i, paragraph_raw in enumerate(paragraphs):
                                paragraph_to_send = self.shorten_reply(paragraph_raw, max_words=MAX_RESPONSE_WORDS)
                                if not paragraph_to_send: continue
                                
                                # Göndermeden önce son bir DOM kontrolü
                                if not self.dom_manager.is_dom_healthy():
                                    print(f"[{time.strftime('%H:%M:%S')}] Mesaj gönderimi iptal edildi, DOM sağlıksız.")
                                    break
                                
                                if self.message_manager.send_message(paragraph_to_send):
                                    print(f"[{time.strftime('%H:%M:%S')}] YANIT PARÇASI ({i+1}/{len(paragraphs)}) GÖNDERİLDİ...")
                                else:
                                    print(f"[{time.strftime('%H:%M:%S')}] YANIT PARÇASI GÖNDERİLEMEDİ! Döngüye devam ediliyor.")
                                    break 
                                
                                if i < len(paragraphs) - 1:
                                    time.sleep(self.MESSAGE_SEND_DELAY)
                    
                    # Bu mesajın işlendiğini işaretle
                    self.message_manager.processed_event_ids.add(current_msg_id)
                
                time.sleep(MAIN_LOOP_SLEEP)

            except KeyboardInterrupt: 
                print(f"\n[{time.strftime('%H:%M:%S')}] Program kullanıcı tarafından durduruluyor...")
                break
            except (NoSuchWindowException, WebDriverException) as e:
                if "target window already closed" in str(e).lower() or "no such window" in str(e).lower() or "disconnected" in str(e).lower():
                    print(f"[{time.strftime('%H:%M:%S')}] Tarayıcı penceresi kapatıldı veya bağlantı kesildi. Program sonlandırılıyor.")
                    break
                print(f"[{time.strftime('%H:%M:%S')}] Ana döngüde WebDriverException: {e}")
                print(traceback.format_exc())
                time.sleep(5)
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Ana döngüde beklenmedik genel hata: {e}")
                print(traceback.format_exc())
                time.sleep(5)

    def cleanup(self):
        try:
            if self.user_archive_manager: 
                print(f"[{time.strftime('%H:%M:%S')}] Kapanış: Arşiv kaydediliyor...")
                self.user_archive_manager.force_save()
            if self.driver: 
                print(f"[{time.strftime('%H:%M:%S')}] Kapanış: Chrome driver kapatılıyor...")
                self.driver.quit()
                print(f"[{time.strftime('%H:%M:%S')}] Chrome driver kapatıldı.")
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Temizlik (cleanup) hatası: {e}")
            print(traceback.format_exc())
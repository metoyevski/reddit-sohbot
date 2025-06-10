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
    MAIN_LOOP_SLEEP, PERIODIC_DOM_CHECK_INTERVAL_LOOPS,
    BOT_GRACE_PERIOD_SECONDS
)
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
        self.initial_scan_complete_time = None
        self.MESSAGE_SEND_DELAY = 2.5 # Hafifçe ayarlandı
        
        # Grace Period - Bot başladıktan sonra eski mesajlara yanıt vermemek için
        self.grace_period_start_time = None
        self.grace_period_active = True
        
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
        
        # Başlangıçta TÜM mesajları al (filtreleme JavaScript tarafında yapılıyor)
        initial_messages = self.message_manager.get_last_n_messages(
            n=INITIAL_MESSAGES_TO_READ, 
            initial_scan=True
        )
        
        if not initial_messages:
            print(f"[{time.strftime('%H:%M:%S')}] Başlangıç taramasında hiç mesaj bulunamadı.")
            return

        print(f"[{time.strftime('%H:%M:%S')}] Başlangıç için {len(initial_messages)} mesaj işleniyor...")
        # Mesajlar artık doğru chronological sırada geliyorlar (eskiden yeniye)
        # Bu yüzden sırayı bozmaya gerek yok
        ai_commands_found = 0
        total_processed = 0
        
        for msg_data in initial_messages:
            text, user, msg_id, timestamp = msg_data['text'], msg_data['user'], msg_data['id'], msg_data['timestamp']
            
            if msg_id in self.message_manager.processed_event_ids: continue
            
            # Başlangıç taramasında /ai komutlarını say (ama yanıtlama - bu sadece bilgi için)
            if text.startswith("/ai "):
                ai_commands_found += 1
                print(f"[{time.strftime('%H:%M:%S')}] 🤖 Başlangıç: /ai komutu bağlama eklendi (yanıtlanmayacak): '{text[:40]}...' (K: {user})")
            
            # Botun kendi mesajlarını kendi bağlamına ekle - hem gerçek username hem HAZIRCEVAP kontrolü
            is_bot_message = (user.lower() == self.bot_username.lower() or 
                            user.lower().startswith('hazircevap'))
            
            if is_bot_message:
                self.context_manager_instance.add_my_response(text, self.create_response_summary(text), timestamp)
            else: # Diğer kullanıcıların mesajları
                self.context_manager_instance.add_user_message(user, text, timestamp)
            
            self.message_manager.processed_event_ids.add(msg_id)
            total_processed += 1

        # Son görülen mesajı ayarla (artık en yeni mesaj listede en sonda)
        self.message_manager.last_seen_message_content = initial_messages[-1]['text']
        self.message_manager.last_seen_message_user = initial_messages[-1]['user']
        
        self.initial_scan_complete_time = datetime.now()
        print(f"[{time.strftime('%H:%M:%S')}] ✅ Başlangıç taraması tamamlandı!")
        print(f"[{time.strftime('%H:%M:%S')}] 📊 İstatistik: {total_processed} mesaj işlendi, {ai_commands_found} adet /ai komutu bulundu (yanıtlanmadı)")
        print(f"[{time.strftime('%H:%M:%S')}] ⏰ initial_scan_complete_time SET EDİLDİ: {self.initial_scan_complete_time}")
        print(f"[{time.strftime('%H:%M:%S')}] 🚀 Bot hazır! Artık yeni /ai komutlarına yanıt verecek.")

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
    
    def filter_thinking_mode(self, raw_response):
        """
        AI Studio thinking mode yanıtlarını filtreler, sadece final answer'ı döndürür.
        """
        if not raw_response:
            return raw_response
            
        # Thinking mode pattern'lerini temizle
        lines = raw_response.split('\n')
        filtered_lines = []
        skip_mode = False
        
        thinking_patterns = [
            "**Initiating", "**Expanding", "**Research", "**Analysis", 
            "**Thinking", "**Processing", "**Examining", "**Delving",
            "**Starting", "**Beginning", "**Continuing"
        ]
        
        for line in lines:
            line_stripped = line.strip()
            
            # Thinking mode başlığı tespit et
            is_thinking_header = any(pattern in line_stripped for pattern in thinking_patterns)
            
            if is_thinking_header:
                skip_mode = True
                continue
                
            # Boş satır thinking mode'u bitirebilir (ama emin olmak için devam et)
            if not line_stripped:
                if skip_mode:
                    # Bir sonraki içerikli satıra bak, thinking devam ediyor mu?
                    continue
                else:
                    filtered_lines.append(line)
                    continue
            
            # Normal metin - thinking mode değilse ekle
            if not skip_mode:
                filtered_lines.append(line)
            else:
                # Thinking mode'dayken gerçek yanıt başlayabilir
                # u/ ile başlıyorsa (kullanıcı mention) veya normal cümle ise thinking bitti
                if (line_stripped.startswith('u/') or 
                    (len(line_stripped.split()) > 3 and not any(pattern in line_stripped for pattern in thinking_patterns))):
                    skip_mode = False
                    filtered_lines.append(line)
        
        result = '\n'.join(filtered_lines).strip()
        
        # Eğer çok az içerik kaldıysa, son paragrafı al
        if len(result.split()) < 10:
            paragraphs = raw_response.split('\n\n')
            if len(paragraphs) > 1:
                # En son boş olmayan paragrafı al
                for p in reversed(paragraphs):
                    if p.strip() and len(p.split()) > 5:
                        result = p.strip()
                        break
        
        # Son kontrol - hala çok kısa ise orijinali döndür ama kırp
        if len(result.split()) < 5:
            # Orijinal yanıtın son 200 kelimesini al
            words = raw_response.split()
            if len(words) > 200:
                result = ' '.join(words[-200:])
            else:
                result = raw_response
        
        print(f"[{time.strftime('%H:%M:%S')}] 🧹 Thinking mode filtresi: {len(raw_response)} -> {len(result)} karakter")
        return result
    
    def generate_ai_response(self, prompt_from_message_manager):
        try:
            print(f"[{time.strftime('%H:%M:%S')}] 🌐 Chat Relay'e bağlanıyor: {self.chat_relay_url}")
            print(f"[{time.strftime('%H:%M:%S')}] 🤖 Model: {self.chat_relay_model}")
            
            payload = {
                "model": self.chat_relay_model,
                "messages": [
                    {"role": "system", "content": self.DAN_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_from_message_manager}
                ], "temperature": 0.7,
            }
            headers = {"Content-Type": "application/json"}
            
            # Kısa timeout ile dene
            short_timeout = 30  # 30 saniye
            print(f"[{time.strftime('%H:%M:%S')}] ⏳ HTTP POST gönderiliyor... (Timeout: {short_timeout}s)")
            
            response = requests.post(self.chat_relay_url, headers=headers, json=payload, timeout=short_timeout)
            
            print(f"[{time.strftime('%H:%M:%S')}] ✅ Yanıt alındı! Status: {response.status_code}")

            if response.status_code != 200:
                print(f"[{time.strftime('%H:%M:%S')}] HATA: Sunucu yanıtı {response.status_code}. Yanıt: {response.text[:500]}")
                return f"Üzgünüm, AI servisinden bir hata alındı (Kod: {response.status_code})."

            print(f"[{time.strftime('%H:%M:%S')}] 📄 JSON parse ediliyor...")
            response_data = json.loads(response.content.decode('utf-8'))
            
            if not response_data.get('choices') or not response_data['choices'][0].get('message') or not response_data['choices'][0]['message'].get('content'):
                 print(f"[{time.strftime('%H:%M:%S')}] HATA: Yanıt beklenen formatta değil. Yanıt: {response_data}")
                 return "Üzgünüm, yanıt formatı geçersiz."
            
            raw_reply_from_api = response_data['choices'][0]['message']['content']
            print(f"[{time.strftime('%H:%M:%S')}] 🎉 AI yanıtı başarıyla alındı! (Uzunluk: {len(raw_reply_from_api)} karakter)")
            
            # Thinking mode filtresi - sadece final answer'ı al
            filtered_reply = self.filter_thinking_mode(raw_reply_from_api)
            filtered_reply_chars = self.filter_non_bmp_chars(filtered_reply)
            summary_for_context = self.create_response_summary(filtered_reply_chars)
            self.context_manager_instance.add_my_response(filtered_reply_chars, summary_for_context)
            
            return filtered_reply_chars

        except requests.exceptions.Timeout:
            print(f"[{time.strftime('%H:%M:%S')}] ⏰ TIMEOUT: Chat Relay {short_timeout} saniyede yanıt vermedi!")
            return f"Üzgünüm, AI yanıtı zaman aşımına uğradı ({short_timeout}s). Chat Relay yavaş yanıt veriyor."
        except requests.exceptions.ConnectionError as e:
            print(f"[{time.strftime('%H:%M:%S')}] 🔌 BAĞLANTI HATASI: {e}")
            return "Üzgünüm, Chat Relay sunucusuna bağlanılamadı. Sunucu çalışıyor mu?"
        except json.JSONDecodeError as e:
            print(f"[{time.strftime('%H:%M:%S')}] 📄 JSON PARSE HATASI: {e}")
            print(f"[{time.strftime('%H:%M:%S')}] Yanıt metni: {response.text[:200]}...")
            return "Üzgünüm, Chat Relay'den gelen yanıt parse edilemedi."
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] ❌ GENEL HATA: {e}")
            print(traceback.format_exc())
            return "Üzgünüm, yanıt oluştururken beklenmedik bir sorun oluştu."

    def run(self):
        print("\n" + "="*50)
        print(f"[{time.strftime('%H:%M:%S')}] BOT ÇALIŞMAYA BAŞLADI!")
        print(f"[{time.strftime('%H:%M:%S')}] Mesajlar arası bekleme: {self.MESSAGE_SEND_DELAY} saniye.")
        print("="*50 + "\n")

        self.populate_initial_context()

        # Grace period'u başlangıç taraması SONRASINDA başlat
        self.grace_period_start_time = datetime.now()
        print(f"[{time.strftime('%H:%M:%S')}] 🕐 Grace Period başladı: {BOT_GRACE_PERIOD_SECONDS} saniye boyunca yanıt verilmeyecek.")
        
        consecutive_dom_failures = 0
        max_consecutive_failures = 5
        
        while True:
            try:
                # Grace period kontrolü
                if self.grace_period_active and self.grace_period_start_time:
                    elapsed_time = (datetime.now() - self.grace_period_start_time).total_seconds()
                    if elapsed_time >= BOT_GRACE_PERIOD_SECONDS:
                        self.grace_period_active = False
                        print(f"[{time.strftime('%H:%M:%S')}] ✅ Grace Period bitti! Artık yeni /ai komutlarına yanıt verilecek.")
                
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
                
                # --- Stabil, tekli mesaj işleme döngüsü ('old' versiyonundan ilhamla) ---
                current_message_content, current_username, current_msg_id, current_msg_timestamp = self.message_manager.get_last_message_with_user()

                if not current_msg_id: 
                    time.sleep(MAIN_LOOP_SLEEP)
                    continue

                # Yeni bir mesaj olup olmadığını kontrol et
                is_new_message = current_msg_id not in self.message_manager.processed_event_ids

                if is_new_message:
                    # Botun kendi mesajını ve diğer olası bot adlarını görmezden gel
                    is_bot_message = (current_username.lower() == self.bot_username.lower() or 
                                      current_username.lower().startswith('FelsefeGPT'))
                    
                    if is_bot_message:
                        self.message_manager.processed_event_ids.add(current_msg_id)
                        continue

                    print(f"[{time.strftime('%H:%M:%S')}] YENİ MESAJ - {current_username}: {current_message_content[:70]}...")

                    # handle_message_for_context şimdi /ai komutlarını ayıklıyor
                    ai_prompt_for_model = self.message_manager.handle_message_for_context(
                        current_message_content, current_username, current_msg_id, 
                        current_msg_timestamp, self.initial_scan_complete_time, 
                        is_already_marked_processed_in_loop=False # Artık döngü içinde işaretlenmediği için False
                    )

                    # Eğer bir /ai komutu varsa ve yanıtlanması gerekiyorsa
                    if ai_prompt_for_model:
                        # Grace period kontrolü - Grace period aktifse yanıt verme
                        if self.grace_period_active:
                            print(f"[{time.strftime('%H:%M:%S')}] 🕐 Grace Period aktif - /ai komutuna yanıt verilmiyor (mesaj bağlama eklendi)")
                        else:
                            print(f"[{time.strftime('%H:%M:%S')}] 🤖 AI yanıtı oluşturuluyor...")
                            ai_response_full = self.generate_ai_response(ai_prompt_for_model)
                            if ai_response_full and ai_response_full.strip():
                                final_response = self.shorten_reply(ai_response_full, max_words=MAX_RESPONSE_WORDS)
                                if self.dom_manager.is_dom_healthy():
                                    print(f"[{time.strftime('%H:%M:%S')}] 📤 AI yanıtı gönderiliyor... (Uzunluk: {len(final_response)} karakter)")
                                    if self.message_manager.send_message(final_response):
                                        print(f"[{time.strftime('%H:%M:%S')}] ✅ AI YANITI BAŞARIYLA GÖNDERİLDİ!")
                                    else:
                                        print(f"[{time.strftime('%H:%M:%S')}] ❌ AI YANITI GÖNDERİLEMEDİ!")
                                else:
                                    print(f"[{time.strftime('%H:%M:%S')}] Mesaj gönderimi iptal edildi, DOM sağlıksız.")
                            else:
                                print(f"[{time.strftime('%H:%M:%S')}] ❌ AI yanıtı boş veya hatalı!")
                                if self.message_manager.send_message("Üzgünüm, şu anda yanıt veremiyorum. Lütfen tekrar deneyin."):
                                    print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Hata mesajı gönderildi.")

                    # Bu mesajın işlendiğini en sonda işaretle
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
            if self.driver: 
                print(f"[{time.strftime('%H:%M:%S')}] Kapanış: Chrome driver kapatılıyor...")
                self.driver.quit()
                print(f"[{time.strftime('%H:%M:%S')}] Chrome driver kapatıldı.")
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Temizlik (cleanup) hatası: {e}")
            print(traceback.format_exc())
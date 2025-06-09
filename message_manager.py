# --- START OF FILE message_manager.py ---

import time
import json
import traceback
import hashlib
from datetime import datetime
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import JavascriptException
import pyperclip

from config import (
    INITIAL_MESSAGES_TO_READ
)

# Console'da Çalışan Gerçek Reddit Monitor - DOM/monitor.js'den alındı
MESSAGE_READER_JS = """
class RefreshFreeRedditMonitor {
    constructor() {
        this.version = "3.0.0";
        this.isActive = false;
        this.stats = {
            messagesFound: 0,
            newMessagesCaught: 0,
            aiCommandsDetected: 0,
            forceLoadAttempts: 0
        };
        
        // Tracking state
        this.lastMessageCount = 0;
        this.lastMessages = [];
        this.processedMessageIds = new Set();
        this.intervals = [];
        
        // Real-time config
        this.config = {
            checkInterval: 2000,        // 2 saniyede bir kontrol
            forceLoadInterval: 15000,   // 15 saniyede bir force load
            scrollTriggerInterval: 8000, // 8 saniyede bir scroll trigger
            maxConsecutiveNoChange: 10   // 10 kez değişiklik yoksa force action
        };
        
        this.consecutiveNoChange = 0;
        this.shadowElements = {};
        this.callbacks = [];
        
        console.log("🚀 Refresh-Free Reddit Monitor v3.0.0 başlatıldı!");
        this.initialize();
    }
    
    initialize() {
        this.findShadowElements();
        this.isActive = true;
        
        window.RefreshFreeMonitor = this;
        this.log("✅ Refresh-free monitor aktif!");
    }
    
    // SHADOW DOM ELEMENTLERİNİ BUL
    findShadowElements() {
        this.log("🔍 Shadow DOM elementleri aranıyor...");
        
        try {
            // rs-app shadow root
            const rsApp = document.querySelector('rs-app');
            if (rsApp && rsApp.shadowRoot) {
                this.shadowElements.rsApp = rsApp.shadowRoot;
                
                // rs-room shadow root
                const rsRoom = this.shadowElements.rsApp.querySelector('rs-room');
                if (rsRoom && rsRoom.shadowRoot) {
                    this.shadowElements.rsRoom = rsRoom.shadowRoot;
                    
                    // rs-timeline shadow root
                    const rsTimeline = this.shadowElements.rsRoom.querySelector('rs-timeline');
                    if (rsTimeline && rsTimeline.shadowRoot) {
                        this.shadowElements.rsTimeline = rsTimeline.shadowRoot;
                        
                        // rs-virtual-scroll shadow root
                        const virtualScroll = this.shadowElements.rsTimeline.querySelector('rs-virtual-scroll-dynamic');
                        if (virtualScroll && virtualScroll.shadowRoot) {
                            this.shadowElements.virtualScroll = virtualScroll.shadowRoot;
                        }
                    }
                    
                    // rs-message-composer shadow root
                    const rsComposer = this.shadowElements.rsRoom.querySelector('rs-message-composer');
                    if (rsComposer && rsComposer.shadowRoot) {
                        this.shadowElements.rsComposer = rsComposer.shadowRoot;
                    }
                }
            }
            
            this.log(`✅ Shadow elementler bulundu: ${Object.keys(this.shadowElements).length} adet`);
            return true;
        } catch (e) {
            this.log(`❌ Shadow element bulma hatası: ${e.message}`);
            return false;
        }
    }
    
    // DOM'DAN MESAJLARI AL
    getMessagesFromDOM() {
        if (!this.shadowElements.virtualScroll) {
            this.findShadowElements(); // Yeniden dene
            if (!this.shadowElements.virtualScroll) return [];
        }
        
        try {
            const timelineEvents = this.shadowElements.virtualScroll.querySelectorAll('rs-timeline-event');
            const messages = [];
            
            // İlk geçişte tüm kullanıcı adlarını topla (doğru sıralama için)
            let lastSeenAuthor = null;
            
            timelineEvents.forEach((event, index) => {
                const messageData = this.extractMessageData(event, index, lastSeenAuthor);
                if (messageData) {
                    messages.push(messageData);
                    // Eğer bu mesajda gerçek bir yazar varsa, bir sonraki için güncelle
                    if (messageData.author && messageData.author !== 'Bilinmeyen' && messageData.hasActualAuthor) {
                        lastSeenAuthor = messageData.author;
                    }
                }
            });
            
            return messages;
        } catch (e) {
            this.log(`❌ DOM mesaj alma hatası: ${e.message}`);
            return [];
        }
    }
    
    // MESAJ VERİSİNİ ÇIKAR - GELİŞTİRİLMİŞ KULLANICI TAKİBİ
    extractMessageData(eventElement, index, lastSeenAuthor) {
        try {
            if (!eventElement.shadowRoot) return null;
            
            const shadowRoot = eventElement.shadowRoot;
            
            // Mesaj metni
            let messageText = '';
            try {
                const textElement = shadowRoot.querySelector('div.room-message-text.truncated');
                if (textElement) {
                    messageText = textElement.textContent.trim();
                }
            } catch (e) {}
            
            // Yazar arama - geliştirilmiş mantık
            let author = null;
            let hasActualAuthor = false; // Gerçek yazar bulundu mu?
            
            try {
                const authorSelectors = [
                    'faceplate-tracker[noun="user_hovers"] > span[slot="trigger"]',
                    '.room-message-author',
                    'span.user-name',
                    'div[slot="author"] span',
                    '[data-testid*="author"] span'
                ];
                
                for (const selector of authorSelectors) {
                    const authorElement = shadowRoot.querySelector(selector);
                    if (authorElement) {
                        let authorText = authorElement.textContent.trim();
                        if (authorText.includes(' replied')) {
                            authorText = authorText.split(' replied')[0];
                        }
                        if (authorText.startsWith('u/')) {
                            authorText = authorText.substring(2);
                        }
                        if (authorText && authorText.length > 0) {
                            author = authorText;
                            hasActualAuthor = true;
                            this.log(`👤 Gerçek yazar bulundu: ${author}`);
                            break;
                        }
                    }
                }
                
                // Eğer gerçek yazar bulunamadıysa, son bilinen kullanıcıyı kullan
                if (!hasActualAuthor && lastSeenAuthor) {
                    author = lastSeenAuthor;
                    this.log(`🔄 Son bilinen kullanıcı kullanılıyor: ${author}`);
                } else if (!hasActualAuthor) {
                    author = 'Bilinmeyen';
                    this.log(`❓ Kullanıcı bulunamadı, 'Bilinmeyen' kullanılıyor`);
                }
                
            } catch (e) {
                // Hata durumunda da son bilinen kullanıcıyı dene
                if (lastSeenAuthor) {
                    author = lastSeenAuthor;
                } else {
                    author = 'Bilinmeyen';
                }
            }
            
            // Timestamp
            let timestamp = new Date().toLocaleTimeString('tr-TR');
            try {
                const timeElement = shadowRoot.querySelector('rs-timestamp time-stamp > span');
                if (timeElement) {
                    timestamp = timeElement.textContent.trim();
                }
            } catch (e) {}
            
            // TUTARLI ID oluştur (content-based, time-independent)
            const contentHash = btoa(messageText + author).substring(0, 16); // Base64 hash
            const id = `${author}_${contentHash}_${index}`;
            
            if (!messageText && !author) return null;
            
            return {
                id: id,
                text: messageText,
                author: author,
                timestamp: timestamp,
                element: eventElement,
                hasActualAuthor: hasActualAuthor // Gerçek yazar olup olmadığını işaretle
            };
            
        } catch (e) {
            return null;
        }
    }
    
    // EN SON MESAJLARI AL (mj2.js'deki getLatestMessages mantığı)
    getLatestMessages(count = 10) {
        const messages = this.getMessagesFromDOM();
        return messages.slice(-count);
    }
    
    // /AI KOMUTLARINI AL (mj2.js'deki getAICommands mantığı)
    getAICommands() {
        const messages = this.getMessagesFromDOM();
        return messages.filter(msg => msg.text.toLowerCase().startsWith('/ai '));
    }
    
    // LOG
    log(message) {
        console.log(`[RefreshFreeMonitor] ${message}`);
    }
    
    startTime = Date.now();
}

// BOT İÇİN MESAJ ALMA FONKSİYONU
try {
    const monitor = new RefreshFreeRedditMonitor();
    const allMessages = monitor.getMessagesFromDOM();
    
    // Bot'un istediği format için convert et
    const convertedMessages = allMessages.map(msg => ({
        text: msg.text,
        author: msg.author,
        timestamp: msg.timestamp,
        isOwn: msg.author.toLowerCase() === '%(bot_username)s'.toLowerCase()
    }));
    
    // En son N mesajı al
    const latestMessages = convertedMessages.slice(-%(message_limit)s);
    
    console.log(`[RefreshFreeMonitor] Bot için ${latestMessages.length} mesaj hazırlandı`);
    
    // Kullanıcı dağılımını göster (debug için)
    const userCounts = {};
    latestMessages.forEach(msg => {
        userCounts[msg.author] = (userCounts[msg.author] || 0) + 1;
    });
    console.log(`[RefreshFreeMonitor] Kullanıcı dağılımı:`, userCounts);
    
    return latestMessages;
} catch (e) {
    console.log(`[RefreshFreeMonitor] HATA: ${e.message}`);
    return [];
}
"""

class MessageManager:
    def __init__(self, dom_manager, context_manager_instance, bot_username):
        self.dom_manager = dom_manager
        self.context_manager = context_manager_instance
        self.bot_actual_username = bot_username
        self.last_seen_message_content = ""
        self.last_seen_message_user = ""
        self.processed_event_ids = set()

    def _clean_username(self, raw_username):
        if not raw_username:
            return "BilinmeyenKullanici"
        cleaned = raw_username.strip()
        if cleaned.startswith("u/"):
            cleaned = cleaned[2:]
        return cleaned if cleaned else "BilinmeyenKullanici"

    def _execute_message_reader_script(self, n):
        """
        Tarayıcıda JavaScript kodunu çalıştırır ve mesaj listesini alır.
        """
        try:
            # JS kodunu bot adı ve mesaj limiti ile formatla
            script_to_run = MESSAGE_READER_JS % {
                'bot_username': self.bot_actual_username,
                'message_limit': n
            }
            
            # Scripti çalıştır ve sonucu al
            messages_from_js = self.dom_manager.driver.execute_script(script_to_run)

            if not messages_from_js or not isinstance(messages_from_js, list):
                # print(f"[{time.strftime('%H:%M:%S')}] JS'den mesaj alınamadı veya format yanlış.")
                return []

            return messages_from_js
        except JavascriptException as e:
            print(f"[{time.strftime('%H:%M:%S')}] Mesaj okuma script'i çalıştırılırken JavaScript hatası: {e}")
            return []
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Mesaj okuma script'i çalıştırılırken genel hata: {e}")
            return []

    def get_last_n_messages(self, n=INITIAL_MESSAGES_TO_READ, initial_scan=False):
        """
        Yeni, akıllı JS tabanlı mesaj alma yöntemi.
        """
        raw_messages = self._execute_message_reader_script(n)
        if not raw_messages:
            return []

        processed_messages = []
        for msg_data in raw_messages:
            # JS'den gelen veriyi standart formatımıza çeviriyoruz
            author = self._clean_username(msg_data.get('author'))
            text = msg_data.get('text', '').strip()
            timestamp = msg_data.get('timestamp', datetime.now().strftime('%H:%M:%S'))
            
            # JavaScript'ten gelen ID'yi doğrudan kullan (artık tutarlı)
            js_id = msg_data.get('id', '')
            
            # Botun kendi mesajlarını doğru kullanıcı adıyla etiketle
            if msg_data.get('isOwn', False):
                author = self.bot_actual_username
            
            if not text:
                continue

            # JavaScript'ten gelen ID varsa onu kullan, yoksa fallback oluştur
            if js_id:
                msg_id = js_id
            else:
                # Fallback ID (JS'ten gelmeyen durumlar için)
                content_hash = hashlib.md5((text + author).encode()).hexdigest()[:8]
                msg_id = f"{author}_{content_hash}"

            processed_messages.append({
                'text': text,
                'user': author,
                'id': msg_id,
                'timestamp': timestamp
            })
        
        # JS kodumuz mesajları zaten doğru (eskiden yeniye) sırada veriyor.
        # Bot döngüsü en son mesajı beklediği için listeyi tersine çeviriyoruz.
        return list(reversed(processed_messages))

    def get_last_message_with_user(self):
        """
        En son mesajı ve yazarını alır.
        """
        try:
            # Son birkaç mesajı almak genellikle en son olanı doğru bulmak için yeterlidir.
            messages = self.get_last_n_messages(n=5, initial_scan=False)
            if messages:
                last_msg = messages[0] # Liste ters çevrildiği için ilk eleman en yenisidir.
                return last_msg['text'], last_msg['user'], last_msg['id'], last_msg['timestamp']
            return "", "BilinmeyenKullanici", None, None
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] get_last_message_with_user hatası: {e}")
            traceback.print_exc()
            return "", "BilinmeyenKullanici", None, None

    def send_message(self, message):
        """
        Mesaj gönderme fonksiyonu - Read-only modda uyarı verir
        """
        try:
            if not message or not message.strip():
                print(f"[{time.strftime('%H:%M:%S')}] UYARI: Boş mesaj gönderilmeye çalışıldı. Atlanıyor.")
                return True

            # Read-only mod kontrolü
            input_area = self.dom_manager.dom_elements.get('message_input_area')
            if not input_area:
                print(f"[{time.strftime('%H:%M:%S')}] READ-ONLY MOD: Mesaj gönderme alanı yok. Mesaj: '{message[:50]}...'")
                return False  # Mesaj gönderilmedi ama hata değil
            
            if not self.dom_manager.is_dom_healthy():
                print(f"[{time.strftime('%H:%M:%S')}] Mesaj göndermeden önce DOM sağlıksız, yeniden initialize deneniyor...")
                if not self.dom_manager.reinitialize_dom_elements():
                     print(f"[{time.strftime('%H:%M:%S')}] DOM yeniden initialize edilemedi, mesaj gönderilemiyor.")
                     return False
            
            input_area = self.dom_manager.dom_elements['message_input_area']
            
            original_clipboard_content = pyperclip.paste()
            pyperclip.copy(message)
            
            input_area.click()
            time.sleep(0.1)
            input_area.send_keys(Keys.CONTROL + "a")
            input_area.send_keys(Keys.DELETE)
            time.sleep(0.1)
            input_area.send_keys(Keys.CONTROL + "v")
            time.sleep(0.2)
            input_area.send_keys(Keys.ENTER)
            
            if original_clipboard_content is not None:
                pyperclip.copy(original_clipboard_content)
            else:
                try: pyperclip.copy("")
                except: pass

            return True
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Mesaj gönderme hatası: {e}")
            try: 
                if 'original_clipboard_content' in locals() and original_clipboard_content is not None: 
                    pyperclip.copy(original_clipboard_content)
                else: pyperclip.copy("")
            except Exception: pass
            return False

    def handle_message_for_context(self, message_content, username_original_case, msg_id, timestamp_str, initial_scan_complete_time, is_already_marked_processed_in_loop=False):
        """
        Bu fonksiyonda değişiklik yok. Gelen veriyi işleme mantığı aynı.
        """
        if username_original_case.lower() == self.bot_actual_username.lower():
            if msg_id and not is_already_marked_processed_in_loop and msg_id not in self.processed_event_ids:
                self.processed_event_ids.add(msg_id)
            return None

        is_ai_command = message_content.startswith("/ai ")
        should_add_to_context = False
        if msg_id:
            if not is_already_marked_processed_in_loop and msg_id not in self.processed_event_ids:
                should_add_to_context = True
        
        if should_add_to_context:
            self.context_manager.add_user_message(username_original_case, message_content, timestamp_str)
            if msg_id:
                self.processed_event_ids.add(msg_id)
            if is_ai_command and (initial_scan_complete_time is None):
                 print(f"[{time.strftime('%H:%M:%S')}] BAŞLANGIÇ /ai: '{message_content[:30]}...' (K: {username_original_case}) bağlama eklendi, yanıtlanmayacak.")

        if is_ai_command:
            should_respond_to_ai_command = False
            if initial_scan_complete_time is not None:
                # Başlangıç taraması bittikten sonra gelen her /ai komutuna yanıt ver
                if not msg_id or (msg_id and msg_id not in self.processed_event_ids):
                     should_respond_to_ai_command = True

            if should_respond_to_ai_command:
                user_prompt = message_content[len("/ai "):].strip()
                print(f"[{time.strftime('%H:%M:%S')}] YENİ /ai komutu '{user_prompt[:30]}...' (K: {username_original_case}) işleniyor...")
                context_string = self.context_manager.get_context_string()
                full_prompt = context_string + f"KULLANICI '{username_original_case}' şunu soruyor: {user_prompt}"
                return full_prompt
        return None
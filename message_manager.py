# --- START OF FILE message_manager.py ---

import time
import json
import traceback
import hashlib
from datetime import datetime
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import JavascriptException, TimeoutException

from config import (
    INITIAL_MESSAGES_TO_READ
)

# Console'da Çalışan Gerçek Reddit Monitor - DOM/monitor.js'den alındı ve geliştirildi
MESSAGE_READER_JS = """
return (function(processedIdsArray) {
    // ====================================================================================
    //              HYBRID MESSAGE READER (v5.1 - STABLE ID FIX)
    // - Fikri: 'monitor.js'in daha sağlam yazar bulma tekniği ile geliştirildi.
    // - Asla tekrar etmeyen, kriptografik ID üretimi korundu.
    // - Dışarıdan 'processedIds' alarak zaten işlenmiş mesajları filtreler.
    // - *** YENİ: Stabil ID üretilemeyen (örn. timestamp'ı olmayan) mesajları
    // - *** atlayarak sonsuz döngüye girmesini engeller.
    // ====================================================================================

    const processedIds = new Set(processedIdsArray || []);

    // 1. Shadow DOM elementlerini güvenilir bir şekilde bul
    // ------------------------------------------------------------------------------------
    let virtualScrollRoot = null;
    try {
        const rsApp = document.querySelector('rs-app');
        if (rsApp && rsApp.shadowRoot) {
            const rsRoom = rsApp.shadowRoot.querySelector('rs-room');
            if (rsRoom && rsRoom.shadowRoot) {
                const rsTimeline = rsRoom.shadowRoot.querySelector('rs-timeline');
                if (rsTimeline && rsTimeline.shadowRoot) {
                    const virtualScroll = rsTimeline.shadowRoot.querySelector('rs-virtual-scroll-dynamic');
                    if (virtualScroll && virtualScroll.shadowRoot) {
                        virtualScrollRoot = virtualScroll.shadowRoot;
                    }
                }
            }
        }
    } catch (e) {
        console.error("Hata: Shadow DOM bulunamadı!", e);
        return []; // Hata durumunda boş liste dön
    }

    if (!virtualScrollRoot) {
        console.error("Hata: Mesajların bulunduğu 'virtualScrollRoot' elementine ulaşılamadı.");
        return [];
    }
    
    // 2. Güvenilir ve Kriptografik ID Üretim Fonksiyonu
    // ------------------------------------------------------------------------------------
    const cyrb53 = (str, seed = 0) => {
        let h1 = 0xdeadbeef ^ seed, h2 = 0x41c6ce57 ^ seed;
        for(let i = 0, ch; i < str.length; i++) {
            ch = str.charCodeAt(i);
            h1 = Math.imul(h1 ^ ch, 2654435761);
            h2 = Math.imul(h2 ^ ch, 1597334677);
        }
        h1  = Math.imul(h1 ^ (h1 >>> 16), 2246822507);
        h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909);
        h2  = Math.imul(h2 ^ (h2 >>> 16), 2246822507);
        h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909);
        return 4294967296 * (2097151 & h2) + (h1 >>> 0);
    };

    // 3. Her mesaj elementi için veri çıkarma fonksiyonu
    // ------------------------------------------------------------------------------------
    function getMessageData(msgElement, index, lastKnownAuthor) {
        try {
            if (!msgElement || !msgElement.shadowRoot) return null;
            const shadowRoot = msgElement.shadowRoot;

            // Yazar (monitor.js'den gelen daha sağlam yöntem)
            let author = null;
            let authorFound = false;
            try {
                const authorSelectors = [
                    'span.user-name',
                    'faceplate-tracker[noun="user_hovers"] > span[slot="trigger"]',
                    '.room-message-author'
                ];
                for (const selector of authorSelectors) {
                    const authorElement = shadowRoot.querySelector(selector);
                    if (authorElement && authorElement.textContent.trim()) {
                        let authorText = authorElement.textContent.trim();
                        if (authorText.includes(' replied')) {
                            authorText = authorText.split(' replied')[0];
                        }
                        if (authorText.startsWith('u/')) {
                            authorText = authorText.substring(2);
                        }

                        // Eğer bulunan yazar metni '[deleted]' ise, bunu "bulunamadı" olarak
                        // kabul et ve aramaya devam et. Bu, son bilinen yazara geri
                        // dönmemizi sağlar.
                        if (authorText && authorText !== '[deleted]') {
                            author = authorText;
                            authorFound = true;
                            break;
                        }
                    }
                }
            } catch (e) { /* Yazar bulunamazsa null kalır */ }

            const messageText = shadowRoot.querySelector('div.room-message-text')?.textContent.trim() || '';
            if (!messageText) return null;
            
            // Eğer bu mesaj elementinde yeni bir yazar bulunamadıysa, son bilinen yazarı kullan.
            if (!authorFound && lastKnownAuthor) {
                author = lastKnownAuthor;
            } else if (!author) {
                author = '[deleted]'; // Hiç yazar bulunamadıysa fallback
            }

            // En güvenilir zaman damgasını al (milisaniye hassasiyetinde)
            let preciseTimestamp;
            const timeAgoEl = shadowRoot.querySelector('rs-timestamp');
            if (timeAgoEl && timeAgoEl.shadowRoot) {
                const faceplateTimeAgo = timeAgoEl.shadowRoot.querySelector('faceplate-timeago[ts]');
                 if (faceplateTimeAgo) {
                    preciseTimestamp = faceplateTimeAgo.getAttribute('ts');
                 }
            }
            if (!preciseTimestamp) {
                // ID için kullanılmayacak, sadece bağlam için bir zaman damgası sağlıyoruz.
                preciseTimestamp = new Date().toISOString(); 
            }

            const contentHash = cyrb53(messageText);
            // STABILITE DÜZELTMESI: ID artık DOM'da hemen bulunamayabilen zaman damgasına
            // bağlı değil. Bu, hem sonsuz döngüleri hem de mesajların atlanmasını önler.
            // ID artık her zaman mevcut olan yazar ve içerik özetine dayanmaktadır.
            const trulyStableId = `${author}_${contentHash}`;
            
            // ID'nin daha önce işlenip işlenmediğini kontrol et
            if (processedIds.has(trulyStableId)) {
                return null; // Zaten işlenmişse atla
            }

            const isOwn = (shadowRoot.querySelector('.flex-row-reverse') !== null);

            return {
                id: trulyStableId,
                text: messageText,
                author: author,
                authorFound: authorFound, // Bu bilgiyi döngüye geri döndür
                timestamp: preciseTimestamp,
                isOwn: isOwn
            };
        } catch (e) {
            console.error("Mesaj parse hatası:", e);
            return null;
        }
    }

    // 4. Tüm mesajları işle ve sonucu dön
    // ------------------------------------------------------------------------------------
    const allMessageElements = virtualScrollRoot.querySelectorAll('rs-timeline-event');
    if (!allMessageElements.length) return [];

    const processedMessages = [];
    let lastValidAuthor = null; // Son "gerçek" yazarı takip et
    for (let i = 0; i < allMessageElements.length; i++) {
        const msgData = getMessageData(allMessageElements[i], i, lastValidAuthor);
        if (msgData) {
            processedMessages.push(msgData);
            // Eğer bu mesajda yeni bir yazar etiketi bulunduysa, bir sonraki isimsiz
            // mesajlar için onu "son geçerli yazar" olarak ayarla.
            if (msgData.authorFound) {
                lastValidAuthor = msgData.author;
            }
        }
    }
    
    return processedMessages;
})(arguments[0] || []);
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

    def _execute_message_reader_script(self, processed_ids=[]):
        """
        Tarayıcıda JavaScript kodunu çalıştırır ve mesaj listesini alır.
        Artık işlenmiş ID'leri de argüman olarak gönderir.
        """
        max_retries = 2
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Set script timeout (WebDriver'ın kendi timeout'unu kullan)
                self.dom_manager.driver.set_script_timeout(10)  # 10 saniye timeout
                
                # Scripti çalıştır ve sonucu al, işlenmiş ID'leri argüman olarak gönder
                messages_from_js = self.dom_manager.driver.execute_script(
                    MESSAGE_READER_JS,
                    processed_ids
                )

                if messages_from_js is None or not isinstance(messages_from_js, list):
                    # print(f"[{time.strftime('%H:%M:%S')}] JS'den mesaj alınamadı veya format yanlış.")
                    if retry_count < max_retries - 1:
                        print(f"[{time.strftime('%H:%M:%S')}] Mesaj okuma başarısız, {retry_count + 1}/{max_retries} deneme...")
                        retry_count += 1
                        time.sleep(1)  # 1 saniye bekle
                        continue
                    return []

                if len(messages_from_js) == 0:
                    # Bu artık beklenen bir durum olabilir (yeni mesaj yoksa)
                    # Bu yüzden log mesajını kaldırdım.
                    pass
                
                return messages_from_js
                
            except JavascriptException as e:
                print(f"[{time.strftime('%H:%M:%S')}] Mesaj okuma script'i JavaScript hatası (deneme {retry_count + 1}/{max_retries}): {e}")
                if retry_count < max_retries - 1:
                    retry_count += 1
                    time.sleep(2)  # JavaScript hatası varsa biraz daha bekle
                    continue
                return []
            except TimeoutException as e:
                print(f"[{time.strftime('%H:%M:%S')}] Mesaj okuma script'i timeout (deneme {retry_count + 1}/{max_retries}): {e}")
                if retry_count < max_retries - 1:
                    retry_count += 1
                    time.sleep(2)
                    continue
                return []
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Mesaj okuma script'i genel hata (deneme {retry_count + 1}/{max_retries}): {e}")
                if retry_count < max_retries - 1:
                    retry_count += 1
                    time.sleep(1)
                    continue
                return []
        
        return []  # Tüm denemeler başarısız

    def get_last_n_messages(self, n=10, initial_scan=False, filter_processed=True):
        """
        Yeni, akıllı JS tabanlı mesaj alma yöntemi.
        JS tarafı artık filtrelemeyi yaptığı için 'n' parametresi bir ipucu olarak kaldı.
        """
        processed_ids_to_filter = []
        if filter_processed:
            # Sadece filtrelenmesi istendiğinde işlenmiş ID'leri kullan
            processed_ids_to_filter = list(self.processed_event_ids)
        
        # JS tarafı filtrelemeyi yapıyor.
        raw_messages_json = self._execute_message_reader_script(processed_ids=processed_ids_to_filter)
        
        if not raw_messages_json:
            return []

        processed_messages = []
        for msg_data in raw_messages_json:
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
        
        # JS kodumuz mesajları artık doğru chronological sırada (eskiden yeniye) veriyor.
        # En son mesaj listede en sonda olacak, bu yüzden ters çevirmeye gerek yok.
        return processed_messages

    def get_last_message_with_user(self):
        """
        En son İŞLENMEMİŞ mesajı ve yazarını alır.
        """
        try:
            # JS tarafı zaten filtreleyeceği için 5 mesaj istemek yeterli
            messages = self.get_last_n_messages(n=5, initial_scan=False, filter_processed=True)
            if messages:
                last_msg = messages[-1] 
                return last_msg['text'], last_msg['user'], last_msg['id'], last_msg['timestamp']
            else:
                # EĞER HİÇ YENİ MESAJ YOKSA BURASI ÇALIŞIR
                return None, None, None, None
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] get_last_message_with_user hatası: {e}")
            traceback.print_exc()
            return None, None, None, None

    def send_message(self, message):
        """
        Çalışan area-button.js kodunu kullanan mesaj gönderme fonksiyonu
        """
        try:
            if not message or not message.strip():
                print(f"[{time.strftime('%H:%M:%S')}] UYARI: Boş mesaj gönderilmeye çalışıldı. Atlanıyor.")
                return True

            print(f"[{time.strftime('%H:%M:%S')}] Mesaj gönderiliyor: '{message[:50]}...'")
            
            # area-button.js'teki çalışan kod
            send_message_script = f"""
            async function sendMessageWithWorkingLogic(messageText) {{
                let foundInput = null;
                
                // Önceki çalışan nested shadow DOM arama fonksiyonu
                function searchInShadowRoot(shadowRoot, depth = 0) {{
                    const indent = "  ".repeat(depth);
                    
                    // Bu shadow root'da textarea ara
                    const textareas = shadowRoot.querySelectorAll('textarea');
                    textareas.forEach(textarea => {{
                        if (textarea.name === 'message' || 
                            (textarea.placeholder && textarea.placeholder.toLowerCase().includes('message')) ||
                            (textarea.getAttribute('aria-label') && textarea.getAttribute('aria-label').toLowerCase().includes('message'))) {{
                            console.log(`${{indent}}🎯 MESAJ ALANI BULUNDU!`);
                            foundInput = textarea;
                        }}
                    }});
                    
                    // Nested shadow root'ları ara
                    const nestedElements = shadowRoot.querySelectorAll('*');
                    nestedElements.forEach(element => {{
                        if (element.shadowRoot) {{
                            searchInShadowRoot(element.shadowRoot, depth + 1);
                        }}
                    }});
                }}
                
                // Ana shadow root'ları ara
                document.querySelectorAll('*').forEach(element => {{
                    if (element.shadowRoot) {{
                        searchInShadowRoot(element.shadowRoot, 0);
                    }}
                }});
                
                if (!foundInput) {{
                    console.log("❌ Mesaj alanı hala bulunamadı!");
                    return false;
                }}
                
                console.log("✅ Mesaj alanı bulundu! Mesaj yazılıyor...");
                
                // Mesajı yaz
                foundInput.focus();
                foundInput.value = messageText;
                
                // Event'leri tetikle
                ['input', 'change', 'keyup', 'keydown'].forEach(eventType => {{
                    const event = new Event(eventType, {{ bubbles: true }});
                    foundInput.dispatchEvent(event);
                }});
                
                console.log("✅ Mesaj yazıldı:", messageText);
                
                // Send butonunu bul (aynı mantıkla)
                return new Promise((resolve) => {{
                    setTimeout(() => {{
                        console.log("📤 Send butonu aranıyor...");
                        
                        let foundSendButton = null;
                        
                        function searchSendButton(shadowRoot, depth = 0) {{
                            const buttons = shadowRoot.querySelectorAll('button');
                            buttons.forEach(button => {{
                                const ariaLabel = button.getAttribute('aria-label') || '';
                                
                                if (ariaLabel.toLowerCase() === 'send message' && !button.disabled) {{
                                    console.log(`🎯 AKTIF SEND BUTONU BULUNDU!`);
                                    foundSendButton = button;
                                }}
                            }});
                            
                            // Nested shadow root'ları ara
                            const nestedElements = shadowRoot.querySelectorAll('*');
                            nestedElements.forEach(element => {{
                                if (element.shadowRoot) {{
                                    searchSendButton(element.shadowRoot, depth + 1);
                                }}
                            }});
                        }}
                        
                        // Ana shadow root'ları ara
                        document.querySelectorAll('*').forEach(element => {{
                            if (element.shadowRoot) {{
                                searchSendButton(element.shadowRoot, 0);
                            }}
                        }});
                        
                        if (foundSendButton) {{
                            console.log("✅ Send butonuna tıklanıyor...");
                            foundSendButton.click();
                            console.log("🎉 MESAJ GÖNDERİLDİ!");
                            resolve(true);
                        }} else {{
                            console.log("❌ Aktif send butonu bulunamadı. Enter tuşu ile deneniyor...");
                            
                            // Enter tuşu
                            const enterEvent = new KeyboardEvent('keydown', {{
                                key: 'Enter',
                                keyCode: 13,
                                which: 13,
                                bubbles: true
                            }});
                            foundInput.dispatchEvent(enterEvent);
                            
                            const enterUpEvent = new KeyboardEvent('keyup', {{
                                key: 'Enter',
                                keyCode: 13,
                                which: 13,
                                bubbles: true
                            }});
                            foundInput.dispatchEvent(enterUpEvent);
                            
                            console.log("⌨️ Enter tuşu gönderildi!");
                            resolve(true);
                        }}
                    }}, 1500);
                }});
            }}
            
            // Mesajı gönder ve sonucu döndür
            return await sendMessageWithWorkingLogic(`{message.replace("`", "\\`").replace("$", "\\$")}`);
            """
            
            # JavaScript'i çalıştır
            result = self.dom_manager.driver.execute_script(send_message_script)
            
            if result:
                print(f"[{time.strftime('%H:%M:%S')}] ✅ Mesaj başarıyla gönderildi!")
                return True
            else:
                print(f"[{time.strftime('%H:%M:%S')}] ❌ Mesaj gönderilemedi!")
                return False
                
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Mesaj gönderme hatası: {e}")
            traceback.print_exc()
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
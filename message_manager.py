# --- START OF FILE message_manager.py ---

import time
import hashlib
import traceback
from datetime import datetime

from config import (
    INITIAL_MESSAGES_TO_READ
)

# Console'da Çalışan Gerçek Reddit Monitor - copy 2'deki çalışan kod + yazar takibi
MESSAGE_READER_JS = """
return (function(processedIdsArray) {
    // ====================================================================================
    //              HYBRID MESSAGE READER (v5.2 - WORKING + STABLE AUTHOR TRACKING)
    // - reddit-sohbot copy 2'deki çalışan JavaScript kodu
    // - RedditDeepSeek'teki stabil yazar takibi mantığı eklendi
    // - Mesaj bulamama sorunu çözüldü
    // ====================================================================================

    const processedIds = new Set(processedIdsArray || []);

    // 1. Shadow DOM elementlerini güvenilir bir şekilde bul (COPY 2'DEN)
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
    
    // 2. Güvenilir ve Kriptografik ID Üretim Fonksiyonu (COPY 2'DEN)
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

    // 3. Her mesaj elementi için veri çıkarma fonksiyonu (COPY 2 + AUTHOR TRACKING)
    // ------------------------------------------------------------------------------------
    function getMessageData(msgElement, index, lastKnownAuthor) {
        try {
            if (!msgElement || !msgElement.shadowRoot) return null;
            const shadowRoot = msgElement.shadowRoot;

            // Mesaj metni (COPY 2'DEKİ DOĞRU SELECTOR!)
            const messageText = shadowRoot.querySelector('div.room-message-text.truncated')?.textContent.trim() || '';
            if (!messageText) return null;

            // Yazar (COPY 2'DEKİ SIRALAMA + AUTHOR TRACKING)
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
                        if (authorText) {
                            author = authorText;
                            authorFound = true;
                            break;
                        }
                    }
                }
            } catch (e) { /* Yazar bulunamazsa null kalır */ }
            
            // AUTHOR TRACKING MANTIGI: Eğer bu mesaj elementinde yeni bir yazar bulunamadıysa, son bilinen yazarı kullan.
            if (!authorFound && lastKnownAuthor) {
                author = lastKnownAuthor;
            } else if (!author) {
                author = '[deleted]'; // Hiç yazar bulunamadıysa fallback
            }

            // Zaman damgası (COPY 2'DEN)
            let timestamp = new Date().toLocaleTimeString('tr-TR');
            try {
                const timeElement = shadowRoot.querySelector('rs-timestamp time-stamp > span');
                if (timeElement) {
                    timestamp = timeElement.textContent.trim();
                }
            } catch (e) {}

            // ID oluştur - SADECE MESAJ İÇERİĞİNE DAYALI (author bağımsız - sonsuz döngü önlenir)
            const contentHash = cyrb53(messageText);
            const messageBasedId = `msg_${contentHash}_${messageText.substring(0, 10)}`;
            
            // ID'nin daha önce işlenip işlenmediğini kontrol et
            if (processedIds.has(messageBasedId)) {
                return null; // Zaten işlenmişse atla
            }

            const isOwn = (shadowRoot.querySelector('.flex-row-reverse') !== null);

            return {
                id: messageBasedId,
                text: messageText,
                user: author, // Python'da 'user' field'ini arayacak
                author: author, // Backward compatibility için
                authorFound: authorFound, // Bu bilgiyi döngüye geri döndür
                timestamp: timestamp,
                isOwn: isOwn
            };
        } catch (e) {
            console.error("Mesaj parse hatası:", e);
            return null;
        }
    }

    // 4. Tüm mesajları işle ve sonucu dön (COPY 2 + AUTHOR TRACKING)
    // ------------------------------------------------------------------------------------
    const allMessageElements = virtualScrollRoot.querySelectorAll('rs-timeline-event');
    if (!allMessageElements.length) return [];

    const processedMessages = [];
    let lastValidAuthor = null; // Son "gerçek" yazarı takip et
    console.log(`[JS] Processing ${allMessageElements.length} message elements...`);
    
    for (let i = 0; i < allMessageElements.length; i++) {
        const msgData = getMessageData(allMessageElements[i], i, lastValidAuthor);
        if (msgData) {
            console.log(`[JS] Message ${i}: "${msgData.text.substring(0, 30)}..." -> User: ${msgData.user} (Found: ${msgData.authorFound}, LastValid: ${lastValidAuthor})`);
            processedMessages.push(msgData);
            // Eğer bu mesajda yeni bir yazar etiketi bulunduysa, bir sonraki isimsiz
            // mesajlar için onu "son geçerli yazar" olarak ayarla.
            if (msgData.authorFound) {
                lastValidAuthor = msgData.author;
                console.log(`[JS] Updated lastValidAuthor to: ${lastValidAuthor}`);
            }
        }
    }
    
    console.log(`[JS] Returning ${processedMessages.length} processed messages`);
    return processedMessages;
})(arguments[0] || []);
"""

class MessageManager:
    def __init__(self, dom_manager, context_manager_instance, bot_username):
        self.dom_manager = dom_manager
        self.context_manager = context_manager_instance
        self.bot_username_lower = bot_username.lower()
        self.bot_actual_username = bot_username
        self.last_seen_message_content = ""
        self.last_seen_message_user = ""
        self.processed_event_ids = set()

    def get_last_n_messages(self, n=INITIAL_MESSAGES_TO_READ, initial_scan=False):
        """
        JavaScript injection kullanarak en son n mesajı alır.
        RedditDeepSeek'teki stable author tracking mantığı uygulandı.
        """
        try:
            if initial_scan:
                print(f"[{time.strftime('%H:%M:%S')}] Başlangıç bağlamı toplanıyor (yeni akıllı yöntemle)...")

            # İşlenmiş ID'leri listeye çevir (JavaScript'e gönderebilmek için)
            processed_ids_to_filter = list(self.processed_event_ids)

            # JavaScript kodumuz mesajları okuyacak
            messages_from_js = self.dom_manager.driver.execute_script(MESSAGE_READER_JS, processed_ids_to_filter)

            # Sonuçları işle
            messages_data = []
            if messages_from_js:
                for msg_data in messages_from_js:
                    messages_data.append({
                        'id': msg_data.get('id'),
                        'text': msg_data.get('text', ''),
                        'user': msg_data.get('user', 'BilinmeyenKullanici'),
                        'timestamp': msg_data.get('timestamp', str(int(time.time())))
                    })

            if initial_scan:
                if messages_data:
                    print(f"[{time.strftime('%H:%M:%S')}] Başlangıç taramasında {len(messages_data)} mesaj bulundu.")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Başlangıç taramasında hiç mesaj bulunamadı.")

            return messages_data

        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] get_last_n_messages içinde genel hata: {e}")
            traceback.print_exc()
            return []

    def get_last_message_with_user(self):
        """
        En son İŞLENMEMİŞ mesajı ve yazarını alır.
        """
        try:
            messages = self.get_last_n_messages(n=10, initial_scan=False)
            if messages:
                # İşlenmemiş mesajları filtrele
                unprocessed_messages = [msg for msg in messages if msg['id'] not in self.processed_event_ids]
                if unprocessed_messages:
                    last_msg = unprocessed_messages[-1]  # En son işlenmemiş mesaj
                    return last_msg['text'], last_msg['user'], last_msg['id'], last_msg['timestamp']
            return None, None, None, None
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] get_last_message_with_user hatası: {e}")
            traceback.print_exc()
            return None, None, None, None
            
    def send_message(self, message):
        """
        Mesaj gönderme fonksiyonu - Artık area-button.js'deki çalışan mantığı kullanıyor
        """
        try:
            if not message or not message.strip():
                print(f"[{time.strftime('%H:%M:%S')}] UYARI: Boş mesaj gönderilmeye çalışıldı. Atlanıyor.")
                return True

            print(f"[{time.strftime('%H:%M:%S')}] Mesaj gönderiliyor: '{message[:50]}...'")
            
            send_message_script = f"""
            async function sendMessageWithWorkingLogic(messageText) {{
                let foundInput = null;
                
                function searchInShadowRoot(shadowRoot) {{
                    const textareas = shadowRoot.querySelectorAll('textarea');
                    textareas.forEach(textarea => {{
                        if (textarea.name === 'message' || 
                            (textarea.placeholder && textarea.placeholder.toLowerCase().includes('message')) ||
                            (textarea.getAttribute('aria-label') && textarea.getAttribute('aria-label').toLowerCase().includes('message'))) {{
                            foundInput = textarea;
                        }}
                    }});
                    if (foundInput) return;

                    const nestedElements = shadowRoot.querySelectorAll('*');
                    nestedElements.forEach(element => {{
                        if (element.shadowRoot) {{
                            searchInShadowRoot(element.shadowRoot);
                        }}
                    }});
                }}
                
                document.querySelectorAll('*').forEach(element => {{
                    if (element.shadowRoot) {{
                        searchInShadowRoot(element.shadowRoot);
                    }}
                }});
                
                if (!foundInput) {{
                    console.error("❌ Mesaj gönderme alanı bulunamadı!");
                    return false;
                }}
                
                foundInput.focus();
                foundInput.value = messageText;
                
                ['input', 'change', 'keyup', 'keydown'].forEach(eventType => {{
                    const event = new Event(eventType, {{ bubbles: true }});
                    foundInput.dispatchEvent(event);
                }});
                
                return new Promise((resolve) => {{
                    setTimeout(() => {{
                        let foundSendButton = null;
                        
                        function searchSendButton(shadowRoot) {{
                            const buttons = shadowRoot.querySelectorAll('button[aria-label*="Send"]');
                            buttons.forEach(button => {{
                                if (!button.disabled) {{
                                    foundSendButton = button;
                                }}
                            }});
                             if (foundSendButton) return;

                            const nestedElements = shadowRoot.querySelectorAll('*');
                            nestedElements.forEach(element => {{
                                if (element.shadowRoot) {{
                                    searchSendButton(element.shadowRoot);
                                }}
                            }});
                        }}
                        
                        document.querySelectorAll('*').forEach(element => {{
                            if (element.shadowRoot) {{
                                searchSendButton(element.shadowRoot, 0);
                            }}
                        }});
                        
                        if (foundSendButton) {{
                            foundSendButton.click();
                            resolve(true);
                        }} else {{
                            console.warn("❌ Aktif send butonu bulunamadı. Enter tuşu ile deneniyor...");
                            const enterEvent = new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13, bubbles: true }});
                            foundInput.dispatchEvent(enterEvent);
                            resolve(true);
                        }}
                    }}, 500);
                }});
            }}
            
            return await sendMessageWithWorkingLogic(`{message.replace("`", "\\`").replace("$", "\\$")}`);
            """
            
            result = self.dom_manager.driver.execute_script(send_message_script)
            
            if result:
                print(f"[{time.strftime('%H:%M:%S')}] ✅ Mesaj başarıyla gönderildi!")
                return True
            else:
                print(f"[{time.strftime('%H:%M:%S')}] ❌ Mesaj gönderilemedi (JS script'i false döndü).")
                return False
                
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Mesaj gönderme hatası: {e}")
            traceback.print_exc()
            return False

    def handle_message_for_context(self, message_content, username_original_case, msg_id, timestamp_str, initial_scan_complete_time, is_already_marked_processed_in_loop=False):
        """
        Bu fonksiyonda değişiklik yok. Gelen veriyi işleme mantığı aynı.
        """
        if username_original_case.lower() == self.bot_username_lower:
            if msg_id and not is_already_marked_processed_in_loop and msg_id not in self.processed_event_ids:
                self.processed_event_ids.add(msg_id)
            return None

        is_ai_command = message_content.startswith("/ai ")
        should_add_to_context = False
        if msg_id:
            # Bu ID daha önce işlenmemişse bağlama ekle
            if msg_id not in self.processed_event_ids:
                should_add_to_context = True
        
        if should_add_to_context:
            self.context_manager.add_user_message(username_original_case, message_content, timestamp_str)
            # Bağlama ekledikten sonra ID'yi işlenmiş olarak işaretle
            if msg_id:
                self.processed_event_ids.add(msg_id)
            if is_ai_command and (initial_scan_complete_time is None):
                 print(f"[{time.strftime('%H:%M:%S')}] BAŞLANGIÇ /ai: '{message_content[:30]}...' (K: {username_original_case}) bağlama eklendi, yanıtlanmayacak.")

        if is_ai_command:
            should_respond_to_ai_command = False
            # Başlangıç taraması bittiyse ve bu mesaj yeni bir mesajsa yanıtla
            if initial_scan_complete_time is not None:
                # `should_add_to_context` zaten bu mesajın yeni olduğunu teyit etti.
                if should_add_to_context:
                     should_respond_to_ai_command = True

            if should_respond_to_ai_command:
                user_prompt = message_content[len("/ai "):].strip()
                print(f"[{time.strftime('%H:%M:%S')}] YENİ /ai komutu '{user_prompt[:30]}...' (K: {username_original_case}) işleniyor...")
                context_string = self.context_manager.get_context_string()
                full_prompt = context_string + f"KULLANICI '{username_original_case}' şunu soruyor: {user_prompt}"
                return full_prompt
        return None
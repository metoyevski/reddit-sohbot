# --- START OF FILE dom_manager.py ---

import time
import traceback
from selenium.common.exceptions import TimeoutException, JavascriptException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import (
    ELEMENT_WAIT_TIMEOUT, DOM_REINITIALIZE_WAIT
)

# Gelişmiş mesaj giriş alanı arama scripti - birden fazla strateji kullanır
ADVANCED_INPUT_FINDER_JS = """
    function findMessageInput() {
        console.log('[DOM] Mesaj giriş alanı aranıyor...');
        
        // Strateji 1: Klasik rs-message-composer ile shadow DOM arama
        try {
            const composer = document.querySelector('rs-message-composer');
            if (composer && composer.shadowRoot) {
                const textarea = composer.shadowRoot.querySelector('textarea[aria-label*="message"], textarea[aria-label*="Message"], textarea[placeholder*="message"], textarea[placeholder*="Message"]');
                if (textarea) {
                    console.log('[DOM] Strateji 1 başarılı: rs-message-composer shadow DOM');
                    return textarea;
                }
            }
        } catch(e) { console.log('[DOM] Strateji 1 hatası:', e); }
        
        // Strateji 2: Tüm shadow DOM'ları tara
        try {
            const allElements = document.querySelectorAll('*');
            for (const el of allElements) {
                if (el.shadowRoot) {
                    const textarea = el.shadowRoot.querySelector('textarea[aria-label*="message"], textarea[aria-label*="Message"], textarea[placeholder*="message"], textarea[placeholder*="Message"]');
                    if (textarea) {
                        console.log('[DOM] Strateji 2 başarılı: Shadow DOM tarama');
                        return textarea;
                    }
                }
            }
        } catch(e) { console.log('[DOM] Strateji 2 hatası:', e); }
        
        // Strateji 3: Reddit'in yeni arayüzü için doğrudan textarea arama
        try {
            const selectors = [
                'textarea[data-testid*="message"]',
                'textarea[aria-label*="Type a message"]',
                'textarea[aria-label*="Write message"]',
                'textarea[placeholder*="Type a message"]',
                'textarea[placeholder*="Write message"]',
                'textarea[data-testid="chat-input"]',
                'textarea[class*="message"]',
                'textarea[class*="chat"]',
                'textarea[class*="input"]',
                '.chat-input textarea',
                '.message-input textarea',
                '[data-testid*="chat"] textarea',
                '[data-testid*="message"] textarea'
            ];
            
            for (const selector of selectors) {
                const textarea = document.querySelector(selector);
                if (textarea && textarea.offsetParent !== null) {
                    console.log('[DOM] Strateji 3 başarılı:', selector);
                    return textarea;
                }
            }
        } catch(e) { console.log('[DOM] Strateji 3 hatası:', e); }
        
        // Strateji 4: Iframe içinde arama
        try {
            const iframes = document.querySelectorAll('iframe');
            for (const iframe of iframes) {
                try {
                    const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                    const textarea = iframeDoc.querySelector('textarea');
                    if (textarea) {
                        console.log('[DOM] Strateji 4 başarılı: iframe içinde');
                        return textarea;
                    }
                } catch(e) { /* Cross-origin iframe, ignore */ }
            }
        } catch(e) { console.log('[DOM] Strateji 4 hatası:', e); }
        
        // Strateji 5: Tüm textarea'ları kontrol et (en son çare)
        try {
            const textareas = document.querySelectorAll('textarea');
            for (const textarea of textareas) {
                if (textarea.offsetParent !== null && 
                    (textarea.getAttribute('aria-label') || 
                     textarea.getAttribute('placeholder') || 
                     textarea.className || 
                     textarea.getAttribute('data-testid'))) {
                    console.log('[DOM] Strateji 5 başarılı: genel textarea');
                    return textarea;
                }
            }
        } catch(e) { console.log('[DOM] Strateji 5 hatası:', e); }
        
        console.log('[DOM] Hiçbir strateji başarılı olmadı');
        return null;
    }
    
    return findMessageInput();
"""

# Sayfa bilgilerini toplayan script
PAGE_INFO_SCRIPT = """
    return {
        url: window.location.href,
        title: document.title,
        readyState: document.readyState,
        hasChat: !!document.querySelector('[class*="chat"], [data-testid*="chat"], rs-message-composer'),
        textareaCount: document.querySelectorAll('textarea').length,
        shadowRootCount: Array.from(document.querySelectorAll('*')).filter(el => el.shadowRoot).length
    };
"""

class ChatDOMManager:
    """
    Geliştirilmiş DOM Manager - Reddit'in farklı arayüz versiyonlarına uyum sağlar
    """
    def __init__(self, driver):
        self.driver = driver
        self.dom_elements = {}
        self.last_successful_check = 0
        self.successful_strategy = None

    def get_page_info(self):
        """Sayfa hakkında debug bilgisi toplar"""
        try:
            return self.driver.execute_script(PAGE_INFO_SCRIPT)
        except Exception as e:
            return {"error": str(e)}

    def reinitialize_dom_elements(self):
        """
        MONITOR TEST MODU: Sadece mesaj okuma için, input arama devre dışı
        """
        try:
            print(f"[{time.strftime('%H:%M:%S')}] MONITOR TEST MODU: Input arama atlanıyor, sadece mesaj okuma...")
            
            # Sayfa bilgilerini al
            page_info = self.get_page_info()
            print(f"[{time.strftime('%H:%M:%S')}] Sayfa bilgileri: {page_info}")
            
            # Reddit chat sayfasında olup olmadığını kontrol et
            if not page_info.get('hasChat', False) and 'chat.reddit.com' not in page_info.get('url', ''):
                print(f"[{time.strftime('%H:%M:%S')}] UYARI: Bu sayfa Reddit chat sayfası gibi görünmüyor!")
                print(f"[{time.strftime('%H:%M:%S')}] URL: {page_info.get('url', 'Bilinmiyor')}")
            
            # Monitor test modu: INPUT arama atla, sadece mesaj okumaya odaklan
            print(f"[{time.strftime('%H:%M:%S')}] ✅ MONITOR TEST MODU aktif - Input alanı aramıyor!")
            
            # Boş dict - mesaj gönderme olmayacak, sadece okuma
            self.dom_elements = {}
            self.last_successful_check = time.time()
            
            return True  # Her zaman başarılı, çünkü input aramıyoruz
            
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Monitor test modu hatası: {e}")
            return True  # Hata olsa bile devam et

    def is_dom_healthy(self):
        """
        Mesaj giriş alanının sağlığını kontrol eder
        Read-only modda (mesaj gönderme olmadığında) her zaman True döner
        """
        try:
            input_area = self.dom_elements.get('message_input_area')
            if not input_area:
                # Read-only mod: mesaj gönderme alanı yok ama bu normal
                return True  # Mesaj okuma çalışabilir
            
            # Element hala DOM'da bağlı mı?
            is_connected = self.driver.execute_script(
                'return arguments[0] && arguments[0].isConnected', 
                input_area
            )
            
            if not is_connected:
                print(f"[{time.strftime('%H:%M:%S')}] DOM health check: Element DOM'dan kopmuş.")
                return False
            
            # Element görünür mü?
            is_visible = self.driver.execute_script("""
                const el = arguments[0];
                return el && el.offsetParent !== null && 
                       getComputedStyle(el).visibility !== 'hidden' &&
                       getComputedStyle(el).display !== 'none';
            """, input_area)
            
            if not is_visible:
                print(f"[{time.strftime('%H:%M:%S')}] DOM health check: Element görünür değil.")
                return False
            
            return True
            
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] DOM health check hatası: {e}")
            return True  # Read-only modda hata olsa bile devam et

    def debug_current_page(self):
        """Debug amaçlı sayfa durumunu yazdırır"""
        try:
            info = self.get_page_info()
            print(f"[{time.strftime('%H:%M:%S')}] === SAYFA DEBUG BİLGİLERİ ===")
            print(f"[{time.strftime('%H:%M:%S')}] URL: {info.get('url', 'N/A')}")
            print(f"[{time.strftime('%H:%M:%S')}] Başlık: {info.get('title', 'N/A')}")
            print(f"[{time.strftime('%H:%M:%S')}] Ready State: {info.get('readyState', 'N/A')}")
            print(f"[{time.strftime('%H:%M:%S')}] Chat elementi var mı: {info.get('hasChat', False)}")
            print(f"[{time.strftime('%H:%M:%S')}] Textarea sayısı: {info.get('textareaCount', 0)}")
            print(f"[{time.strftime('%H:%M:%S')}] Shadow DOM sayısı: {info.get('shadowRootCount', 0)}")
            print(f"[{time.strftime('%H:%M:%S')}] ================================")
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Debug bilgisi alınamadı: {e}")
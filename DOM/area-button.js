// Önceki Çalışan Kodla Mesaj Alanı Bulma ve Gönderme
console.log("=== ÖNCEKİ ÇALIŞAN MANTIKLA MESAJ GÖNDERME ===");

async function sendMessageWithWorkingLogic() {
    let foundInput = null;
    
    // Önceki çalışan nested shadow DOM arama fonksiyonu
    function searchInShadowRoot(shadowRoot, depth = 0) {
        const indent = "  ".repeat(depth);
        
        // Bu shadow root'da textarea ara
        const textareas = shadowRoot.querySelectorAll('textarea');
        textareas.forEach(textarea => {
            if (textarea.name === 'message' || 
                (textarea.placeholder && textarea.placeholder.toLowerCase().includes('message')) ||
                (textarea.getAttribute('aria-label') && textarea.getAttribute('aria-label').toLowerCase().includes('message'))) {
                console.log(`${indent}🎯 MESAJ ALANI BULUNDU!`);
                foundInput = textarea;
            }
        });
        
        // Nested shadow root'ları ara
        const nestedElements = shadowRoot.querySelectorAll('*');
        nestedElements.forEach(element => {
            if (element.shadowRoot) {
                searchInShadowRoot(element.shadowRoot, depth + 1);
            }
        });
    }
    
    // Ana shadow root'ları ara
    document.querySelectorAll('*').forEach(element => {
        if (element.shadowRoot) {
            searchInShadowRoot(element.shadowRoot, 0);
        }
    });
    
    if (!foundInput) {
        console.log("❌ Mesaj alanı hala bulunamadı!");
        return false;
    }
    
    console.log("✅ Mesaj alanı bulundu! Mesaj yazılıyor...");
    
    // Mesajı yaz
    const testMessage = "🤖 Çalışan kodla gönderilen test mesajı!";
    
    foundInput.focus();
    foundInput.value = testMessage;
    
    // Event'leri tetikle
    ['input', 'change', 'keyup', 'keydown'].forEach(eventType => {
        const event = new Event(eventType, { bubbles: true });
        foundInput.dispatchEvent(event);
    });
    
    console.log("✅ Mesaj yazıldı:", testMessage);
    
    // Send butonunu bul (aynı mantıkla)
    return new Promise((resolve) => {
        setTimeout(() => {
            console.log("📤 Send butonu aranıyor...");
            
            let foundSendButton = null;
            
            function searchSendButton(shadowRoot, depth = 0) {
                const buttons = shadowRoot.querySelectorAll('button');
                buttons.forEach(button => {
                    const ariaLabel = button.getAttribute('aria-label') || '';
                    
                    if (ariaLabel.toLowerCase() === 'send message' && !button.disabled) {
                        console.log(`🎯 AKTIF SEND BUTONU BULUNDU!`);
                        foundSendButton = button;
                    }
                });
                
                // Nested shadow root'ları ara
                const nestedElements = shadowRoot.querySelectorAll('*');
                nestedElements.forEach(element => {
                    if (element.shadowRoot) {
                        searchSendButton(element.shadowRoot, depth + 1);
                    }
                });
            }
            
            // Ana shadow root'ları ara
            document.querySelectorAll('*').forEach(element => {
                if (element.shadowRoot) {
                    searchSendButton(element.shadowRoot, 0);
                }
            });
            
            if (foundSendButton) {
                console.log("✅ Send butonuna tıklanıyor...");
                foundSendButton.click();
                console.log("🎉 MESAJ GÖNDERİLDİ!");
                resolve(true);
            } else {
                console.log("❌ Aktif send butonu bulunamadı. Enter tuşu ile deneniyor...");
                
                // Enter tuşu
                const enterEvent = new KeyboardEvent('keydown', {
                    key: 'Enter',
                    keyCode: 13,
                    which: 13,
                    bubbles: true
                });
                foundInput.dispatchEvent(enterEvent);
                
                const enterUpEvent = new KeyboardEvent('keyup', {
                    key: 'Enter',
                    keyCode: 13,
                    which: 13,
                    bubbles: true
                });
                foundInput.dispatchEvent(enterUpEvent);
                
                console.log("⌨️ Enter tuşu gönderildi!");
                resolve(true);
            }
        }, 1500); // Biraz daha uzun bekle
    });
}

// Test et
sendMessageWithWorkingLogic().then(success => {
    if (success) {
        console.log("🎊 Başarıyla tamamlandı!");
    } else {
        console.log("❌ Test başarısız!");
    }
});
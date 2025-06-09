// Refresh-Free Reddit Chat Real-Time Monitor
// Console'a yapıştır ve test et

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
        this.setupRealTimeMonitoring();
        this.injectContentLoader();
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
    
    // REAL-TIME MONİTORİNG KURULUMU
    setupRealTimeMonitoring() {
        this.log("⚡ Real-time monitoring kuruluyor...");
        
        // 1. Ana mesaj kontrol döngüsü
        const mainCheck = setInterval(() => {
            this.checkForNewMessages();
        }, this.config.checkInterval);
        this.intervals.push(mainCheck);
        
        // 2. Force content load
        const forceLoad = setInterval(() => {
            this.forceContentLoad();
        }, this.config.forceLoadInterval);
        this.intervals.push(forceLoad);
        
        // 3. Scroll trigger
        const scrollTrigger = setInterval(() => {
            this.triggerScrollLoad();
        }, this.config.scrollTriggerInterval);
        this.intervals.push(scrollTrigger);
        
        // 4. MutationObserver for DOM changes
        this.setupMutationObserver();
        
        this.log("✅ Real-time intervals kuruldu");
    }
    
    // CONTENT LOADER INJECTION
    injectContentLoader() {
        this.log("💉 Content loader inject ediliyor...");
        
        // Sayfa aktivitesi simülasyonu
        this.simulateUserActivity();
        
        // Event listener'lar
        this.setupEventListeners();
        
        this.log("✅ Content loader aktif");
    }
    
    // KULLANICI AKTİVİTESİ SİMÜLASYONU
    simulateUserActivity() {
        // Periyodik olarak sayfaya "canlı" olduğumuz sinyali ver
        setInterval(() => {
            // Mouse move simülasyonu
            document.dispatchEvent(new MouseEvent('mousemove', {
                clientX: Math.random() * 100,
                clientY: Math.random() * 100
            }));
            
            // Visibility API ile sayfa aktif sinyali
            if (document.hidden) {
                document.dispatchEvent(new Event('visibilitychange'));
            }
        }, 30000); // 30 saniyede bir
    }
    
    // EVENT LİSTENER'LAR
    setupEventListeners() {
        // Input focus/blur
        const messageInput = this.getMessageInput();
        if (messageInput) {
            ['focus', 'blur', 'click'].forEach(event => {
                messageInput.addEventListener(event, () => {
                    setTimeout(() => this.checkForNewMessages(), 500);
                });
            });
        }
        
        // Scroll events
        window.addEventListener('scroll', () => {
            setTimeout(() => this.checkForNewMessages(), 1000);
        });
    }
    
    // MUTATION OBSERVER
    setupMutationObserver() {
        if (!this.shadowElements.virtualScroll) return;
        
        const observer = new MutationObserver((mutations) => {
            let hasNewContent = false;
            
            mutations.forEach(mutation => {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    mutation.addedNodes.forEach(node => {
                        if (node.nodeType === 1 && node.tagName === 'RS-TIMELINE-EVENT') {
                            hasNewContent = true;
                        }
                    });
                }
            });
            
            if (hasNewContent) {
                this.log("👀 MutationObserver: Yeni content algılandı");
                setTimeout(() => this.checkForNewMessages(), 500);
            }
        });
        
        observer.observe(this.shadowElements.virtualScroll, {
            childList: true,
            subtree: true
        });
        
        this.log("👁️ MutationObserver aktif");
    }
    
    // YENİ MESAJ KONTROLÜ
    checkForNewMessages() {
        if (!this.isActive) return;
        
        try {
            const currentMessages = this.getMessagesFromDOM();
            
            if (currentMessages.length !== this.lastMessageCount) {
                this.log(`📊 Mesaj sayısı değişti: ${this.lastMessageCount} → ${currentMessages.length}`);
                this.handleNewMessages(currentMessages);
                this.consecutiveNoChange = 0;
            } else {
                // Mesaj içeriği değişti mi kontrol et
                const contentChanged = this.hasContentChanged(currentMessages);
                if (contentChanged) {
                    this.log("📝 Mesaj içeriği değişti");
                    this.handleNewMessages(currentMessages);
                    this.consecutiveNoChange = 0;
                } else {
                    this.consecutiveNoChange++;
                }
            }
            
            // Çok uzun süre değişiklik yoksa action al
            if (this.consecutiveNoChange >= this.config.maxConsecutiveNoChange) {
                this.log("⚠️ Uzun süre değişiklik yok, force loading...");
                this.forceContentLoad();
                this.consecutiveNoChange = 0;
            }
            
            this.lastMessageCount = currentMessages.length;
            this.lastMessages = currentMessages;
            
        } catch (e) {
            this.log(`❌ Mesaj kontrol hatası: ${e.message}`);
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
            
            timelineEvents.forEach((event, index) => {
                const messageData = this.extractMessageData(event, index);
                if (messageData) {
                    messages.push(messageData);
                }
            });
            
            return messages;
        } catch (e) {
            this.log(`❌ DOM mesaj alma hatası: ${e.message}`);
            return [];
        }
    }
    
    // MESAJ VERİSİNİ ÇIKAR
    extractMessageData(eventElement, index) {
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
            
            // Yazar
            let author = 'Bilinmeyen';
            try {
                const authorSelectors = [
                    'faceplate-tracker[noun="user_hovers"] > span[slot="trigger"]',
                    '.room-message-author',
                    'span.user-name'
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
                        if (authorText) {
                            author = authorText;
                            break;
                        }
                    }
                }
            } catch (e) {}
            
            // Timestamp
            let timestamp = new Date().toLocaleTimeString('tr-TR');
            try {
                const timeElement = shadowRoot.querySelector('rs-timestamp time-stamp > span');
                if (timeElement) {
                    timestamp = timeElement.textContent.trim();
                }
            } catch (e) {}
            
            // ID oluştur
            const id = `${messageText.substring(0, 50)}_${timestamp}_${index}`;
            
            if (!messageText && !author) return null;
            
            return {
                id: id,
                text: messageText,
                author: author,
                timestamp: timestamp,
                element: eventElement
            };
            
        } catch (e) {
            return null;
        }
    }
    
    // İÇERİK DEĞİŞİKLİĞİ KONTROLÜ
    hasContentChanged(currentMessages) {
        if (currentMessages.length !== this.lastMessages.length) return true;
        
        for (let i = 0; i < currentMessages.length; i++) {
            const current = currentMessages[i];
            const last = this.lastMessages[i];
            
            if (!last || current.text !== last.text || current.author !== last.author) {
                return true;
            }
        }
        
        return false;
    }
    
    // YENİ MESAJLARI İŞLE
    handleNewMessages(messages) {
        const newMessages = messages.filter(msg => 
            !this.processedMessageIds.has(msg.id)
        );
        
        if (newMessages.length > 0) {
            this.log(`🆕 ${newMessages.length} yeni mesaj algılandı`);
            
            newMessages.forEach(msg => {
                this.processedMessageIds.add(msg.id);
                this.stats.messagesFound++;
                
                // /ai komutu kontrolü
                if (msg.text.toLowerCase().startsWith('/ai ')) {
                    this.stats.aiCommandsDetected++;
                    this.log(`🤖 /ai komutu algılandı: ${msg.author} - "${msg.text.substring(0, 50)}..."`);
                    this.handleAICommand(msg);
                }
                
                // Callback'leri çağır
                this.callbacks.forEach(callback => {
                    try {
                        callback(msg);
                    } catch (e) {
                        this.log(`❌ Callback hatası: ${e.message}`);
                    }
                });
            });
            
            // Event gönder
            const event = new CustomEvent('redditNewMessages', {
                detail: { messages: newMessages }
            });
            document.dispatchEvent(event);
            
            this.stats.newMessagesCaught += newMessages.length;
        }
    }
    
    // /AI KOMUTU İŞLEME
    handleAICommand(message) {
        const command = message.text.substring(4).trim(); // "/ai " kısmını çıkar
        
        console.log(`\n🤖 AI KOMUTU ALGıLANDı:`);
        console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
        console.log(`👤 Kullanıcı: ${message.author}`);
        console.log(`⏰ Zaman: ${message.timestamp}`);
        console.log(`💬 Komut: "${command}"`);
        console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`);
        
        // Custom event for AI commands
        const aiEvent = new CustomEvent('redditAICommand', {
            detail: { 
                message: message,
                command: command
            }
        });
        document.dispatchEvent(aiEvent);
    }
    
    // FORCE CONTENT LOADING
    forceContentLoad() {
        this.log("💪 Force content loading...");
        this.stats.forceLoadAttempts++;
        
        try {
            // Method 1: Input focus trigger
            this.triggerInputFocus();
            
            // Method 2: Scroll trigger
            setTimeout(() => {
                this.triggerScrollLoad();
            }, 1000);
            
            // Method 3: Container interaction
            setTimeout(() => {
                this.triggerContainerInteraction();
            }, 2000);
            
        } catch (e) {
            this.log(`❌ Force load hatası: ${e.message}`);
        }
    }
    
    // INPUT FOCUS TETİKLEME
    triggerInputFocus() {
        const messageInput = this.getMessageInput();
        if (messageInput) {
            messageInput.focus();
            setTimeout(() => messageInput.blur(), 100);
            setTimeout(() => messageInput.focus(), 200);
        }
    }
    
    // SCROLL TETİKLEME
    triggerScrollLoad() {
        try {
            if (this.shadowElements.virtualScroll) {
                const container = this.shadowElements.virtualScroll.querySelector('#container');
                if (container) {
                    const currentScroll = container.scrollTop;
                    
                    // Yukarı scroll
                    container.scrollTop = Math.max(0, currentScroll - 100);
                    
                    setTimeout(() => {
                        // Aşağı scroll (geri)
                        container.scrollTop = currentScroll + 50;
                    }, 500);
                }
            }
        } catch (e) {
            this.log(`❌ Scroll trigger hatası: ${e.message}`);
        }
    }
    
    // CONTAINER ETKİLEŞİM TETİKLEME
    triggerContainerInteraction() {
        try {
            if (this.shadowElements.virtualScroll) {
                const container = this.shadowElements.virtualScroll.querySelector('#container');
                if (container) {
                    // Mouse events
                    ['mouseover', 'mouseout', 'click'].forEach(eventType => {
                        const event = new MouseEvent(eventType, { bubbles: true });
                        container.dispatchEvent(event);
                    });
                }
            }
        } catch (e) {
            this.log(`❌ Container interaction hatası: ${e.message}`);
        }
    }
    
    // MESAJ INPUT ELEMENTI AL
    getMessageInput() {
        if (this.shadowElements.rsComposer) {
            return this.shadowElements.rsComposer.querySelector('textarea[aria-label="Write message"]');
        }
        return null;
    }
    
    // CALLBACK EKLEME
    onNewMessage(callback) {
        this.callbacks.push(callback);
        this.log("✅ Yeni mesaj callback'i eklendi");
    }
    
    // MANUEL KONTROLLER
    forceCheck() {
        this.log("🔍 Manuel kontrol tetiklendi");
        this.checkForNewMessages();
    }
    
    forceLoad() {
        this.log("💪 Manuel force load tetiklendi");
        this.forceContentLoad();
    }
    
    // EN SON MESAJLARI AL
    getLatestMessages(count = 10) {
        const messages = this.getMessagesFromDOM();
        return messages.slice(-count);
    }
    
    // /AI KOMUTLARINI AL
    getAICommands() {
        const messages = this.getMessagesFromDOM();
        return messages.filter(msg => msg.text.toLowerCase().startsWith('/ai '));
    }
    
    // İSTATİSTİKLER
    getStats() {
        return {
            ...this.stats,
            uptime: Date.now() - this.startTime,
            consecutiveNoChange: this.consecutiveNoChange,
            processedMessages: this.processedMessageIds.size,
            isActive: this.isActive
        };
    }
    
    displayStats() {
        const stats = this.getStats();
        console.log(`
📊 REFRESH-FREE MONITOR STATİSTİKLERİ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 Aktivite:
   Bulunan Mesajlar: ${stats.messagesFound}
   Yakalanan Yeni Mesajlar: ${stats.newMessagesCaught}
   AI Komutları: ${stats.aiCommandsDetected}
   Force Load Denemeleri: ${stats.forceLoadAttempts}
   İşlenen Mesajlar: ${stats.processedMessages}

⚡ Durum:
   Aktif: ${stats.isActive ? '✅' : '❌'}
   Ardışık Değişiklik Yok: ${stats.consecutiveNoChange}
   Çalışma Süresi: ${(stats.uptime / 1000 / 60).toFixed(1)} dakika
        `);
    }
    
    // DURDURMA
    stop() {
        this.intervals.forEach(interval => clearInterval(interval));
        this.intervals = [];
        this.isActive = false;
        this.log("🛑 Refresh-free monitor durduruldu");
    }
    
    // LOG
    log(message) {
        console.log(`[RefreshFreeMonitor] ${message}`);
    }
    
    startTime = Date.now();
}

// KULLANIM VE TEST
console.log("🚀 Refresh-Free Reddit Monitor v3.0.0 yüklendi!");
console.log("📋 Test komutları:");
console.log("   const monitor = new RefreshFreeRedditMonitor()");
console.log("   monitor.onNewMessage(msg => console.log('Yeni:', msg))");
console.log("   monitor.forceCheck()     // Manuel kontrol");
console.log("   monitor.forceLoad()      // Manuel force load");
console.log("   monitor.displayStats()   // İstatistikler");
console.log("   monitor.getAICommands()  // /ai komutlarını göster");

// Event listener örnekleri
console.log("\n📡 Event listener örnekleri:");
console.log("   document.addEventListener('redditNewMessages', e => console.log('Yeni mesajlar:', e.detail))");
console.log("   document.addEventListener('redditAICommand', e => console.log('AI Komutu:', e.detail))");
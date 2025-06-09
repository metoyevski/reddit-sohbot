// Monitor'u başlat
const monitor = new RefreshFreeRedditMonitor();

// /ai komutları için callback
monitor.onNewMessage((message) => {
    if (message.text.toLowerCase().startsWith('/ai ')) {
        console.log(`🤖 YENİ AI KOMUTU: ${message.author} - "${message.text}"`);
    }
});

// Event listener'lar
document.addEventListener('redditAICommand', (event) => {
    const { message, command } = event.detail;
    console.log(`AI KOMUTU YAKALANDI: ${command}`);
});

// Manuel testler
setTimeout(() => {
    console.log("=== EN SON MESAJLAR ===");
    console.log(monitor.getLatestMessages(5));
}, 5000);

setTimeout(() => {
    console.log("=== AI KOMUTLARI ===");
    console.log(monitor.getAICommands());
}, 10000);

// İstatistikleri göster
setInterval(() => {
    monitor.displayStats();
}, 30000);
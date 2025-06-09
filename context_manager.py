from collections import deque
from datetime import datetime
from config import CONTEXT_WINDOW_SIZE, CONTEXT_PROMPT_USER_MESSAGES, CONTEXT_PROMPT_AI_RESPONSES

class ContextManager:
    def __init__(self, max_size=CONTEXT_WINDOW_SIZE):
        self.messages = deque(maxlen=max_size)
        self.my_responses = deque(maxlen=max_size)

    def add_user_message(self, username, message, timestamp_str=None):
        self.messages.append({
            'type': 'user',
            'username': username,
            'content': message,
            'timestamp': timestamp_str or datetime.now().strftime('%H:%M:%S')
        })

    def add_my_response(self, original_response, summary, timestamp_str=None):
        self.my_responses.append({
            'original': original_response,
            'summary': summary,
            'timestamp': timestamp_str or datetime.now().strftime('%H:%M:%S')
        })

    def get_context_string(self):
        context = "Aşağıda real-time Reddit chat geçmişi ve senin (AI) önceki yanıtların yer almaktadır. Bu bilgileri kullanarak yeni soruya yanıt vereceksin. Yanıtın en fazla 150 kelimelik olması gerekiyor. Yanıtını tek paragrafta yazacaksın. Yanıtlarında herhangi bir markdown kullanmayacaksın.\n"
        
        # Real-time mesaj sayısı bilgisi
        total_messages = len(self.messages)
        total_responses = len(self.my_responses)
        context += f"AKTIF SOHBET DURUMU: {total_messages} mesaj, {total_responses} AI yanıtı izlenmekte.\n\n"
        
        context += "SON SOHBET GEÇMİŞİ (en yeniden en eskiye doğru):\n"
        user_messages_in_context = list(self.messages)
        if not user_messages_in_context:
            context += "- Henüz okunmuş kullanıcı mesajı yok.\n"
        else:
            recent_messages = user_messages_in_context[-CONTEXT_PROMPT_USER_MESSAGES:]
            for i, msg in enumerate(reversed(recent_messages)):
                # Mesaj uzunluğuna göre dinamik kırpma
                max_length = 300 if len(recent_messages) <= 20 else 200
                content = msg['content'][:max_length]
                if len(msg['content']) > max_length:
                    content += "..."
                    
                context += f"{i+1}. [{msg['timestamp']}] {msg['username']}: \"{content}\"\n"
        
        if self.my_responses:
            context += f"\nSENİN (AI) SON {min(len(self.my_responses), CONTEXT_PROMPT_AI_RESPONSES)} YANITININ:\n"
            ai_responses_in_context = list(self.my_responses)
            recent_responses = ai_responses_in_context[-CONTEXT_PROMPT_AI_RESPONSES:]
            for i, resp in enumerate(reversed(recent_responses)):
                context += f"{i+1}. [{resp['timestamp']}] Yanıt özetin: \"{resp['summary']}\"\n"
        else:
            context += "\n- Henüz önceki bir yanıtın (AI) yok.\n"
        
        context += f"\n🎯 YENİ SORU/İSTEK (yukarıdaki {total_messages} mesajlık bağlamı kullanarak yanıtla):\n"
        return context
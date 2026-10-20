import { useState, useRef, useEffect } from 'react';
import { Bot, Send, User, BookOpen, Lightbulb } from 'lucide-react';
import { sendCopilotMessage } from '../../services/api';
import { MessageMarkdown } from '../copilot/MessageMarkdown';

const QUICK_PROMPTS = [
  'Tại sao hệ thống lại khuyên tôi nên tái cơ cấu?',
  'Tình hình chu kỳ thị trường theo mô hình ML ra sao?',
  'Tỷ trọng Vàng SJC của tôi hiện tại đã hợp lý chưa?',
  'Cơ chế lãi kép của sổ tiết kiệm hoạt động như thế nào?'
];

export function CopilotTab() {
  const [messages, setMessages] = useState<Array<{
    role: 'user' | 'assistant';
    content: string;
    time: string;
    references?: string[];
  }>>([
    {
      role: 'assistant',
      content: `Xin chào! Tôi là cố vấn VNxCapital. Bạn có thể hỏi về danh mục, phân bổ tài sản, tín hiệu thị trường và tiết kiệm của mình.`,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, sending]);

  const handleSend = async (customText?: string) => {
    const textToSend = (customText || input).trim();
    if (!textToSend || sending) return;

    const userTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: textToSend, time: userTime }
    ]);
    if (!customText) setInput('');
    setSending(true);

    try {
      const res = await sendCopilotMessage(textToSend);
      const assistantTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: res.reply,
          time: assistantTime,
          references: res.references
        }
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Xin lỗi, đã xảy ra sự cố khi kết nối với cố vấn. Bạn vui lòng thử lại sau giây lát nhé.',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="vnx-panel p-4 space-y-4 flex flex-col h-[750px] relative">
      <div className="border-b border-border-subtle pb-3 shrink-0">
        <h2 className="text-base font-bold text-text-primary">Cố vấn</h2>
      </div>

      {/* Quick Prompts Chips */}
      <div className="flex flex-wrap gap-2 shrink-0">
        <span className="text-[11px] font-bold text-text-muted flex items-center gap-1 py-1">
          <Lightbulb className="w-3.5 h-3.5 text-accent-gold" /> Gợi ý câu hỏi:
        </span>
        {QUICK_PROMPTS.map((prompt, idx) => (
          <button
            key={idx}
            disabled={sending}
            onClick={() => handleSend(prompt)}
            className="px-3 py-1 rounded-full bg-surface-container hover:bg-surface-container-high border border-border-subtle text-text-primary text-[11px] font-medium transition-all text-left"
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto pr-2 space-y-4">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex min-w-0 gap-3 max-w-3xl ${msg.role === 'user' ? 'ml-auto flex-row-reverse' : ''}`}
          >
            {/* Avatar */}
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${
                msg.role === 'user'
                  ? 'bg-surface-container-high text-text-primary border border-border-subtle'
                  : 'bg-accent-emerald text-white '
              }`}
            >
              {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>

            {/* Content Bubble */}
            <div
              className={`min-w-0 p-4 rounded-2xl text-xs space-y-2 leading-relaxed ${
                msg.role === 'user'
                  ? 'rounded-tr-none bg-surface-container-high border border-border-subtle text-text-primary'
                  : 'rounded-tl-none bg-surface-container-low border border-border-subtle text-text-primary'
              }`}
            >
              {msg.role === 'assistant' ? (
                <MessageMarkdown content={msg.content} />
              ) : (
                <p className="leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere]">{msg.content}</p>
              )}

              {/* Reference citations if any */}
              {msg.references && msg.references.length > 0 && (
                <div className="pt-2 mt-2 border-t border-border-subtle text-[11px] text-text-muted space-y-1">
                  <span className="font-bold flex items-center gap-1 text-accent-emerald">
                    <BookOpen className="w-3 h-3" /> Nguồn tri thức tham chiếu:
                  </span>
                  {msg.references.map((ref, rIdx) => (
                    <div key={rIdx} className="pl-3 border-l-2 border-accent-emerald/40 italic">
                      "{ref}"
                    </div>
                  ))}
                </div>
              )}

              <span className="block text-[10px] text-text-muted text-right pt-1">{msg.time}</span>
            </div>
          </div>
        ))}

        {/* Typing indicator */}
        {sending && (
          <div className="flex gap-3 max-w-xl">
            <div className="w-8 h-8 rounded-full bg-accent-emerald text-white flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="p-3.5 rounded-2xl rounded-tl-none bg-surface-container-low border border-border-subtle text-xs text-text-muted flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse"></div>
              <div className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse [animation-delay:200ms]"></div>
              <div className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse [animation-delay:400ms]"></div>
              <span className="ml-1 text-[11px]">
                Cố vấn đang soạn câu trả lời…
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <div className="pt-3 border-t border-border-subtle flex gap-2 shrink-0">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Hỏi về danh mục của bạn…"
          disabled={sending}
          className="flex-1 px-4 py-2.5 rounded-lg border border-border-subtle bg-surface-container-lowest text-xs text-text-primary placeholder:text-text-muted focus:outline-hidden focus:border-accent-emerald transition-colors"
        />
        <button
          onClick={() => handleSend()}
          disabled={sending || !input.trim()}
          className={`px-4 py-2.5 rounded-lg text-white font-bold flex items-center gap-1.5  transition-all text-xs ${
            sending || !input.trim()
              ? 'bg-accent-emerald/50 cursor-not-allowed'
              : 'bg-accent-emerald hover:bg-accent-emerald/90'
          }`}
        >
          <Send className="w-3.5 h-3.5" />
          <span>Gửi</span>
        </button>
      </div>

    </div>
  );
}

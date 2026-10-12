import { useState, useRef, useEffect } from 'react';
import { Bot, Send, Sparkles, User, BookOpen, Lightbulb, Key, Eye, EyeOff, CheckCircle2, ExternalLink, X, ShieldCheck } from 'lucide-react';
import { sendCopilotMessage, getCopilotStatus, saveCopilotApiKey } from '../../services/api';

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
      content: `Xin chào! Tôi là **EquiFolio Copilot**, trợ lý tư vấn tài chính định lượng thông minh của bạn.

Tôi có quyền truy cập trực tiếp vào **Sổ cái kép thời gian thực** (NAV, độ lệch tỷ trọng Drift, các sổ tiết kiệm) cùng **Mô hình học máy ONNX nhận diện chu kỳ thị trường**.

Bạn có thể bấm vào các gợi ý bên dưới hoặc đặt bất kỳ câu hỏi nào về danh mục của mình nhé!`,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // API Key State & Modal
  const [hasApiKey, setHasApiKey] = useState(false);
  const [modelName, setModelName] = useState('gemini-1.5-flash');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState('');

  const checkStatus = async () => {
    try {
      const status = await getCopilotStatus();
      setHasApiKey(status.hasApiKey);
      if (status.model) setModelName(status.model);
    } catch {
      // fallback
    }
  };

  useEffect(() => {
    checkStatus();
    const stored = localStorage.getItem('gemini_api_key');
    if (stored) {
      setApiKeyInput(stored);
    }
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, sending]);

  const handleSaveApiKey = async () => {
    const trimmed = apiKeyInput.trim();
    await saveCopilotApiKey(trimmed);
    setHasApiKey(!!trimmed);
    setSaveSuccessMsg(trimmed ? 'Đã lưu và kích hoạt Google Gemini API Key!' : 'Đã xóa API Key, trở về chế độ Local RAG.');
    setTimeout(() => {
      setSaveSuccessMsg('');
      setIsModalOpen(false);
    }, 1200);
  };

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
          content: 'Xin lỗi, đã xảy ra sự cố khi kết nối tới động cơ Copilot. Bạn vui lòng thử lại sau giây lát nhé.',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-6 flex flex-col h-[750px] relative">
      {/* Header */}
      <div className="border-b border-border-subtle pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shrink-0">
        <div>
          <h2 className="text-lg font-bold text-text-primary tracking-tight">
            Trợ Lý Tài Chính Thông Minh (Financial Copilot)
          </h2>
          <p className="text-xs text-text-secondary">
            Phân tích thời gian thực với dữ liệu Sổ cái kép & Mô hình máy học chu kỳ thị trường
          </p>
        </div>

        <div className="flex items-center gap-2">
          {hasApiKey ? (
            <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-accent-emerald-light text-accent-emerald text-xs font-bold border border-accent-emerald/30 shadow-xs">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Google Gemini ({modelName})</span>
            </span>
          ) : (
            <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-surface-container-high text-text-secondary text-xs font-semibold border border-border-subtle">
              <Sparkles className="w-3.5 h-3.5 text-accent-gold" />
              <span>Local RAG Mode</span>
            </span>
          )}

          <button
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-surface-container hover:bg-surface-container-high border border-border-subtle text-text-primary text-xs font-medium transition-all"
            title="Cài đặt Google Gemini API Key"
          >
            <Key className="w-3.5 h-3.5 text-accent-emerald" />
            <span>{hasApiKey ? 'Đổi API Key' : 'Nhập API Key'}</span>
          </button>
        </div>
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
            className={`flex gap-3 max-w-3xl ${msg.role === 'user' ? 'ml-auto flex-row-reverse' : ''}`}
          >
            {/* Avatar */}
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${
                msg.role === 'user'
                  ? 'bg-surface-container-high text-text-primary border border-border-subtle'
                  : 'bg-accent-emerald text-white shadow-sm'
              }`}
            >
              {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
            </div>

            {/* Content Bubble */}
            <div
              className={`p-4 rounded-2xl text-xs space-y-2 leading-relaxed ${
                msg.role === 'user'
                  ? 'rounded-tr-none bg-surface-container-high border border-border-subtle text-text-primary'
                  : 'rounded-tl-none bg-surface-container-low border border-border-subtle text-text-primary'
              }`}
            >
              {msg.content.split('\n\n').map((para, pIdx) => (
                <p key={pIdx} className="leading-relaxed whitespace-pre-wrap">{para}</p>
              ))}

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
                {hasApiKey ? 'Google Gemini đang phân tích danh mục & soạn câu trả lời...' : 'Copilot đang phân tích danh mục & tra cứu tri thức...'}
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
          placeholder="Hỏi Copilot về tỷ trọng danh mục, độ lệch Drift, mô hình ML hoặc lý do tái cơ cấu..."
          disabled={sending}
          className="flex-1 px-4 py-2.5 rounded-lg border border-border-subtle bg-surface-container-lowest text-xs text-text-primary placeholder:text-text-muted focus:outline-hidden focus:border-accent-emerald transition-colors"
        />
        <button
          onClick={() => handleSend()}
          disabled={sending || !input.trim()}
          className={`px-4 py-2.5 rounded-lg text-white font-bold flex items-center gap-1.5 shadow-xs transition-all text-xs ${
            sending || !input.trim()
              ? 'bg-accent-emerald/50 cursor-not-allowed'
              : 'bg-accent-emerald hover:bg-accent-emerald/90'
          }`}
        >
          <Send className="w-3.5 h-3.5" />
          <span>Gửi</span>
        </button>
      </div>

      {/* API Key Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-surface-container-lowest border border-border-subtle rounded-2xl shadow-xl w-full max-w-md p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-border-subtle">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-accent-emerald-light text-accent-emerald flex items-center justify-center">
                  <Key className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-text-primary">Cấu hình Google Gemini API Key</h3>
                  <p className="text-[11px] text-text-secondary">Trực tiếp kết nối mô hình {modelName}</p>
                </div>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-text-muted hover:text-text-primary p-1 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-text-secondary leading-relaxed">
              EquiFolio sẽ kết nối trực tiếp với <strong>Google Gemini API</strong> để tự động tổng hợp số liệu tài chính thời gian thực (NAV, số dư tiền mặt, tỷ lệ tài sản, lệnh lô 100 HOSE, tín hiệu chu kỳ ONNX) vào câu trả lời.
            </p>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-text-primary">Google API Key</label>
              <div className="relative">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={apiKeyInput}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  placeholder="AIzaSy..."
                  className="w-full px-3 py-2 pr-10 rounded-lg border border-border-subtle bg-surface-container-low text-xs text-text-primary font-mono focus:outline-hidden focus:border-accent-emerald"
                />
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
                >
                  {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between text-[11px] text-text-muted bg-surface-container p-2.5 rounded-lg border border-border-subtle">
              <span className="flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-accent-emerald" /> Key được mã hóa và lưu tại trình duyệt
              </span>
              <a
                href="https://aistudio.google.com/app/apikey"
                target="_blank"
                rel="noreferrer"
                className="text-accent-emerald hover:underline font-semibold flex items-center gap-0.5"
              >
                Lấy Key <ExternalLink className="w-3 h-3" />
              </a>
            </div>

            {saveSuccessMsg && (
              <div className="p-2.5 rounded-lg bg-accent-emerald-light text-accent-emerald text-xs font-semibold flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" />
                <span>{saveSuccessMsg}</span>
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2">
              {hasApiKey && (
                <button
                  type="button"
                  onClick={() => {
                    setApiKeyInput('');
                    saveCopilotApiKey('');
                    setHasApiKey(false);
                    setSaveSuccessMsg('Đã xóa API Key!');
                    setTimeout(() => {
                      setSaveSuccessMsg('');
                      setIsModalOpen(false);
                    }, 1000);
                  }}
                  className="px-3 py-2 rounded-lg text-accent-rose hover:bg-accent-rose-light text-xs font-semibold mr-auto transition-colors"
                >
                  Xóa Key
                </button>
              )}
              <button
                type="button"
                onClick={() => setIsModalOpen(false)}
                className="px-4 py-2 rounded-lg border border-border-subtle text-text-secondary hover:text-text-primary text-xs font-medium"
              >
                Đóng
              </button>
              <button
                type="button"
                onClick={handleSaveApiKey}
                className="px-4 py-2 rounded-lg bg-accent-emerald hover:bg-accent-emerald/90 text-white text-xs font-bold shadow-xs transition-all"
              >
                Lưu & Kích hoạt
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import { useState } from 'react';
import { Bot, Send, Sparkles } from 'lucide-react';

export function CopilotTab() {
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'assistant'; content: string; time: string }>>([
    {
      role: 'user',
      content: 'Tại sao hệ thống lại khuyên tao nên bán bớt cổ phiếu HPG để mua thêm Vàng SJC lúc này?',
      time: '14:20'
    },
    {
      role: 'assistant',
      content: `Chào anh Alex,

Lý do hệ thống đề xuất tái cơ cấu xuất phát từ 2 căn cứ khoa học:

1. **Lệch tỷ trọng tự nhiên (Drift Detection):** Đợt tăng giá vừa qua đã đẩy tỷ trọng Cổ phiếu của anh lên **55.1%**, vượt xa mốc mục tiêu **35.0%** đã thống nhất trong hồ sơ rủi ro ban đầu (độ lệch > 20%).
2. **Tín hiệu chu kỳ liên thị trường:** Mô hình LightGBM ONNX nhận thấy tỷ lệ Vàng/VN-Index đang ở vùng đáy chu kỳ và bắt đầu có dấu hiệu đảo chiều tích lũy. Việc chốt lời bớt 2.800 cp HPG (lô chẵn 100 sàn HOSE) để chuyển sang 9 chỉ Vàng SJC giúp anh khóa lợi nhuận và phòng hộ lạm phát hiệu quả.

*Lưu ý nguyên tắc Zero-Trust: Em chỉ đưa ra khuyến nghị phân tích, anh vui lòng xem lại trước khi đặt lệnh ngoài app TCBS nhé!`,
      time: '14:21'
    }
  ]);
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (!input.trim()) return;
    const userMsg = input.trim();
    setInput('');
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: userMsg, time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) },
      {
        role: 'assistant',
        content: `Cảm ơn anh đã hỏi! Em đã tra cứu tài liệu đầu tư qua cơ chế Hybrid Search RRF (PostgreSQL pgvector) và nhận thấy: danh mục của anh hiện đang được tối ưu hóa theo mô hình Markowitz với hệ số λ = 3.88. Với câu hỏi "${userMsg}", em khuyến nghị anh giữ kỷ luật danh mục, không nên fomo gia tăng tỷ trọng cổ phiếu khi chưa có điểm cân bằng mới.`,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ]);
  };

  return (
    <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-6">
      <div className="border-b border-border-subtle pb-4 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-text-primary tracking-tight">Trợ Lý Tài Chính Thông Minh (Financial Copilot)</h2>
          <p className="text-xs text-text-secondary">Trò chuyện tự nhiên, tra cứu Hybrid Search RRF tài chính và hỗ trợ ra quyết định an toàn</p>
        </div>
        <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-accent-emerald-light text-accent-emerald text-xs font-bold border border-accent-emerald/30">
          <Sparkles className="w-3.5 h-3.5" />
          <span>PostgreSQL RRF Active</span>
        </span>
      </div>

      {/* Chat Messages Log */}
      <div className="space-y-4 max-h-[500px] overflow-y-auto pr-2">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex gap-3 max-w-2xl ${msg.role === 'user' ? '' : 'ml-auto flex-row-reverse'}`}
          >
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${
                msg.role === 'user'
                  ? 'bg-surface-container text-text-primary border border-border-subtle'
                  : 'bg-accent-emerald text-white shadow-sm'
              }`}
            >
              {msg.role === 'user' ? 'AN' : <Bot className="w-4 h-4" />}
            </div>
            <div
              className={`p-4 rounded-2xl text-xs space-y-2 leading-relaxed ${
                msg.role === 'user'
                  ? 'rounded-tl-none bg-surface-container-low border border-border-subtle text-text-primary'
                  : 'rounded-tr-none bg-accent-emerald-light/40 border border-accent-emerald/30 text-text-primary'
              }`}
            >
              {msg.content.split('\n\n').map((para, pIdx) => (
                <p key={pIdx}>{para}</p>
              ))}
              <span className="block text-[10px] text-text-muted text-right pt-1">{msg.time}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Chat Input */}
      <div className="pt-2 border-t border-border-subtle flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Hỏi Copilot về danh mục, tỷ trọng, hoặc lý do mua bán..."
          className="flex-1 px-4 py-2.5 rounded-lg border border-border-subtle bg-surface-container-lowest text-xs text-text-primary placeholder:text-text-muted focus:outline-hidden focus:border-accent-emerald transition-colors"
        />
        <button
          onClick={handleSend}
          className="px-4 py-2.5 rounded-lg bg-accent-emerald text-white hover:bg-accent-emerald/90 transition-colors text-xs font-bold flex items-center gap-1.5 shadow-xs"
        >
          <Send className="w-3.5 h-3.5" />
          <span>Gửi</span>
        </button>
      </div>
    </div>
  );
}

import { useState } from 'react';
import { Award, CheckCircle2, ShieldCheck, ArrowRight, RefreshCw } from 'lucide-react';
import { submitRiskSurvey } from '../../services/api';
import { useToast } from '../../context/ToastContext';

interface SurveyTabProps {
  surveyScores: number[];
  setSurveyScores: (scores: number[]) => void;
  onApplyProfile?: () => void;
}

export function SurveyTab({ surveyScores, setSurveyScores, onApplyProfile }: SurveyTabProps) {
  const toast = useToast();
  const [submitting, setSubmitting] = useState(false);

  const questions = [
    {
      q: "1. Kỳ hạn đầu tư dự kiến",
      desc: "Thời gian bạn dự kiến duy trì đầu tư mà không cần rút vốn chi tiêu?",
      score: surveyScores[0],
      options: [
        { text: "Dưới 1 năm", val: 0, tag: "Rất ngắn" },
        { text: "1 đến 3 năm", val: 7, tag: "Trung hạn" },
        { text: "3 đến 5 năm", val: 14, tag: "Dài hạn" },
        { text: "Trên 5 năm", val: 20, tag: "Chiến lược" },
      ]
    },
    {
      q: "2. Tính ổn định dòng tiền",
      desc: "Tình hình tài chính và quỹ dự phòng khẩn cấp hàng tháng?",
      score: surveyScores[1],
      options: [
        { text: "Không có quỹ dự phòng", val: 0, tag: "Rủi ro cao" },
        { text: "Dư <10% & Dự phòng mỏng", val: 7, tag: "Tạm ổn" },
        { text: "Dư 20-40% & Quỹ 6 tháng", val: 14, tag: "Vững vàng" },
        { text: "Dư >40% & Quỹ >12 tháng", val: 20, tag: "Dồi dào" },
      ]
    },
    {
      q: "3. Mục tiêu tài chính ưu tiên",
      desc: "Mục tiêu quan trọng nhất đối với danh mục tài sản này?",
      score: surveyScores[2],
      options: [
        { text: "Bảo toàn vốn tuyệt đối", val: 0, tag: "An toàn" },
        { text: "Bù đắp lạm phát nhẹ", val: 7, tag: "Thận trọng" },
        { text: "Tăng trưởng cân bằng vốn", val: 14, tag: "Cân bằng" },
        { text: "Tối đa hóa tài sản dài hạn", val: 20, tag: "Tăng trưởng" },
      ]
    },
    {
      q: "4. Thử nghiệm khi giảm -15%",
      desc: "Phản ứng của bạn nếu danh mục sụt giảm -15% trong 1 tháng?",
      score: surveyScores[3],
      options: [
        { text: "Bán cắt lỗ toàn bộ", val: 0, tag: "Hoảng loạn" },
        { text: "Lo lắng, bán một nửa", val: 7, tag: "E ngại" },
        { text: "Bình tĩnh, giữ kỷ luật", val: 14, tag: "Kỷ luật" },
        { text: "Mua thêm quyết liệt", val: 20, tag: "Cơ hội" },
      ]
    },
    {
      q: "5. Kinh nghiệm thực tế",
      desc: "Kinh nghiệm đầu tư cổ phiếu, vàng và các kênh tài sản?",
      score: surveyScores[4],
      options: [
        { text: "Chưa từng đầu tư", val: 0, tag: "Mới tinh" },
        { text: "Chỉ gửi tiết kiệm ngân hàng", val: 6, tag: "Cơ bản" },
        { text: "Đã đầu tư chứng khoán >1 năm", val: 12, tag: "Đã có KN" },
        { text: "Chuyên sâu thị trường >3 năm", val: 20, tag: "Chuyên nghiệp" },
      ]
    },
  ];

  const totalScore = surveyScores.reduce((acc: number, curr: number) => acc + curr, 0);
  const lambdaRisk = (10.0 - 0.09 * totalScore).toFixed(2);
  let profileLabel = 'Bảo Thủ (Conservative)';
  let profileKey = 'CONSERVATIVE';
  let saaSummary = '20% Cổ phiếu • 20% Vàng • 60% Tiết kiệm';
  if (totalScore >= 75) {
    profileLabel = 'Tăng Trưởng (Growth)';
    profileKey = 'GROWTH';
    saaSummary = '60% Cổ phiếu • 25% Vàng • 15% Tiết kiệm';
  } else if (totalScore >= 50) {
    profileLabel = 'Cân Bằng (Balanced)';
    profileKey = 'BALANCED';
    saaSummary = '35% Cổ phiếu • 35% Vàng • 30% Tiết kiệm';
  }

  const handleSaveAndApply = async () => {
    setSubmitting(true);
    try {
      const answers = [
        { questionId: 1, selectedOption: surveyScores[0] === 20 ? 'D' : surveyScores[0] === 14 ? 'C' : surveyScores[0] === 7 ? 'B' : 'A', score: surveyScores[0] },
        { questionId: 2, selectedOption: surveyScores[1] === 20 ? 'D' : surveyScores[1] === 14 ? 'C' : surveyScores[1] === 7 ? 'B' : 'A', score: surveyScores[1] },
        { questionId: 3, selectedOption: surveyScores[2] === 20 ? 'D' : surveyScores[2] === 14 ? 'C' : surveyScores[2] === 7 ? 'B' : 'A', score: surveyScores[2] },
        { questionId: 4, selectedOption: surveyScores[3] === 20 ? 'D' : surveyScores[3] === 14 ? 'C' : surveyScores[3] === 7 ? 'B' : 'A', score: surveyScores[3] },
        { questionId: 5, selectedOption: surveyScores[4] === 20 ? 'D' : surveyScores[4] === 12 ? 'C' : surveyScores[4] === 6 ? 'B' : 'A', score: surveyScores[4] },
      ];

      try {
        await submitRiskSurvey({ answers });
      } catch (err) {
        console.warn("Backend not logged in, updating local profile state", err);
      }

      // Cập nhật profile cục bộ nếu dùng phiên khách
      try {
        const saved = localStorage.getItem('equifolio_user');
        const userObj = saved ? JSON.parse(saved) : {};
        localStorage.setItem('equifolio_user', JSON.stringify({
          ...userObj,
          riskScore: totalScore,
          riskAversionLambda: Number(lambdaRisk),
          riskProfile: profileKey
        }));
      } catch (e) {}

      localStorage.setItem('equifolio_onboarding_dismissed', 'true');
      toast.success(
        `Đã xác lập hồ sơ: ${profileLabel} (λ = ${lambdaRisk}). Mô hình Markowitz đã được kích hoạt theo khẩu vị của bạn!`,
        "Cá nhân hóa thành công"
      );

      if (onApplyProfile) {
        onApplyProfile();
      }
    } catch (e: any) {
      toast.error(e.message || "Lỗi lưu kết quả khảo sát", "Thất bại");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="bg-surface-container-lowest border border-border-subtle rounded-2xl p-6 lg:p-8 shadow-xs space-y-6">
      {/* Header */}
      <div className="border-b border-border-subtle pb-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-8 h-8 rounded-lg bg-accent-emerald-light border border-accent-emerald/30 flex items-center justify-center text-accent-emerald">
              <Award className="w-4 h-4" />
            </span>
            <h2 className="text-lg font-extrabold text-text-primary tracking-tight">
              Bộ Khảo Sát Khẩu Vị Rủi Ro Chuẩn Hóa (MiFID II)
            </h2>
          </div>
          <p className="text-xs text-text-secondary font-medium max-w-2xl">
            5 câu hỏi đo lường Năng lực tài chính khách quan và Tâm lý chấp nhận biến động chủ quan, tính toán chính xác Hệ số Ngại Rủi Ro λ của bạn.
          </p>
        </div>

        {/* Real-time Score Pill */}
        <div className="flex items-center gap-3 px-4 py-2.5 rounded-xl bg-surface-container-low border border-border-subtle self-start md:self-auto shrink-0">
          <div>
            <span className="text-[10px] uppercase font-bold text-text-muted tracking-wider block">Điểm Hiện Tại</span>
            <span className="text-base font-black font-mono-num text-accent-emerald">{totalScore} <span className="text-xs text-text-muted font-medium">/ 100đ</span></span>
          </div>
          <div className="w-px h-8 bg-border-subtle"></div>
          <div>
            <span className="text-[10px] uppercase font-bold text-text-muted tracking-wider block">Hệ Số λ</span>
            <span className="text-base font-black font-mono-num text-text-primary">{lambdaRisk}</span>
          </div>
        </div>
      </div>

      {/* 5 Questions */}
      <div className="space-y-4">
        {questions.map((item, qIdx) => (
          <div key={qIdx} className="p-5 rounded-xl border border-border-subtle bg-surface-container-low/50 hover:bg-surface-container-low transition-colors space-y-3.5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <span className="font-extrabold text-text-primary text-sm">{item.q}</span>
                <p className="text-xs text-text-secondary mt-0.5 font-medium">{item.desc}</p>
              </div>
              <span className="px-3 py-1 rounded-lg bg-surface-container text-xs font-bold font-mono-num text-accent-emerald border border-border-subtle shadow-2xs shrink-0">
                {item.score} / 20đ
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5 pt-1">
              {item.options.map((opt, oIdx) => {
                const isSelected = item.score === opt.val;
                return (
                  <button
                    key={oIdx}
                    type="button"
                    onClick={() => {
                      const updated = [...surveyScores];
                      updated[qIdx] = opt.val;
                      setSurveyScores(updated);
                    }}
                    className={`p-3 rounded-xl border text-left text-xs transition-all cursor-pointer ${
                      isSelected
                        ? 'border-accent-emerald bg-surface-container-high text-text-primary font-bold shadow-xs ring-1 ring-accent-emerald/30'
                        : 'border-border-subtle bg-surface-container-lowest text-text-secondary hover:border-border-highlight hover:bg-surface-container-low'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] px-1.5 py-0.2 rounded font-bold uppercase tracking-wider bg-surface-container text-text-muted">
                        {opt.tag}
                      </span>
                      {isSelected && <CheckCircle2 className="w-3.5 h-3.5 text-accent-emerald shrink-0" />}
                    </div>
                    <div className="font-bold text-text-primary text-xs mt-1">{opt.text}</div>
                    <div className="text-[10px] text-text-muted font-mono-num mt-1">+{opt.val} điểm</div>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Aggregate Result & Apply Action Card */}
      <div className="p-6 rounded-2xl border-2 border-accent-emerald/30 bg-gradient-to-r from-accent-emerald-light via-surface-container-lowest to-surface-container-lowest flex flex-col lg:flex-row lg:items-center justify-between gap-6 shadow-xs">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse"></span>
            <h4 className="text-sm font-extrabold text-text-primary uppercase tracking-wider">
              Kết Quả Khảo Sát Phân Tầng Khẩu Vị
            </h4>
          </div>
          <p className="text-xs text-text-secondary font-medium">
            Điểm tổng: <strong className="text-accent-emerald font-mono-num">{totalScore}/100</strong> • Hệ số ngại rủi ro <strong className="text-text-primary font-mono-num">λ = {lambdaRisk}</strong> • Nhóm <strong className="text-text-primary">{profileLabel}</strong>
          </p>
          <div className="pt-1 flex items-center gap-2">
            <span className="text-[11px] font-bold text-text-muted">Mục tiêu SAA chuẩn:</span>
            <span className="text-[11px] font-extrabold text-accent-emerald bg-accent-emerald-light px-2 py-0.5 rounded-md border border-accent-emerald/30 font-mono-num">
              {saaSummary}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <button
            type="button"
            onClick={handleSaveAndApply}
            disabled={submitting}
            className="flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-accent-emerald hover:opacity-90 text-white font-bold text-xs shadow-sm hover:shadow transition-all cursor-pointer"
          >
            {submitting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Đang lưu khẩu vị...</span>
              </>
            ) : (
              <>
                <ShieldCheck className="w-4 h-4" />
                <span>Áp dụng vào Danh mục & Trở về Tổng quan</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

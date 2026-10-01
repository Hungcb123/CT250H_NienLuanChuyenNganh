interface SurveyTabProps {
  surveyScores: number[];
  setSurveyScores: (scores: number[]) => void;
}

export function SurveyTab({ surveyScores, setSurveyScores }: SurveyTabProps) {
  const questions = [
    {
      q: "1. Kỳ hạn đầu tư dự kiến",
      desc: "Thời gian bạn dự kiến duy trì đầu tư mà không cần rút vốn chi tiêu?",
      score: surveyScores[0],
      options: [
        { text: "Dưới 1 năm", val: 0 },
        { text: "1 đến 3 năm", val: 7 },
        { text: "3 đến 5 năm", val: 14 },
        { text: "Trên 5 năm", val: 20 },
      ]
    },
    {
      q: "2. Tính ổn định dòng tiền",
      desc: "Tình hình tài chính và quỹ dự phòng khẩn cấp hàng tháng?",
      score: surveyScores[1],
      options: [
        { text: "Không có quỹ dự phòng", val: 0 },
        { text: "Dư <10% & Dự phòng mỏng", val: 7 },
        { text: "Dư 20-40% & Quỹ 6 tháng", val: 14 },
        { text: "Dư >40% & Quỹ >12 tháng", val: 20 },
      ]
    },
    {
      q: "3. Mục tiêu tài chính ưu tiên",
      desc: "Mục tiêu quan trọng nhất đối với danh mục tài sản này?",
      score: surveyScores[2],
      options: [
        { text: "Bảo toàn vốn tuyệt đối", val: 0 },
        { text: "Bù đắp lạm phát nhẹ", val: 7 },
        { text: "Tăng trưởng cân bằng vốn", val: 14 },
        { text: "Tối đa hóa tài sản dài hạn", val: 20 },
      ]
    },
    {
      q: "4. Thử nghiệm khi giảm -15%",
      desc: "Phản ứng của bạn nếu danh mục sụt giảm -15% trong 1 tháng?",
      score: surveyScores[3],
      options: [
        { text: "Bán cắt lỗ toàn bộ", val: 0 },
        { text: "Lo lắng, bán một nửa", val: 7 },
        { text: "Bình tĩnh, giữ kỷ luật", val: 14 },
        { text: "Mua thêm quyết liệt", val: 20 },
      ]
    },
    {
      q: "5. Kinh nghiệm thực tế",
      desc: "Kinh nghiệm đầu tư cổ phiếu, vàng và các kênh tài sản?",
      score: surveyScores[4],
      options: [
        { text: "Chưa từng đầu tư", val: 0 },
        { text: "Chỉ gửi tiết kiệm ngân hàng", val: 6 },
        { text: "Đã đầu tư chứng khoán >1 năm", val: 12 },
        { text: "Chuyên sâu thị trường >3 năm", val: 20 },
      ]
    },
  ];

  const totalScore = surveyScores.reduce((acc: number, curr: number) => acc + curr, 0);
  const lambdaRisk = (10.0 - 0.09 * totalScore).toFixed(2);
  let profileLabel = 'Thận Trọng (Conservative)';
  let saaSummary = '20% Cổ phiếu • 20% Vàng • 60% Tiết kiệm';
  if (totalScore >= 75) {
    profileLabel = 'Tăng Trưởng (Aggressive)';
    saaSummary = '60% Cổ phiếu • 25% Vàng • 15% Tiết kiệm';
  } else if (totalScore >= 50) {
    profileLabel = 'Cân Bằng (Balanced)';
    saaSummary = '35% Cổ phiếu • 35% Vàng • 30% Tiết kiệm';
  }

  return (
    <div className="bg-surface-container-lowest border border-border-subtle rounded-xl p-6 shadow-sm space-y-6">
      <div className="border-b border-border-subtle pb-4">
        <h2 className="text-lg font-bold text-text-primary tracking-tight">Bộ Khảo Sát Khẩu Vị Rủi Ro Chuẩn Hóa (MiFID II)</h2>
        <p className="text-xs text-text-secondary">5 câu hỏi đo lường Năng lực tài chính khách quan và Tâm lý chịu đựng sụt giảm chủ quan</p>
      </div>

      <div className="space-y-4">
        {questions.map((item, qIdx) => (
          <div key={qIdx} className="p-4 rounded-lg border border-border-subtle bg-surface-container-low text-xs space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="font-bold text-text-primary text-sm">{item.q}</span>
                <p className="text-text-secondary mt-0.5">{item.desc}</p>
              </div>
              <span className="px-3 py-1 rounded-full bg-surface-container text-xs font-bold text-accent-emerald border border-border-subtle">
                {item.score} / 20đ
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
              {item.options.map((opt, oIdx) => (
                <button
                  key={oIdx}
                  type="button"
                  onClick={() => {
                    const updated = [...surveyScores];
                    updated[qIdx] = opt.val;
                    setSurveyScores(updated);
                  }}
                  className={`p-2.5 rounded-lg border text-left text-xs transition-all ${
                    item.score === opt.val
                      ? 'border-accent-emerald bg-accent-emerald-light/40 text-accent-emerald font-bold shadow-xs'
                      : 'border-border-subtle bg-surface-container-lowest text-text-secondary hover:border-slate-300'
                  }`}
                >
                  <div className="font-semibold">{opt.text}</div>
                  <div className="text-[10px] text-text-muted mt-0.5">+{opt.val} điểm</div>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Aggregate Result Card */}
      <div className="p-5 rounded-xl border border-accent-emerald/30 bg-accent-emerald-light/30 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h4 className="text-sm font-bold text-text-primary">Kết Quả Khảo Sát Tổng Hợp</h4>
          <p className="text-xs text-text-secondary mt-1">
            Tổng điểm: <span className="font-bold text-accent-emerald">{totalScore}/100</span> • Hệ số ngại rủi ro λ = <span className="font-bold">{lambdaRisk}</span> • Nhóm <span className="font-bold text-text-primary">{profileLabel}</span>
          </p>
        </div>
        <div className="text-left sm:text-right">
          <span className="text-xs font-bold px-3 py-1.5 rounded-lg bg-accent-emerald text-white inline-block">
            Tỷ trọng SAA: {saaSummary}
          </span>
        </div>
      </div>
    </div>
  );
}

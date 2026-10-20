import { netScoreLabel } from '../../utils/regimeDisplay';
import { FormEvent, useEffect, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ScatterChart,
  Scatter,
} from "recharts";
import { formatVND } from "../../utils/formatters";

type Section =
  "optimize" | "models" | "evaluation" | "performance" | "goals" | "knowledge";
type Point = {
  annualReturn: number;
  annualVolatility: number;
  weights: Record<string, number>;
};
type Optimization = {
  observations: number;
  from: string;
  to: string;
  optimal: Point;
  frontier: Point[];
};
type Prediction = { signal: number; confidence: number; regimeName: string };
type ModelStatus = {
  stockEngine?: string;
  nativeStockPrediction?: { available: boolean; status: string; session: string | null; modelId: string; classScores: number[]; netScore: number | null };
  stockPrediction: Prediction;
  goldPrediction: Prediction;
  models: {
    taaEnabled: boolean;
    featureVersion: string;
    stock: { loaded: boolean; metadata?: Record<string, string> };
    gold: { loaded: boolean; metadata?: Record<string, string> };
  };
};
type Evaluation = {
  ticker: string;
  artifactTrainEnd: string;
  dataEnd: string;
  folds: {
    trainEnd: string;
    testStart: string;
    purgeSessions: number;
    f1Macro: number;
    mcc: number;
    majorityBaselineF1: number;
  }[];
  backtest: {
    assumptions: { feePerTurnover: number };
    metrics: Record<
      string,
      {
        totalReturn: number;
        maxDrawdown: number;
        annualVolatility: number;
        turnover: number;
      }
    >;
    curves: Record<string, { date: string; nav: number }[]>;
  };
};
type Performance = {
  available: boolean;
  reason?: string;
  totalReturn: number;
  annualReturn: number;
  annualVolatility: number;
  maxDrawdown: number;
  sharpe: number;
  xirr: number | null;
  curve: { date: string; growthIndex: number }[];
};
type Goal = {
  id: number;
  title: string;
  targetAmount: number;
  allocatedAmount: number;
  monthlyContribution: number;
  annualRate: number;
  targetDate: string;
  version: number;
  projectedAmount: number;
  requiredMonthlyContribution: number;
  shortfall: number;
};
type Source = {
  id: string;
  title: string;
  source: string;
  chunk: number;
  content: string;
  retrievalMode: string;
};
const sections: [Section, string][] = [
  ["optimize", "Tối ưu lịch sử"],
  ["models", "Trạng thái ML"],
  ["evaluation", "Kiểm chứng ML"],
  ["performance", "Hiệu suất"],
  ["goals", "Mục tiêu tích lũy"],
  ["knowledge", "Kho tri thức"],
];
const inputClass =
  "w-full rounded-lg border border-border-subtle bg-surface-container-low px-3 py-2 text-sm text-text-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent-blue";
const buttonClass =
  "rounded-lg bg-accent-blue text-white px-4 py-2 text-sm font-semibold disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2";
const pct = (value: number) => `${(value * 100).toFixed(2)}%`;
async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch(`/api/v1/${path}`, {
    method,
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      response.status === 401
        ? "Đăng nhập để sử dụng dữ liệu của bạn."
        : payload.message || "Không tải được dữ liệu. Hãy thử lại.",
    );
  return payload.data;
}

export function ResearchWorkbench() {
  const [section, setSection] = useState<Section>("optimize");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [tickers, setTickers] = useState("FPT,HPG,TCB");
  const [lambda, setLambda] = useState(5);
  const [optimization, setOptimization] = useState<Optimization | null>(null);
  const [models, setModels] = useState<ModelStatus | null>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [performance, setPerformance] = useState<Performance | null>(null);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [editing, setEditing] = useState<Goal | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [retrieval, setRetrieval] = useState("");
  useEffect(() => {
    let cancelled = false;
    setError("");
    setNotice("");
    const load = async () => {
      if (section === "optimize") return;
      setBusy(true);
      try {
        if (section === "models") {
          const result = await request<ModelStatus>("research/models");
          if (!cancelled) setModels(result);
        }
        if (section === "evaluation") {
          const result = await request<Evaluation>("research/evaluation");
          if (!cancelled) setEvaluation(result);
        }
        if (section === "performance") {
          const result = await request<Performance>("research/performance");
          if (!cancelled) setPerformance(result);
        }
        if (section === "goals") {
          const result = await request<Goal[]>("goals");
          if (!cancelled) setGoals(result);
        }
        if (section === "knowledge") {
          const result = await request<{ retrievalMode: string }>(
            "knowledge/status",
          );
          if (!cancelled) setRetrieval(result.retrievalMode);
        }
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Không tải được dữ liệu");
      } finally {
        if (!cancelled) setBusy(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [section]);
  async function action(run: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await run();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Thao tác thất bại");
    } finally {
      setBusy(false);
    }
  }
  function optimize(event: FormEvent) {
    event.preventDefault();
    void action(async () => {
      const result = await request<Optimization>(
        `research/optimize?tickers=${encodeURIComponent(tickers.toUpperCase().replace(/\s/g, ""))}&lambda=${lambda}`,
      );
      setOptimization(result);
    });
  }
  function saveGoal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const goal = {
      title: values.get("title"),
      targetDate: values.get("targetDate"),
      targetAmount: Number(values.get("targetAmount")),
      allocatedAmount: Number(values.get("allocatedAmount")),
      monthlyContribution: Number(values.get("monthlyContribution")),
      annualRate: Number(values.get("annualRate")),
      version: editing?.version ?? 0,
    };
    void action(async () => {
      await request(
        editing ? `goals/${editing.id}` : "goals",
        editing ? "PUT" : "POST",
        goal,
      );
      setGoals(await request<Goal[]>("goals"));
      setEditing(null);
      form.reset();
      setNotice("Đã lưu mục tiêu.");
    });
  }
  const chart =
    evaluation?.backtest.curves.BUY_HOLD.map((point, i) => ({
      date: point.date,
      BUY_HOLD: point.nav,
      SAA: evaluation.backtest.curves.SAA[i]?.nav,
      TAA: evaluation.backtest.curves.TAA[i]?.nav,
    })) ?? [];
  return (
    <section className="vnx-panel p-4 sm:p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-text-primary">
          Phân tích danh mục từ dữ liệu thực
        </h2>
        <p className="mt-2 text-sm text-text-secondary max-w-3xl">
          Kiểm tra nguồn dự báo, so sánh chiến lược và lập kế hoạch tích lũy.
          Kết quả lịch sử và giả định được trình bày riêng.
        </p>
      </div>
      <nav aria-label="Phân tích danh mục" className="flex flex-wrap gap-4 border-b border-border-subtle">
        {sections.map(([key, label]) => (
          <button
            key={key}
            disabled={busy}
            aria-pressed={section === key}
            onClick={() => setSection(key)}
            className={`px-1 py-3 border-b-2 text-sm focus-visible:outline focus-visible:outline-2 ${section === key ? "border-text-primary text-text-primary font-semibold" : "border-transparent text-text-secondary"}`}
          >
            {label}
          </button>
        ))}
      </nav>
      {busy && (
        <p role="status" className="text-sm text-text-secondary">
          Đang xử lý dữ liệu…
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="text-sm text-text-secondary">
          {notice}
        </p>
      )}
      {section === "optimize" && (
        <div className="space-y-5">
          <form onSubmit={optimize} className="flex flex-wrap items-end gap-4">
            <label className="flex-1 min-w-48 text-sm space-y-2">
              <span>Các mã tài sản, cách nhau bằng dấu phẩy</span>
              <input
                className={inputClass}
                value={tickers}
                onChange={(e) => setTickers(e.target.value)}
                required
                maxLength={120}
              />
            </label>
            <label className="text-sm space-y-2">
              <span>Ngại rủi ro λ (1–10)</span>
              <input
                className={inputClass}
                type="number"
                min="1"
                max="10"
                step="0.5"
                value={lambda}
                onChange={(e) => setLambda(Number(e.target.value))}
                required
              />
            </label>
            <button disabled={busy} className={buttonClass}>
              Tính tỷ trọng
            </button>
          </form>
          <p className="text-sm text-text-secondary">
            Ước lượng lợi suất và hiệp phương sai trên tối đa 252 khoảng giá
            chung. Long-only, tổng tỷ trọng 100%. Kết quả phân tích chưa tự thay
            đổi SAA hay tạo giao dịch.
          </p>
          {optimization && (
            <>
              <p className="text-sm">
                {optimization.observations} khoảng giá · {optimization.from} →{" "}
                {optimization.to}
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <caption className="sr-only">
                    Tỷ trọng tối ưu theo dữ liệu lịch sử
                  </caption>
                  <thead>
                    <tr>
                      <th className="py-2">Tài sản</th>
                      <th>Tỷ trọng</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(optimization.optimal.weights).map(
                      ([ticker, weight]) => (
                        <tr
                          className="border-t border-border-subtle"
                          key={ticker}
                        >
                          <td className="py-2">{ticker}</td>
                          <td>{pct(weight)}</td>
                        </tr>
                      ),
                    )}
                  </tbody>
                </table>
              </div>
              <p className="text-sm">
                Lợi suất trung bình năm:{" "}
                {pct(optimization.optimal.annualReturn)} · Biến động năm:{" "}
                {pct(optimization.optimal.annualVolatility)}
              </p>
              <div
                className="h-64"
                aria-label="Các nghiệm theo mức ngại rủi ro"
              >
                <ResponsiveContainer>
                  <ScatterChart>
                    <XAxis
                      type="number"
                      dataKey="annualVolatility"
                      name="Biến động"
                      tickFormatter={pct}
                    />
                    <YAxis
                      type="number"
                      dataKey="annualReturn"
                      name="Lợi suất"
                      tickFormatter={pct}
                    />
                    <Tooltip formatter={(value: number) => pct(value)} />
                    <Scatter data={optimization.frontier} fill="#2563eb" isAnimationActive={false} />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            </>
          )}
        </div>
      )}
      {section === "models" && models && (
        <div className="space-y-4">
          <p className="text-sm font-semibold">
            TAA:{" "}
            {models.models.taaEnabled
              ? "được bật trong cấu hình"
              : "tắt — giữ SAA; đang kiểm chứng ngoài mẫu"}
          </p>
          <p className="text-sm">
            {models.stockEngine === 'shock-onnx'
              ? 'VNINDEX dùng ensemble shock_shrink chạy ONNX trực tiếp trong backend Java, kỳ hạn 20 phiên. Điểm xu hướng chưa hiệu chỉnh thành xác suất.'
              : models.stockEngine === 'native'
              ? 'VNINDEX dùng ensemble native shock_shrink, horizon 20 phiên. Điểm xu hướng chưa hiệu chỉnh thành xác suất.'
              : `Hợp đồng ONNX: ${models.models.featureVersion} · 12 chỉ báo từ giá đóng cửa.`}
          </p>
          {(models.stockEngine === 'native' || models.stockEngine === 'shock-onnx') && models.nativeStockPrediction && (
            <div className="border-t border-border-subtle py-4 space-y-2">
              <h3 className="font-semibold">Cổ phiếu VNINDEX · ensemble {models.stockEngine === 'shock-onnx' ? 'ONNX' : 'native'}</h3>
              <p className="text-sm">
                {models.nativeStockPrediction.available
                  ? `Ngày ${models.nativeStockPrediction.session} · ${netScoreLabel(models.nativeStockPrediction.netScore)}: ${models.nativeStockPrediction.netScore == null ? 'Chưa có' : Math.abs(models.nativeStockPrediction.netScore).toFixed(3)}`
                  : 'Chưa có dự báo hợp lệ. Giữ tỷ trọng chiến lược; kiểm tra dữ liệu và dịch vụ model.'}
              </p>
              {models.nativeStockPrediction.available && <p className="text-xs text-text-secondary">
                Giảm / đi ngang / tăng: {models.nativeStockPrediction.classScores.map(v => v.toFixed(3)).join(' / ')}. Đây là score quyết định.
              </p>}
            </div>
          )}
          {(
            [
              ["Cổ phiếu VNINDEX", models.stockPrediction, models.models.stock],
              ["Vàng SJC", models.goldPrediction, models.models.gold],
            ] as const
          ).filter(([name]) => !['native', 'shock-onnx'].includes(models.stockEngine ?? '') || name !== 'Cổ phiếu VNINDEX').map(([name, prediction, model]) => (
            <div
              className="border-t border-border-subtle py-4 space-y-2"
              key={name}
            >
              <h3 className="font-semibold">{name}</h3>
              <p className="text-sm break-words">
                {prediction.regimeName.startsWith("UNAVAILABLE")
                  ? "Giữ SAA — chưa có dự báo ML hợp lệ"
                  : `${prediction.regimeName} · Xác suất nhãn: ${pct(prediction.confidence)}`}
              </p>
              <p className="text-xs text-text-secondary break-words">
                {prediction.regimeName} · Model{" "}
                {model.loaded ? "đã nạp" : "chưa nạp"} · Tài sản huấn luyện:{" "}
                {model.metadata?.ticker ?? "không rõ"} · Kết thúc train:{" "}
                {model.metadata?.train_end ?? "không rõ"}
              </p>
            </div>
          ))}
          <p className="text-sm text-text-secondary">
            Model GC quốc tế bị chặn với danh mục SJC/VND. Thiếu dữ liệu, sai
            schema hoặc lỗi suy luận đều không phát sinh tín hiệu chiến thuật.
          </p>
        </div>
      )}
      {section === "evaluation" && evaluation && (
        <div className="space-y-5">
          <p className="text-sm text-text-secondary">
            Đây là báo cáo ONNX lịch sử. Các số liệu trong phần này không phải kết quả đánh giá ensemble native VNINDEX hiện tại.
          </p>
          <p className="text-sm">
            {evaluation.ticker} · Dữ liệu đến {evaluation.dataEnd} · Artifact
            huấn luyện đến {evaluation.artifactTrainEnd}. Mỗi fold loại 20 mẫu
            sát ranh giới để tránh nhãn tương lai chồng lên tập kiểm tra.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <caption className="sr-only">
                Đánh giá walk-forward ngoài mẫu
              </caption>
              <thead>
                <tr>
                  <th className="py-2">Train đến</th>
                  <th>Test từ</th>
                  <th>F1 macro</th>
                  <th>Baseline</th>
                  <th>MCC</th>
                </tr>
              </thead>
              <tbody>
                {evaluation.folds.map((f) => (
                  <tr
                    className="border-t border-border-subtle"
                    key={f.testStart}
                  >
                    <td className="py-2 whitespace-nowrap">{f.trainEnd}</td>
                    <td>{f.testStart}</td>
                    <td>{f.f1Macro.toFixed(3)}</td>
                    <td>{f.majorityBaselineF1.toFixed(3)}</td>
                    <td>{f.mcc.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="h-72" aria-label="Tăng trưởng vốn backtest ngoài mẫu">
            <ResponsiveContainer>
              <LineChart data={chart}>
                <XAxis dataKey="date" minTickGap={70} />
                <YAxis />
                <Tooltip />
                <Legend />
                {["BUY_HOLD", "SAA", "TAA"].map((key, i) => (
                  <Line
                    key={key}
                    dataKey={key}
                    stroke={["#64748b", "#2563eb", "#059669"][i]}
                    dot={false}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <caption className="sr-only">
                Kết quả chiến lược sau chi phí
              </caption>
              <thead>
                <tr>
                  <th className="py-2">Chiến lược</th>
                  <th>Lợi suất</th>
                  <th>Drawdown</th>
                  <th>Turnover</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(evaluation.backtest.metrics).map(
                  ([name, m]) => (
                    <tr key={name} className="border-t border-border-subtle">
                      <td className="py-2">{name}</td>
                      <td>{pct(m.totalReturn)}</td>
                      <td>{pct(m.maxDrawdown)}</td>
                      <td>{m.turnover.toFixed(2)}×</td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
          <p className="text-sm text-text-secondary">
            Mô phỏng cổ phiếu/tiền mặt: SAA 35% cổ phiếu, TAA dịch tối đa 15
            điểm %. Tín hiệu từ giá đóng cửa đầu kỳ áp dụng cho khoảng giá kế
            tiếp. Phí {pct(evaluation.backtest.assumptions.feePerTurnover)} trên
            turnover; tiền mặt lãi 0%; chưa tính trượt giá, thuế hay vàng.
            VNINDEX là chỉ số đại diện, không phải mã đặt lệnh. Đây là kiểm
            chứng nghiên cứu, chưa đồng nhất toàn bộ engine giao dịch thực tế.
          </p>
        </div>
      )}
      {section === "performance" &&
        performance &&
        (performance.available ? (
          <div className="space-y-5">
            <dl className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-4">
              {[
                ["Lợi suất điều chỉnh dòng tiền", pct(performance.totalReturn)],
                ["Lợi suất năm hóa", pct(performance.annualReturn)],
                ["Biến động năm hóa", pct(performance.annualVolatility)],
                ["Sharpe lịch sử", performance.sharpe.toFixed(2)],
                ["Drawdown", pct(performance.maxDrawdown)],
                [
                  "XIRR",
                  performance.xirr == null
                    ? "Không tìm được nghiệm"
                    : pct(performance.xirr),
                ],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-xs text-text-secondary">{label}</dt>
                  <dd className="mt-1 font-semibold tabular-nums">{value}</dd>
                </div>
              ))}
            </dl>
            <div className="h-64">
              <ResponsiveContainer>
                <LineChart data={performance.curve}>
                  <XAxis dataKey="date" minTickGap={60} />
                  <YAxis />
                  <Tooltip />
                  <Line
                    dataKey="growthIndex"
                    name="Chỉ số tăng trưởng"
                    stroke="#2563eb"
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="text-sm text-text-secondary">
              Liên kết Modified Dietz, giả định nạp/rút cuối ngày; không phải
              TWR chính xác trong ngày. Chuẩn hóa theo ngày lịch và năm hóa
              365,25 ngày. Snapshot thưa làm biến động bị làm mượt. Dùng
              snapshot có sẵn, không sinh lịch sử giả để bù dữ liệu.
            </p>
          </div>
        ) : (
          <p className="text-sm text-text-secondary">{performance.reason}</p>
        ))}
      {section === "goals" && (
        <div className="space-y-6">
          <p className="text-sm text-text-secondary">
            Vốn dành riêng do bạn khai báo, chưa tự trích tài sản từ danh mục.
            Mô phỏng góp cuối tháng và lãi suất cố định.
          </p>
          <form
            key={editing?.id ?? "new"}
            onSubmit={saveGoal}
            className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4"
          >
            <label className="text-sm space-y-2">
              <span>Tên mục tiêu</span>
              <input
                name="title"
                defaultValue={editing?.title}
                required
                maxLength={120}
                className={inputClass}
              />
            </label>
            <label className="text-sm space-y-2">
              <span>Số tiền đích (₫)</span>
              <input
                name="targetAmount"
                type="number"
                min="1"
                max="100000000000000"
                defaultValue={editing?.targetAmount}
                required
                className={inputClass}
              />
            </label>
            <label className="text-sm space-y-2">
              <span>Vốn dành riêng hiện tại (₫)</span>
              <input
                name="allocatedAmount"
                type="number"
                min="0"
                max="100000000000000"
                defaultValue={editing?.allocatedAmount ?? 0}
                required
                className={inputClass}
              />
            </label>
            <label className="text-sm space-y-2">
              <span>Góp mỗi tháng (₫)</span>
              <input
                name="monthlyContribution"
                type="number"
                min="0"
                max="100000000000000"
                defaultValue={editing?.monthlyContribution ?? 0}
                required
                className={inputClass}
              />
            </label>
            <label className="text-sm space-y-2">
              <span>Lãi suất giả định (%/năm)</span>
              <input
                name="annualRate"
                type="number"
                min="-50"
                max="50"
                step="0.1"
                defaultValue={editing?.annualRate ?? 0}
                required
                className={inputClass}
              />
            </label>
            <label className="text-sm space-y-2">
              <span>Ngày hoàn thành</span>
              <input
                name="targetDate"
                type="date"
                defaultValue={editing?.targetDate}
                required
                className={inputClass}
              />
            </label>
            <div className="flex gap-2 items-center">
              <button className={buttonClass} disabled={busy}>
                {editing ? "Lưu thay đổi" : "Thêm mục tiêu"}
              </button>
              {editing && (
                <button
                  type="button"
                  onClick={() => setEditing(null)}
                  className="text-sm underline"
                >
                  Hủy sửa
                </button>
              )}
            </div>
          </form>
          {!goals.length && !busy && (
            <p className="text-sm text-text-secondary">
              Chưa có mục tiêu. Thêm số tiền đích và thời hạn để tính mức góp
              cần thiết.
            </p>
          )}
          {goals.map((goal) => (
            <article
              key={goal.id}
              className="border-t border-border-subtle pt-4 space-y-3"
            >
              <div className="flex flex-wrap justify-between gap-3">
                <h3 className="font-semibold break-words">{goal.title}</h3>
                <span className="text-sm text-text-secondary">
                  Đến {goal.targetDate}
                </span>
              </div>
              <p className="text-sm">
                Dự kiến {formatVND(goal.projectedAmount)} / mục tiêu{" "}
                {formatVND(goal.targetAmount)} · Cần góp{" "}
                {formatVND(goal.requiredMonthlyContribution)}/tháng
              </p>
              <p className="text-sm text-text-secondary">
                Còn thiếu theo kịch bản: {formatVND(goal.shortfall)}
              </p>
              <div className="flex gap-5">
                <button
                  disabled={busy}
                  onClick={() => setEditing(goal)}
                  className="text-sm underline"
                >
                  Sửa mục tiêu
                </button>
                <button
                  disabled={busy}
                  onClick={() => {
                    if (window.confirm(`Xóa mục tiêu “${goal.title}”?`))
                      void action(async () => {
                        await request(`goals/${goal.id}`, "DELETE");
                        setGoals(await request<Goal[]>("goals"));
                        if (editing?.id === goal.id) setEditing(null);
                      });
                  }}
                  className="text-sm underline"
                >
                  Xóa
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      {section === "knowledge" && (
        <div className="space-y-6">
          <p className="text-sm text-text-secondary">
            Chế độ truy xuất: {retrieval || "chưa xác định"}. Tài liệu nạp vào
            chỉ được tìm kiếm bởi tài khoản của bạn. Nội dung trùng tên và nguồn
            sẽ được cập nhật.
          </p>
          <form
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              const form = event.currentTarget;
              const values = new FormData(form);
              void action(async () => {
                const chunks = await request<number>(
                  "knowledge/documents",
                  "POST",
                  Object.fromEntries(values),
                );
                setNotice(`Đã lưu ${chunks} đoạn tài liệu.`);
                form.reset();
              });
            }}
          >
            <label className="block text-sm space-y-2">
              <span>Tên tài liệu</span>
              <input
                name="title"
                required
                maxLength={120}
                className={inputClass}
              />
            </label>
            <label className="block text-sm space-y-2">
              <span>Nguồn (tên tài liệu hoặc URL)</span>
              <input
                name="source"
                required
                maxLength={500}
                className={inputClass}
              />
            </label>
            <label className="block text-sm space-y-2">
              <span>Nội dung</span>
              <textarea
                name="content"
                required
                maxLength={40000}
                rows={5}
                className={inputClass}
              />
            </label>
            <button disabled={busy} className={buttonClass}>
              Nạp tài liệu
            </button>
          </form>
          <form
            className="flex flex-wrap gap-3 items-end"
            onSubmit={(event) => {
              event.preventDefault();
              const query = String(
                new FormData(event.currentTarget).get("query"),
              );
              void action(async () => {
                const result = await request<Source[]>(
                  `knowledge/search?query=${encodeURIComponent(query)}`,
                );
                setSources(result);
                if (!result.length)
                  setNotice("Không tìm thấy đoạn phù hợp. Thử từ khóa khác.");
              });
            }}
          >
            <label className="flex-1 min-w-48 text-sm space-y-2">
              <span>Kiểm tra câu hỏi truy xuất</span>
              <input
                name="query"
                required
                maxLength={2000}
                className={inputClass}
              />
            </label>
            <button disabled={busy} className={buttonClass}>
              Tìm nguồn
            </button>
          </form>
          {sources.map((source) => (
            <article
              key={source.id}
              className="border-t border-border-subtle pt-4 space-y-2"
            >
              <h3 className="font-semibold break-words">
                {source.title} · đoạn {source.chunk + 1}
              </h3>
              <p className="text-xs text-text-secondary break-all">
                {source.source} · {source.retrievalMode} · [{source.id}]
              </p>
              <p className="text-sm whitespace-pre-wrap break-words max-w-3xl">
                {source.content}
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

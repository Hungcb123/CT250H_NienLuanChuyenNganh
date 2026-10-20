import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { X, Lock, User, Mail, ShieldCheck, ArrowRight, Sparkles, AlertCircle } from 'lucide-react';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export function AuthModal({ isOpen, onClose, onSuccess }: AuthModalProps) {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  
  // Login form state
  const [loginIdentifier, setLoginIdentifier] = useState('alex_nguyen');
  const [loginPassword, setLoginPassword] = useState('123456');

  // Register form state
  const [regUsername, setRegUsername] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirmPassword, setRegConfirmPassword] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await login({
        usernameOrEmail: loginIdentifier,
        password: loginPassword
      });
      setSuccessMsg('Đăng nhập thành công!');
      setTimeout(() => {
        onSuccess?.();
        onClose();
      }, 500);
    } catch (err: any) {
      setError(err.message || 'Đăng nhập không thành công. Vui lòng kiểm tra lại thông tin.');
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (regPassword !== regConfirmPassword) {
      setError('Mật khẩu xác nhận không khớp');
      return;
    }

    if (regPassword.length < 6) {
      setError('Mật khẩu phải chứa ít nhất 6 ký tự');
      return;
    }

    setLoading(true);
    try {
      await register({
        username: regUsername,
        email: regEmail,
        password: regPassword
      });
      setSuccessMsg('Đăng ký tài khoản thành công! Bạn đã đăng nhập.');
      setTimeout(() => {
        onSuccess?.();
        onClose();
      }, 700);
    } catch (err: any) {
      setError(err.message || 'Đăng ký không thành công');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickDemoLogin = () => {
    setLoginIdentifier('alex_nguyen');
    setLoginPassword('123456');
    setMode('login');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs transition-opacity animate-fade-in">
      <div className="relative w-full max-w-md bg-surface-container-lowest border border-border-subtle rounded-2xl shadow-2xl overflow-hidden">
        {/* Header decoration banner */}
        <div className="bg-gradient-to-r from-accent-emerald/20 via-primary/10 to-transparent p-6 pb-4 border-b border-border-subtle relative">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-1 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-container transition-colors"
          >
            <X className="w-5 h-5" />
          </button>

          <div className="flex items-center gap-2 mb-2">
            <div className="p-2 rounded-xl bg-accent-emerald text-white shadow-sm">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-text-primary">VNxCapital</h3>
              <p className="text-xs text-text-muted">Cổng xác thực danh tính & Quản trị tài sản cá nhân</p>
            </div>
          </div>

          {/* Mode Switch Tabs */}
          <div className="flex gap-2 mt-4 bg-surface-container/60 p-1 rounded-xl border border-border-subtle">
            <button
              type="button"
              onClick={() => { setMode('login'); setError(null); }}
              className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all ${
                mode === 'login'
                  ? 'bg-surface-container-lowest text-text-primary shadow-xs'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              Đăng nhập
            </button>
            <button
              type="button"
              onClick={() => { setMode('register'); setError(null); }}
              className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all ${
                mode === 'register'
                  ? 'bg-surface-container-lowest text-text-primary shadow-xs'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              Đăng ký tài khoản
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-xl bg-accent-rose-light/40 border border-accent-rose/30 text-accent-rose text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-3 rounded-xl bg-accent-emerald-light/40 border border-accent-emerald/30 text-accent-emerald text-xs flex items-start gap-2">
              <ShieldCheck className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {mode === 'login' ? (
            <form onSubmit={handleLoginSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-text-secondary mb-1">
                  Tên đăng nhập hoặc Email
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-text-muted absolute left-3 top-3" />
                  <input
                    type="text"
                    required
                    value={loginIdentifier}
                    onChange={(e) => setLoginIdentifier(e.target.value)}
                    placeholder="alex_nguyen hoặc email..."
                    className="w-full pl-9 pr-3 py-2 text-xs rounded-xl bg-surface-container border border-border-subtle text-text-primary focus:outline-hidden focus:border-accent-emerald transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-text-secondary mb-1">
                  Mật khẩu
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-text-muted absolute left-3 top-3" />
                  <input
                    type="password"
                    required
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full pl-9 pr-3 py-2 text-xs rounded-xl bg-surface-container border border-border-subtle text-text-primary focus:outline-hidden focus:border-accent-emerald transition-colors"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 rounded-xl bg-accent-emerald hover:bg-emerald-600 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-sm transition-all disabled:opacity-50"
              >
                {loading ? 'Đang xác thực...' : 'Đăng nhập vào Hệ thống'}
                <ArrowRight className="w-4 h-4" />
              </button>

              {/* Quick Demo Fill button */}
              <div className="pt-2 border-t border-border-subtle">
                <button
                  type="button"
                  onClick={handleQuickDemoLogin}
                  className="w-full py-2 px-3 rounded-xl border border-dashed border-accent-emerald/40 text-accent-emerald hover:bg-accent-emerald-light/30 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  Điền tài khoản Demo chuẩn SRS (alex_nguyen / 123456)
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={handleRegisterSubmit} className="space-y-3.5">
              <div>
                <label className="block text-xs font-bold text-text-secondary mb-1">
                  Tên đăng nhập (Username)
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-text-muted absolute left-3 top-3" />
                  <input
                    type="text"
                    required
                    value={regUsername}
                    onChange={(e) => setRegUsername(e.target.value)}
                    placeholder="Ví dụ: investor_vietnam"
                    className="w-full pl-9 pr-3 py-2 text-xs rounded-xl bg-surface-container border border-border-subtle text-text-primary focus:outline-hidden focus:border-accent-emerald transition-colors"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-text-secondary mb-1">
                  Địa chỉ Email
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-text-muted absolute left-3 top-3" />
                  <input
                    type="email"
                    required
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    placeholder="name@example.com"
                    className="w-full pl-9 pr-3 py-2 text-xs rounded-xl bg-surface-container border border-border-subtle text-text-primary focus:outline-hidden focus:border-accent-emerald transition-colors"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-bold text-text-secondary mb-1">
                    Mật khẩu
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-text-muted absolute left-3 top-3" />
                    <input
                      type="password"
                      required
                      value={regPassword}
                      onChange={(e) => setRegPassword(e.target.value)}
                      placeholder="Ít nhất 6 ký tự"
                      className="w-full pl-9 pr-3 py-2 text-xs rounded-xl bg-surface-container border border-border-subtle text-text-primary focus:outline-hidden focus:border-accent-emerald transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-text-secondary mb-1">
                    Xác nhận
                  </label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-text-muted absolute left-3 top-3" />
                    <input
                      type="password"
                      required
                      value={regConfirmPassword}
                      onChange={(e) => setRegConfirmPassword(e.target.value)}
                      placeholder="Nhập lại mật khẩu"
                      className="w-full pl-9 pr-3 py-2 text-xs rounded-xl bg-surface-container border border-border-subtle text-text-primary focus:outline-hidden focus:border-accent-emerald transition-colors"
                    />
                  </div>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 rounded-xl bg-accent-emerald hover:bg-emerald-600 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-sm transition-all disabled:opacity-50 mt-2"
              >
                {loading ? 'Đang đăng ký...' : 'Tạo Tài Khoản & Bắt Đầu'}
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

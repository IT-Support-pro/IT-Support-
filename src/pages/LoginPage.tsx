import React, { useState } from 'react';
import { Lock, User, AlertCircle, ArrowRight, ShieldCheck, Terminal, Server } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getBaseApiUrl, setCustomApiUrl } from '../api';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showConfig, setShowConfig] = useState(false);
  const [gatewayUrl, setGatewayUrl] = useState(getBaseApiUrl());

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setIsLoading(true);

    try {
      await login(username, password);
    } catch (err: any) {
      setErrorMsg(err.message || 'Login failed. Please check credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveGateway = (e: React.FormEvent) => {
    e.preventDefault();
    setCustomApiUrl(gatewayUrl);
    setShowConfig(false);
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center px-4 py-12 relative overflow-hidden selection:bg-cyan-500 selection:text-black">
      {/* Background glow */}
      <div className="absolute w-[500px] h-[500px] bg-cyan-500/5 rounded-full blur-3xl pointer-events-none -top-32 -left-32"></div>
      <div className="absolute w-[500px] h-[500px] bg-blue-600/5 rounded-full blur-3xl pointer-events-none -bottom-32 -right-32"></div>

      <div className="max-w-md w-full space-y-6 relative z-10">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex w-14 h-14 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 items-center justify-center shadow-xl shadow-cyan-500/20 text-white font-black text-2xl">
            HBK
          </div>
          <h2 className="text-2xl font-black text-white tracking-tight">HBK IT Monitoring System</h2>
          <p className="text-xs text-slate-400">
            Retail Hypermarket Control Hub • 50+ Windows POS Terminals
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl space-y-5">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <span className="text-xs font-bold text-slate-200 flex items-center gap-2">
              <Lock className="w-3.5 h-3.5 text-cyan-400" />
              IT Staff Authentication
            </span>
            <span className="text-[10px] font-mono text-slate-500 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
              JWT HS256
            </span>
          </div>

          {errorMsg && (
            <div className="p-3.5 rounded-xl bg-rose-950/60 border border-rose-800/80 text-rose-300 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div className="leading-relaxed">
                {errorMsg}
                {errorMsg.toLowerCase().includes('connect') && (
                  <div className="mt-2">
                    <button
                      type="button"
                      onClick={() => setShowConfig(true)}
                      className="underline font-semibold hover:text-white"
                    >
                      Change Gateway Target URL
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-[11px] font-medium text-slate-300 block mb-1">Username</label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="admin"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
                />
              </div>
            </div>

            <div>
              <label className="text-[11px] font-medium text-slate-300 block mb-1">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
                />
              </div>
              <p className="text-[10px] text-slate-500 mt-1">
                Account locks for 5 minutes after 5 consecutive failed attempts.
              </p>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-bold text-xs rounded-xl flex items-center justify-center gap-2 transition shadow-lg shadow-cyan-500/20 disabled:opacity-50"
            >
              {isLoading ? (
                <span>Authenticating...</span>
              ) : (
                <>
                  <span>Sign In to Dashboard</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </form>

          {/* Quick Info & Gateway Link */}
          <div className="pt-3 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-500">
            <div className="flex items-center gap-1.5">
              <Server className="w-3.5 h-3.5 text-slate-400" />
              <span>Target: <code className="text-slate-400">{getBaseApiUrl()}</code></span>
            </div>
            <button
              type="button"
              onClick={() => setShowConfig(!showConfig)}
              className="text-cyan-400 hover:underline"
            >
              Configure
            </button>
          </div>

          {showConfig && (
            <form onSubmit={handleSaveGateway} className="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-2">
              <label className="text-[10px] text-slate-400 block font-medium">Gateway Address (VITE_API_URL):</label>
              <input
                type="text"
                value={gatewayUrl}
                onChange={(e) => setGatewayUrl(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1 text-xs font-mono text-cyan-300 focus:outline-none"
              />
              <div className="flex justify-end gap-2">
                <button
                  type="submit"
                  className="px-2.5 py-1 bg-cyan-600 hover:bg-cyan-500 text-slate-950 text-[11px] font-bold rounded"
                >
                  Save Target
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Security Notice */}
        <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 text-[11px] text-slate-400 space-y-1">
          <div className="font-semibold text-slate-300 flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            Seed Admin Credentials Hint:
          </div>
          <p className="text-slate-400">
            Initial administrator credentials are generated when running <code className="text-cyan-300 bg-slate-950 px-1 py-0.5 rounded">python scripts/seed.py</code> in the gateway folder.
          </p>
        </div>
      </div>
    </div>
  );
};

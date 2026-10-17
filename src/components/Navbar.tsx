import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  Monitor, 
  Bell, 
  Store, 
  Users, 
  PlusCircle, 
  LogOut, 
  Settings, 
  RefreshCw, 
  ShieldCheck, 
  CheckCircle2, 
  AlertCircle,
  FileText
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getBaseApiUrl, setCustomApiUrl, api } from '../api';

interface NavbarProps {
  activePage: string;
  setActivePage: (page: string) => void;
  firingAlertsCount: number;
  autoRefresh: boolean;
  setAutoRefresh: (val: boolean) => void;
  onRefresh: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activePage,
  setActivePage,
  firingAlertsCount,
  autoRefresh,
  setAutoRefresh,
  onRefresh
}) => {
  const { user, role, logout } = useAuth();
  const [showConfigModal, setShowConfigModal] = useState<boolean>(false);
  const [gatewayUrlInput, setGatewayUrlInput] = useState<string>(getBaseApiUrl());
  const [gatewayStatus, setGatewayStatus] = useState<'ok' | 'err' | 'checking'>('checking');

  // Configurable silent refresh intervals (Section H.7)
  const [statusIntervalSec, setStatusIntervalSec] = useState<number>(() => {
    const val = localStorage.getItem('hbk_status_refresh_sec');
    return val ? parseInt(val, 10) : 30;
  });
  const [fullIntervalMin, setFullIntervalMin] = useState<number>(() => {
    const val = localStorage.getItem('hbk_full_refresh_min');
    return val ? parseInt(val, 10) : 15;
  });

  const checkConnection = async () => {
    setGatewayStatus('checking');
    try {
      await api.checkHealth();
      setGatewayStatus('ok');
    } catch {
      setGatewayStatus('err');
    }
  };

  useEffect(() => {
    checkConnection();
  }, []);

  const handleSaveGateway = (e: React.FormEvent) => {
    e.preventDefault();
    setCustomApiUrl(gatewayUrlInput);
    localStorage.setItem('hbk_status_refresh_sec', String(statusIntervalSec));
    localStorage.setItem('hbk_full_refresh_min', String(fullIntervalMin));
    setShowConfigModal(false);
    checkConnection();
    onRefresh();
  };

  return (
    <>
      <header className="border-b border-slate-800 bg-slate-900/95 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="h-16 flex items-center justify-between gap-4">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 text-white font-black text-lg">
                HBK
              </div>
              <div className="hidden sm:block">
                <div className="flex items-center gap-2">
                  <h1 className="font-bold text-base tracking-tight text-white">HBK IT Monitoring</h1>
                  <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-cyan-950 text-cyan-400 border border-cyan-800">
                    Live
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">Retail Hypermarket Control Hub</p>
              </div>
            </div>

            {/* Nav Links */}
            <nav className="flex items-center gap-1 overflow-x-auto py-1 text-xs font-semibold">
              <button
                onClick={() => setActivePage('overview')}
                className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition shrink-0 ${
                  activePage === 'overview'
                    ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                    : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                <Activity className="w-3.5 h-3.5" />
                Overview
              </button>

              <button
                onClick={() => setActivePage('devices')}
                className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition shrink-0 ${
                  activePage === 'devices'
                    ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                    : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                <Monitor className="w-3.5 h-3.5" />
                Devices
              </button>

              <button
                onClick={() => setActivePage('alerts')}
                className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition shrink-0 relative ${
                  activePage === 'alerts'
                    ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                    : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                <Bell className="w-3.5 h-3.5" />
                Alerts
                {firingAlertsCount > 0 && (
                  <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                    activePage === 'alerts' ? 'bg-slate-950 text-rose-400' : 'bg-rose-600 text-white animate-pulse'
                  }`}>
                    {firingAlertsCount}
                  </span>
                )}
              </button>

              <button
                onClick={() => setActivePage('stores')}
                className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition shrink-0 ${
                  activePage === 'stores'
                    ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                    : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                <Store className="w-3.5 h-3.5" />
                Stores
              </button>

              <button
                onClick={() => setActivePage('fbr')}
                className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition shrink-0 ${
                  activePage === 'fbr'
                    ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                    : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                FBR Hub
              </button>

              <button
                onClick={() => setActivePage('invoices')}
                className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition shrink-0 ${
                  activePage === 'invoices'
                    ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                    : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                Invoices
              </button>

              {role === 'admin' && (
                <button
                  onClick={() => setActivePage('users')}
                  className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition shrink-0 ${
                    activePage === 'users'
                      ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/20'
                      : 'text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <Users className="w-3.5 h-3.5" />
                  Users
                </button>
              )}

              {role === 'admin' && (
                <button
                  onClick={() => setActivePage('add-device')}
                  className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition shrink-0 ${
                    activePage === 'add-device'
                      ? 'bg-emerald-600 text-slate-950 shadow-md shadow-emerald-600/20 font-bold'
                      : 'text-emerald-400 hover:bg-emerald-950/40 border border-emerald-900/40'
                  }`}
                >
                  <PlusCircle className="w-3.5 h-3.5" />
                  Add Device
                </button>
              )}
            </nav>

            {/* Right Tools: Connection, Auto-refresh, User Profile */}
            <div className="flex items-center gap-3">
              {/* Gateway Connection Indicator */}
              <button
                onClick={() => setShowConfigModal(true)}
                title={`Target: ${getBaseApiUrl()}`}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-400 hover:text-white transition"
              >
                <span className={`w-2 h-2 rounded-full ${
                  gatewayStatus === 'ok' ? 'bg-emerald-400 animate-pulse' :
                  gatewayStatus === 'err' ? 'bg-rose-500' : 'bg-amber-400'
                }`}></span>
                <span className="hidden md:inline font-mono truncate max-w-[130px]">
                  {getBaseApiUrl().replace(/^https?:\/\//, '')}
                </span>
                <Settings className="w-3 h-3 text-slate-500 ml-0.5" />
              </button>

              {/* Refresh Control */}
              <div className="flex items-center gap-1 bg-slate-950 px-2 py-1 rounded-lg border border-slate-800 text-[11px]">
                <button
                  onClick={onRefresh}
                  title="Refresh now"
                  className="text-slate-400 hover:text-cyan-400 transition"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setAutoRefresh(!autoRefresh)}
                  className={`px-1 rounded font-mono text-[10px] ${
                    autoRefresh ? 'text-emerald-400 font-bold' : 'text-slate-500'
                  }`}
                >
                  {autoRefresh ? '10s' : 'OFF'}
                </button>
              </div>

              {/* User Profile & Role */}
              <div className="flex items-center gap-2 pl-1 border-l border-slate-800">
                <div className="text-right hidden lg:block">
                  <div className="text-xs font-semibold text-white leading-tight">{user?.username}</div>
                  <div className="text-[10px] font-mono text-cyan-400 uppercase tracking-wider">{role}</div>
                </div>

                <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-800 text-cyan-300 border border-slate-700 lg:hidden">
                  {role}
                </span>

                <button
                  onClick={logout}
                  title="Logout"
                  className="p-1.5 rounded-lg hover:bg-rose-950/60 hover:text-rose-400 text-slate-400 transition"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Gateway Connection Switcher Modal */}
      {showConfigModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Settings className="w-4 h-4 text-cyan-400" />
                Gateway Target URL
              </h3>
              <button
                onClick={() => setShowConfigModal(false)}
                className="text-slate-400 hover:text-white text-xs"
              >
                Close
              </button>
            </div>

            <p className="text-xs text-slate-400">
              The dashboard calls this URL directly. If your FastAPI gateway runs on a different port or IP address (e.g. during local testing), update it here.
            </p>

            <form onSubmit={handleSaveGateway} className="space-y-3">
              <div>
                <label className="text-[11px] font-medium text-slate-300 block mb-1">Gateway URL:</label>
                <input
                  type="text"
                  value={gatewayUrlInput}
                  onChange={(e) => setGatewayUrlInput(e.target.value)}
                  placeholder="http://localhost:8000"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3 pt-1">
                <div>
                  <label className="text-[11px] font-medium text-slate-300 block mb-1">
                    Status/FBR Refresh (s):
                  </label>
                  <input
                    type="number"
                    min="5"
                    max="300"
                    value={statusIntervalSec}
                    onChange={(e) => setStatusIntervalSec(Math.max(5, parseInt(e.target.value, 10) || 30))}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
                  />
                  <span className="text-[10px] text-slate-500">Default: 30s</span>
                </div>

                <div>
                  <label className="text-[11px] font-medium text-slate-300 block mb-1">
                    Charts/Full Refresh (m):
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="60"
                    value={fullIntervalMin}
                    onChange={(e) => setFullIntervalMin(Math.max(1, parseInt(e.target.value, 10) || 15))}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
                  />
                  <span className="text-[10px] text-slate-500">Default: 15m</span>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setGatewayUrlInput('http://localhost:8000');
                    setCustomApiUrl('');
                    setShowConfigModal(false);
                    checkConnection();
                    onRefresh();
                  }}
                  className="text-slate-400 hover:text-slate-200 text-xs"
                >
                  Reset Default
                </button>

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setShowConfigModal(false)}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-750 text-xs"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 text-xs font-bold"
                  >
                    Save & Reconnect
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
};

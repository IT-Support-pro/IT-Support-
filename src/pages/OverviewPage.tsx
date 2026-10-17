import React, { useEffect, useState, useRef } from 'react';
import { 
  Activity, 
  MonitorCheck, 
  WifiOff, 
  AlertTriangle, 
  Store, 
  ArrowRight, 
  Check, 
  ShieldAlert, 
  RefreshCw,
  ShieldCheck,
  Pause
} from 'lucide-react';
import { OverviewCounts, Alert, Device } from '../types';
import { api } from '../api';
import { formatPktTime, formatPktDateTime, formatUtcTooltip, formatRelativeMinutesAgo } from '../utils/time';

interface OverviewPageProps {
  onNavigateToDevice: (deviceId: string) => void;
  onNavigateToAlerts: () => void;
  onNavigateToDevices: () => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  onNavigateToDevice,
  onNavigateToAlerts,
  onNavigateToDevices
}) => {
  const [counts, setCounts] = useState<OverviewCounts | null>(null);
  const [recentAlerts, setRecentAlerts] = useState<Alert[]>([]);
  const [unhealthyDevices, setUnhealthyDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [updatedText, setUpdatedText] = useState<string>('Updated just now');
  const isFetchingRef = useRef<boolean>(false);

  // Silent background fetch: does not show spinner if counts are already present
  const fetchData = async (isSilent: boolean = false) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;

    try {
      if (!isSilent) setLoading(true);
      setError(null);

      const [overviewData, alertsData, devicesData] = await Promise.all([
        api.getOverview(),
        api.getAlerts({ state: 'FIRING' }),
        api.getDevices({ limit: 100 })
      ]);

      setCounts(overviewData);
      setRecentAlerts(alertsData.slice(0, 6));

      // Flagged: offline, degraded, FBR down, or with active firing alerts
      const flagged = devicesData.filter(d => 
        d.status === 'OFFLINE' || 
        d.status === 'DEGRADED' || 
        d.fbr_status === 'DOWN' || 
        (d.active_alerts_count != null && d.active_alerts_count > 0)
      );
      setUnhealthyDevices(flagged);
      setLastUpdated(new Date());
      setUpdatedText('Updated just now');
    } catch (err: any) {
      if (!isSilent) {
        setError(err.message || 'Failed to fetch overview data.');
      }
    } finally {
      if (!isSilent) setLoading(false);
      isFetchingRef.current = false;
    }
  };

  // Initial load
  useEffect(() => {
    fetchData(false);
  }, []);

  // Silent periodic background refresh (default 30s) that pauses when tab is hidden
  useEffect(() => {
    const rawInterval = localStorage.getItem('hbk_status_refresh_sec');
    const intervalSec = rawInterval ? Math.max(5, parseInt(rawInterval, 10)) : 30;

    const timer = setInterval(() => {
      if (document.hidden) return; // Pause while browser tab is hidden
      fetchData(true);
    }, intervalSec * 1000);

    return () => clearInterval(timer);
  }, []);

  // Update "Updated X min ago" tick
  useEffect(() => {
    const textTimer = setInterval(() => {
      setUpdatedText(`Updated ${formatRelativeMinutesAgo(lastUpdated)}`);
    }, 15000);
    return () => clearInterval(textTimer);
  }, [lastUpdated]);

  if (loading && !counts) {
    return (
      <div className="flex flex-col items-center justify-center h-80 space-y-3">
        <RefreshCw className="w-6 h-6 text-cyan-400 animate-spin" />
        <span className="text-xs text-slate-400">Loading hypermarket overview metrics...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Title & Status */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Activity className="w-5 h-5 text-cyan-400" />
            Infrastructure Health Overview
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time telemetry, FBR fiscal integration, and availability monitoring across all hypermarket stores.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span 
            className="text-[11px] font-mono text-slate-400 bg-slate-900 px-3 py-1 rounded-lg border border-slate-800"
            title={formatUtcTooltip(counts?.generated_at)}
          >
            {counts?.generated_at ? `Evaluated: ${formatPktTime(counts.generated_at)}` : ''} • <span className="text-cyan-400">{updatedText}</span>
          </span>

          <button
            onClick={() => fetchData(true)}
            className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition"
            title="Refresh overview silently"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-300 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => fetchData(false)} className="px-3 py-1 bg-rose-900 hover:bg-rose-800 text-white rounded font-semibold text-xs">
            Retry
          </button>
        </div>
      )}

      {/* Overview Stat Cards - 6 Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {/* Total Terminals */}
        <div 
          onClick={onNavigateToDevices}
          className="bg-slate-900 border border-slate-800 rounded-xl p-4 cursor-pointer hover:border-slate-700 transition space-y-2"
        >
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Terminals</span>
            <MonitorCheck className="w-4 h-4 text-slate-400" />
          </div>
          <div className="text-2xl font-black text-white">{counts?.devices_total ?? 0}</div>
          <div className="text-[10px] text-slate-500 font-medium">Windows POS & PC</div>
        </div>

        {/* Online Devices */}
        <div 
          onClick={onNavigateToDevices}
          className="bg-slate-900 border border-emerald-900/40 rounded-xl p-4 cursor-pointer hover:border-emerald-700 transition space-y-2 relative overflow-hidden"
        >
          <div className="flex items-center justify-between text-emerald-400 text-xs font-semibold">
            <span>Online</span>
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          </div>
          <div className="text-2xl font-black text-emerald-300">{counts?.online ?? 0}</div>
          <div className="text-[10px] text-slate-500">Telemetry active</div>
        </div>

        {/* Offline Devices */}
        <div 
          onClick={onNavigateToDevices}
          className={`border rounded-xl p-4 cursor-pointer transition space-y-2 ${
            (counts?.offline ?? 0) > 0 
              ? 'bg-rose-950/20 border-rose-900/60 hover:border-rose-700 text-rose-300' 
              : 'bg-slate-900 border-slate-800 hover:border-slate-700 text-slate-300'
          }`}
        >
          <div className="flex items-center justify-between text-xs font-semibold">
            <span>Offline</span>
            <WifiOff className="w-4 h-4 text-rose-400" />
          </div>
          <div className="text-2xl font-black text-rose-400">{counts?.offline ?? 0}</div>
          <div className="text-[10px] text-slate-500">&gt; 90s heartbeat silence</div>
        </div>

        {/* Paused Terminals */}
        <div 
          onClick={onNavigateToDevices}
          className="bg-slate-900 border border-amber-900/40 rounded-xl p-4 cursor-pointer hover:border-amber-700 transition space-y-2"
        >
          <div className="flex items-center justify-between text-amber-400 text-xs font-semibold">
            <span>Paused</span>
            <Pause className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-black text-amber-300">{counts?.paused ?? 0}</div>
          <div className="text-[10px] text-slate-500">Telemetry suspended</div>
        </div>

        {/* FBR Down Counter */}
        <div 
          onClick={onNavigateToDevices}
          className={`border rounded-xl p-4 cursor-pointer transition space-y-2 ${
            (counts?.fbr_down ?? 0) > 0 
              ? 'bg-rose-950/30 border-rose-800 hover:border-rose-600 text-rose-300' 
              : 'bg-slate-900 border-slate-800 hover:border-slate-700 text-slate-300'
          }`}
        >
          <div className="flex items-center justify-between text-xs font-semibold">
            <span>FBR Down</span>
            <ShieldCheck className={`w-4 h-4 ${(counts?.fbr_down ?? 0) > 0 ? 'text-rose-400 animate-pulse' : 'text-slate-400'}`} />
          </div>
          <div className={`text-2xl font-black ${(counts?.fbr_down ?? 0) > 0 ? 'text-rose-400' : 'text-white'}`}>
            {counts?.fbr_down ?? 0}
          </div>
          <div className="text-[10px] text-slate-500">Fiscal portal failures</div>
        </div>

        {/* Active Alerts */}
        <div 
          onClick={onNavigateToAlerts}
          className={`border rounded-xl p-4 cursor-pointer transition space-y-2 ${
            (counts?.firing_alerts ?? 0) > 0 
              ? 'bg-amber-950/20 border-amber-900/60 hover:border-amber-700 text-amber-300' 
              : 'bg-slate-900 border-slate-800 hover:border-slate-700 text-slate-300'
          }`}
        >
          <div className="flex items-center justify-between text-xs font-semibold">
            <span>Active Alerts</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-black text-amber-400">{counts?.firing_alerts ?? 0}</div>
          <div className="text-[10px] text-slate-500">
            {counts?.critical_alerts ?? 0} Crit • {counts?.warning_alerts ?? 0} Warn
          </div>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* Left Column: Devices Requiring Immediate Attention */}
        <div className="lg:col-span-7 space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
            <div className="px-5 py-3.5 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-cyan-400" />
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                  Attention Required ({unhealthyDevices.length})
                </h3>
              </div>
              <button 
                onClick={onNavigateToDevices}
                className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-semibold"
              >
                View all devices <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            <div className="divide-y divide-slate-850">
              {unhealthyDevices.map((dev) => (
                <div 
                  key={dev.id} 
                  onClick={() => onNavigateToDevice(dev.device_id)}
                  className="p-4 hover:bg-slate-850/50 cursor-pointer transition flex items-center justify-between gap-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-white">{dev.device_id}</span>
                      <span className="text-xs text-slate-400">({dev.computer_name})</span>
                      <span className="text-[10px] text-slate-500 bg-slate-950 px-1.5 py-0.5 rounded border border-slate-800 font-mono">
                        {dev.store_code}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400">
                      IP: <code className="text-slate-300 font-mono">{dev.ip_address}</code> • Type: {dev.device_type} • Last seen:{' '}
                      <span title={formatUtcTooltip(dev.last_seen)} className="text-slate-300 font-mono">
                        {formatPktTime(dev.last_seen)}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {/* FBR Down Indicator Badge */}
                    {dev.fbr_status === 'DOWN' && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-950 text-rose-400 border border-rose-800 animate-pulse">
                        FBR Down
                      </span>
                    )}

                    {/* Terminal Status Badge */}
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                      dev.status === 'OFFLINE' ? 'bg-rose-950 text-rose-400 border border-rose-800' :
                      dev.status === 'PAUSED' ? 'bg-amber-950 text-amber-400 border border-amber-800' :
                      dev.status === 'DEGRADED' ? 'bg-amber-950 text-amber-400 border border-amber-800' :
                      'bg-emerald-950 text-emerald-400 border border-emerald-800'
                    }`}>
                      {dev.status}
                    </span>

                    <ArrowRight className="w-4 h-4 text-slate-600" />
                  </div>
                </div>
              ))}

              {unhealthyDevices.length === 0 && (
                <div className="p-8 text-center text-xs text-slate-500">
                  <Check className="w-6 h-6 text-emerald-400 mx-auto mb-2" />
                  All monitored POS terminals and devices are online, synced, and healthy.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Recent Firing Alerts */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg flex flex-col">
            <div className="px-5 py-3.5 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                  Active Alerts ({recentAlerts.length})
                </h3>
              </div>
              <button 
                onClick={onNavigateToAlerts}
                className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1 font-semibold"
              >
                Alerts hub <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            <div className="divide-y divide-slate-850 flex-1">
              {recentAlerts.map((alert) => (
                <div key={alert.id} className="p-4 space-y-2 hover:bg-slate-850/40 transition">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.2 rounded text-[10px] font-bold uppercase ${
                        alert.severity === 'critical' ? 'bg-rose-950 text-rose-400 border border-rose-800' : 'bg-amber-950 text-amber-400 border border-amber-800'
                      }`}>
                        {alert.severity}
                      </span>
                      <span 
                        onClick={() => alert.device_id && onNavigateToDevice(alert.device_id)}
                        className="font-mono text-xs font-bold text-cyan-300 hover:underline cursor-pointer"
                      >
                        {alert.device_id || 'Device'}
                      </span>
                    </div>
                    <span 
                      className="text-[10px] font-mono text-slate-400"
                      title={formatUtcTooltip(alert.fired_at)}
                    >
                      {formatPktTime(alert.fired_at)}
                    </span>
                  </div>

                  <p className="text-xs text-slate-200">{alert.message}</p>
                </div>
              ))}

              {recentAlerts.length === 0 && (
                <div className="p-8 text-center text-xs text-slate-500">
                  No active firing alerts.
                </div>
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

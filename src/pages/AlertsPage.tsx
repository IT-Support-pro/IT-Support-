import React, { useState, useEffect } from 'react';
import { 
  Bell, 
  AlertTriangle, 
  CheckCircle2, 
  RefreshCw, 
  Filter, 
  Check, 
  Clock, 
  ArrowRight,
  ShieldAlert,
  Search
} from 'lucide-react';
import { Alert, Store } from '../types';
import { api } from '../api';
import { useAuth } from '../context/AuthContext';
import { formatPktDateTime, formatUtcTooltip } from '../utils/time';

interface AlertsPageProps {
  onNavigateToDevice: (deviceId: string) => void;
}

export const AlertsPage: React.FC<AlertsPageProps> = ({ onNavigateToDevice }) => {
  const { role } = useAuth();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Filters
  const [stateFilter, setStateFilter] = useState<string>('FIRING');
  const [severityFilter, setSeverityFilter] = useState<string>('');
  const [storeFilter, setStoreFilter] = useState<string>('');
  const [deviceSearch, setDeviceSearch] = useState<string>('');

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      setError(null);
      const [alertsData, storesData] = await Promise.all([
        api.getAlerts({
          state: stateFilter === 'ALL' ? undefined : stateFilter,
          severity: severityFilter || undefined,
          store: storeFilter || undefined,
          device: deviceSearch || undefined
        }),
        api.getStores()
      ]);
      setAlerts(alertsData);
      setStores(storesData);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch alerts.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [stateFilter, severityFilter, storeFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchAlerts();
  };

  const handleAck = async (alertId: number) => {
    try {
      await api.ackAlert(alertId);
      setSuccessMsg(`Alert #${alertId} acknowledged.`);
      setTimeout(() => setSuccessMsg(null), 3000);
      fetchAlerts();
    } catch (err: any) {
      setError(err.message || 'Failed to acknowledge alert.');
    }
  };

  const handleResolve = async (alertId: number) => {
    try {
      await api.resolveAlert(alertId);
      setSuccessMsg(`Alert #${alertId} marked as resolved.`);
      setTimeout(() => setSuccessMsg(null), 3000);
      fetchAlerts();
    } catch (err: any) {
      setError(err.message || 'Failed to resolve alert.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Bell className="w-5 h-5 text-amber-400" />
            Alerts & Incident Management
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Rule-based evaluations: high CPU, low disk space, offline printers, agent disconnects.
          </p>
        </div>

        <button
          onClick={fetchAlerts}
          className="self-start sm:self-auto px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white text-xs flex items-center gap-1.5 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          Refresh
        </button>
      </div>

      {successMsg && (
        <div className="p-3 bg-emerald-950/60 border border-emerald-800 text-emerald-300 text-xs rounded-xl flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          {successMsg}
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-300 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button onClick={fetchAlerts} className="px-3 py-1 bg-rose-900 text-white rounded font-bold text-xs">
            Retry
          </button>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {/* State */}
          <div>
            <label className="text-[10px] text-slate-400 block font-medium mb-1">Alert State</label>
            <select
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="FIRING">FIRING (Active)</option>
              <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
              <option value="RESOLVED">RESOLVED</option>
              <option value="ALL">ALL STATES</option>
            </select>
          </div>

          {/* Severity */}
          <div>
            <label className="text-[10px] text-slate-400 block font-medium mb-1">Severity</label>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="">All Severities</option>
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
            </select>
          </div>

          {/* Store */}
          <div>
            <label className="text-[10px] text-slate-400 block font-medium mb-1">Store</label>
            <select
              value={storeFilter}
              onChange={(e) => setStoreFilter(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="">All Stores</option>
              {stores.map((s) => (
                <option key={s.id} value={s.code}>
                  {s.code} - {s.name}
                </option>
              ))}
            </select>
          </div>

          {/* Device Search */}
          <div className="lg:col-span-2">
            <label className="text-[10px] text-slate-400 block font-medium mb-1">Device ID Search</label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="POS-12, POS-01..."
                value={deviceSearch}
                onChange={(e) => setDeviceSearch(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-cyan-500"
              />
              <button
                type="submit"
                className="px-3 py-2 bg-cyan-600 hover:bg-cyan-500 text-slate-950 rounded-lg text-xs font-bold shrink-0"
              >
                Search
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Alerts Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950/70 text-slate-400 uppercase text-[10px] tracking-wider font-semibold">
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Device</th>
                <th className="py-3 px-4">Store</th>
                <th className="py-3 px-4">Rule / Condition</th>
                <th className="py-3 px-4">Message</th>
                <th className="py-3 px-4">State</th>
                <th className="py-3 px-4">Fired At</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {alerts.map((alert) => {
                const isCrit = alert.severity === 'critical';
                const isFiring = alert.state === 'FIRING';
                const isAcked = alert.state === 'ACKNOWLEDGED';
                const isResolved = alert.state === 'RESOLVED';

                return (
                  <tr key={alert.id} className="hover:bg-slate-850/60 transition">
                    <td className="py-3.5 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                        isCrit ? 'bg-rose-950 text-rose-400 border border-rose-800' : 'bg-amber-950 text-amber-400 border border-amber-800'
                      }`}>
                        {alert.severity}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 font-mono font-bold">
                      {alert.device_id ? (
                        <button
                          onClick={() => onNavigateToDevice(alert.device_id!)}
                          className="text-cyan-400 hover:underline flex items-center gap-1"
                        >
                          {alert.device_id}
                          <ArrowRight className="w-3 h-3 opacity-60" />
                        </button>
                      ) : (
                        <span className="text-slate-400">N/A</span>
                      )}
                    </td>

                    <td className="py-3.5 px-4">
                      <span className="font-mono text-xs text-slate-300 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                        {alert.store_code || 'Store'}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 text-slate-300 font-mono text-[11px]">
                      {alert.rule_key}
                    </td>

                    <td className="py-3.5 px-4 text-slate-200 max-w-xs">
                      {alert.message}
                    </td>

                    <td className="py-3.5 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                        isFiring ? 'bg-rose-950/80 text-rose-400 border border-rose-800' :
                        isAcked ? 'bg-amber-950/80 text-amber-400 border border-amber-800' :
                        'bg-slate-800 text-emerald-400 border border-emerald-900/60'
                      }`}>
                        {alert.state}
                      </span>
                    </td>

                    <td 
                      className="py-3.5 px-4 text-slate-400 text-[11px] font-mono"
                      title={formatUtcTooltip(alert.fired_at)}
                    >
                      {formatPktDateTime(alert.fired_at)}
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        {role !== 'viewer' && isFiring && (
                          <button
                            onClick={() => handleAck(alert.id)}
                            className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-750 text-slate-200 text-[10px] font-semibold"
                          >
                            Ack
                          </button>
                        )}

                        {role !== 'viewer' && !isResolved && (
                          <button
                            onClick={() => handleResolve(alert.id)}
                            className="px-2 py-1 rounded bg-emerald-950 hover:bg-emerald-900 text-emerald-400 border border-emerald-800 text-[10px] font-semibold"
                          >
                            Resolve
                          </button>
                        )}

                        {alert.device_id && (
                          <button
                            onClick={() => onNavigateToDevice(alert.device_id!)}
                            className="p-1 rounded text-slate-500 hover:text-cyan-400"
                            title="View device detail"
                          >
                            <ArrowRight className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}

              {alerts.length === 0 && !loading && (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500 text-xs">
                    No alerts found for selected criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

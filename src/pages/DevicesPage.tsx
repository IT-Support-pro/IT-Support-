import React, { useState, useEffect, useRef } from 'react';
import { 
  Monitor, 
  Search, 
  Filter, 
  Wifi, 
  WifiOff, 
  AlertTriangle, 
  ArrowRight, 
  RefreshCw,
  Layers,
  Pause,
  ShieldCheck
} from 'lucide-react';
import { Device, Store } from '../types';
import { api } from '../api';
import { formatPktDateTime, formatUtcTooltip, formatRelativeMinutesAgo } from '../utils/time';

interface DevicesPageProps {
  initialStoreFilter?: string;
  onSelectDevice: (deviceId: string) => void;
}

export const DevicesPage: React.FC<DevicesPageProps> = ({ 
  initialStoreFilter = '', 
  onSelectDevice 
}) => {
  const [devices, setDevices] = useState<Device[]>([]);
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [storeFilter, setStoreFilter] = useState<string>(initialStoreFilter);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');

  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [updatedText, setUpdatedText] = useState<string>('Updated just now');
  const isFetchingRef = useRef<boolean>(false);

  const fetchDevices = async (isSilent: boolean = false) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;

    try {
      if (!isSilent) setLoading(true);
      setError(null);
      const [devList, storeList] = await Promise.all([
        api.getDevices({
          store: storeFilter || undefined,
          status: statusFilter || undefined,
          type: typeFilter || undefined,
          search: searchQuery || undefined,
          limit: 100
        }),
        api.getStores()
      ]);
      setDevices(devList);
      setStores(storeList);
      setLastUpdated(new Date());
      setUpdatedText('Updated just now');
    } catch (err: any) {
      if (!isSilent) {
        setError(err.message || 'Failed to fetch devices inventory.');
      }
    } finally {
      if (!isSilent) setLoading(false);
      isFetchingRef.current = false;
    }
  };

  useEffect(() => {
    fetchDevices(false);
  }, [storeFilter, statusFilter, typeFilter]);

  // Silent background refresh (every 30s) that preserves filters, search, scroll
  useEffect(() => {
    const rawInterval = localStorage.getItem('hbk_status_refresh_sec');
    const intervalSec = rawInterval ? Math.max(5, parseInt(rawInterval, 10)) : 30;

    const timer = setInterval(() => {
      if (document.hidden) return; // Pause while browser tab is hidden
      fetchDevices(true);
    }, intervalSec * 1000);

    return () => clearInterval(timer);
  }, [storeFilter, statusFilter, typeFilter, searchQuery]);

  // Update "Updated X min ago" tick
  useEffect(() => {
    const textTimer = setInterval(() => {
      setUpdatedText(`Updated ${formatRelativeMinutesAgo(lastUpdated)}`);
    }, 15000);
    return () => clearInterval(textTimer);
  }, [lastUpdated]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchDevices(false);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Monitor className="w-5 h-5 text-cyan-400" />
            Terminal Fleet Inventory
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Monitored POS registers, PC terminals, servers, and network equipment.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-slate-400 bg-slate-900 px-3 py-1 rounded-lg border border-slate-800">
            <span className="text-cyan-400">{updatedText}</span>
          </span>

          <button
            onClick={() => fetchDevices(true)}
            className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition"
            title="Refresh fleet list"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-300 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => fetchDevices(false)} className="px-3 py-1 bg-rose-900 text-white rounded font-semibold text-xs">
            Retry
          </button>
        </div>
      )}

      {/* Filter Toolbar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {/* Search box */}
          <div className="lg:col-span-2 relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search Device ID, IP, or computer name..."
              className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
            />
          </div>

          {/* Store select */}
          <div>
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

          {/* Status select */}
          <div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="">All Statuses</option>
              <option value="ONLINE">ONLINE</option>
              <option value="OFFLINE">OFFLINE</option>
              <option value="PAUSED">PAUSED</option>
              <option value="DEGRADED">DEGRADED</option>
            </select>
          </div>

          {/* Type select */}
          <div className="flex gap-2">
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="">All Types</option>
              <option value="POS">POS</option>
              <option value="PC">PC</option>
              <option value="PRINTER">PRINTER</option>
              <option value="SERVER">SERVER</option>
            </select>
            <button
              type="submit"
              className="px-3 py-2 bg-cyan-600 hover:bg-cyan-500 text-slate-950 rounded-lg text-xs font-bold shrink-0"
            >
              Filter
            </button>
          </div>
        </form>

        <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
          <span>Showing <strong>{devices.length}</strong> devices</span>
          {(storeFilter || statusFilter || typeFilter || searchQuery) && (
            <button
              onClick={() => {
                setStoreFilter('');
                setStatusFilter('');
                setTypeFilter('');
                setSearchQuery('');
              }}
              className="text-cyan-400 hover:underline"
            >
              Clear filters
            </button>
          )}
        </div>
      </div>

      {/* Devices Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950/70 text-slate-400 uppercase text-[10px] tracking-wider font-semibold">
                <th className="py-3 px-4">Device ID</th>
                <th className="py-3 px-4">Computer Name</th>
                <th className="py-3 px-4">Store</th>
                <th className="py-3 px-4">Type</th>
                <th className="py-3 px-4">IP Address</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">FBR</th>
                <th className="py-3 px-4">Last Seen (PKT)</th>
                <th className="py-3 px-4">Active Alerts</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {devices.map((device) => {
                const isPaused = device.agent_state === 'PAUSED' || device.status === 'PAUSED';
                const isOnline = !isPaused && device.status === 'ONLINE';
                const isOffline = device.status === 'OFFLINE';
                const fbrStatus = device.fbr_status || 'NOT_CONFIGURED';

                return (
                  <tr
                    key={device.id}
                    onClick={() => onSelectDevice(device.device_id)}
                    className="hover:bg-slate-850/60 cursor-pointer transition"
                  >
                    <td className="py-3.5 px-4 font-mono font-bold text-white flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full" style={{
                        backgroundColor: isPaused ? '#f59e0b' : isOnline ? '#10b981' : isOffline ? '#ef4444' : '#f59e0b'
                      }}></span>
                      {device.device_id}
                    </td>

                    <td className="py-3.5 px-4 text-slate-300 font-mono text-[11px]">
                      {device.computer_name}
                    </td>

                    <td className="py-3.5 px-4">
                      <span className="font-mono text-cyan-300 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                        {device.store_code}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 text-slate-400">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300">
                        {device.device_type}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 text-slate-300 font-mono text-[11px]">
                      {device.ip_address}
                    </td>

                    {/* Terminal Status Column */}
                    <td className="py-3.5 px-4">
                      {isPaused ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-950/80 text-amber-400 border border-amber-800 flex items-center gap-1 w-fit">
                          <Pause className="w-2.5 h-2.5" /> PAUSED
                        </span>
                      ) : isOnline ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-950/80 text-emerald-400 border border-emerald-800 flex items-center gap-1 w-fit">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> ONLINE
                        </span>
                      ) : isOffline ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-950/80 text-rose-400 border border-rose-800 flex items-center gap-1 w-fit">
                          <WifiOff className="w-2.5 h-2.5" /> OFFLINE
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-950/80 text-amber-400 border border-amber-800">
                          {device.status}
                        </span>
                      )}
                    </td>

                    {/* FBR Status Column */}
                    <td className="py-3.5 px-4">
                      {fbrStatus === 'OK' ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-950/80 text-emerald-400 border border-emerald-800 flex items-center gap-1 w-fit">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Connected
                        </span>
                      ) : fbrStatus === 'DOWN' ? (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-950/80 text-rose-400 border border-rose-800 flex items-center gap-1 w-fit animate-pulse">
                          <span className="w-1.5 h-1.5 rounded-full bg-rose-400"></span> Down
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-800 text-slate-400 border border-slate-700">
                          Not Configured
                        </span>
                      )}
                    </td>

                    <td 
                      className="py-3.5 px-4 text-slate-400 text-[11px] font-mono"
                      title={formatUtcTooltip(device.last_seen)}
                    >
                      {formatPktDateTime(device.last_seen)}
                    </td>

                    <td className="py-3.5 px-4">
                      {(device.active_alerts_count ?? 0) > 0 ? (
                        <span className="px-2 py-0.5 rounded bg-rose-950 text-rose-400 border border-rose-800 text-[10px] font-bold flex items-center gap-1 w-fit">
                          <AlertTriangle className="w-2.5 h-2.5" />
                          {device.active_alerts_count} active
                        </span>
                      ) : (
                        <span className="text-slate-500 text-[11px]">—</span>
                      )}
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      <button 
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectDevice(device.device_id);
                        }}
                        className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition"
                      >
                        <ArrowRight className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}

              {devices.length === 0 && !loading && (
                <tr>
                  <td colSpan={10} className="py-8 text-center text-slate-500 text-xs">
                    No terminals match the current filters.
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

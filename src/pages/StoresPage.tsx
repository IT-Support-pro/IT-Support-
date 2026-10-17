import React, { useState, useEffect } from 'react';
import { Store as StoreIcon, Monitor, WifiOff, AlertTriangle, ArrowRight, RefreshCw, Layers } from 'lucide-react';
import { Store } from '../types';
import { api } from '../api';

interface StoresPageProps {
  onSelectStore: (storeCode: string) => void;
}

export const StoresPage: React.FC<StoresPageProps> = ({ onSelectStore }) => {
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStores = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getStores();
      setStores(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load stores.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStores();
  }, []);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <StoreIcon className="w-5 h-5 text-cyan-400" />
            Hypermarket Stores & Branches
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Store hierarchy, POS lane densities, and network connectivity summaries.
          </p>
        </div>

        <button
          onClick={fetchStores}
          className="self-start sm:self-auto px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white text-xs flex items-center gap-1.5 transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-300 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button onClick={fetchStores} className="px-3 py-1 bg-rose-900 text-white rounded font-bold text-xs">
            Retry
          </button>
        </div>
      )}

      {/* Stores Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {stores.map((s) => (
          <div
            key={s.id}
            onClick={() => onSelectStore(s.code)}
            className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-5 cursor-pointer transition flex flex-col justify-between space-y-4 shadow-lg group"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-black text-cyan-300 bg-cyan-950/80 px-2 py-0.5 rounded border border-cyan-800">
                  {s.code}
                </span>
                <span className="text-[11px] text-slate-500 font-mono">
                  Region: {s.region}
                </span>
              </div>
              <h3 className="text-base font-bold text-white mt-2 group-hover:text-cyan-400 transition">
                {s.name}
              </h3>
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-3 gap-2 p-3 bg-slate-950/70 rounded-xl border border-slate-800 text-center">
              <div>
                <span className="text-[10px] text-slate-500 uppercase block font-semibold">Terminals</span>
                <span className="text-lg font-black text-white font-mono">{s.devices_total ?? 0}</span>
              </div>
              <div>
                <span className="text-[10px] text-emerald-500 uppercase block font-semibold">Online</span>
                <span className="text-lg font-black text-emerald-400 font-mono">{s.online_count ?? 0}</span>
              </div>
              <div>
                <span className="text-[10px] text-rose-500 uppercase block font-semibold">Offline</span>
                <span className="text-lg font-black text-rose-400 font-mono">{s.offline_count ?? 0}</span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-xs text-slate-400">
              <div className="flex items-center gap-1.5">
                {(s.firing_alerts ?? 0) > 0 ? (
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-400 border border-rose-800 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    {s.firing_alerts} Alerts
                  </span>
                ) : (
                  <span className="text-emerald-400 text-[11px] font-semibold flex items-center gap-1">
                    All terminals nominal
                  </span>
                )}
              </div>

              <span className="text-cyan-400 flex items-center gap-1 font-semibold group-hover:translate-x-0.5 transition">
                View devices <ArrowRight className="w-3.5 h-3.5" />
              </span>
            </div>
          </div>
        ))}

        {stores.length === 0 && !loading && (
          <div className="col-span-3 p-12 text-center text-slate-500 text-xs bg-slate-900 border border-slate-800 rounded-xl">
            No hypermarket stores configured in the database yet.
          </div>
        )}
      </div>
    </div>
  );
};

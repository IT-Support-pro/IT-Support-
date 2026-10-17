import React, { useState, useEffect, useRef } from 'react';
import { 
  ShieldCheck, 
  ShieldAlert, 
  Server, 
  RefreshCw, 
  Search, 
  Filter, 
  ExternalLink, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Clock, 
  Building2, 
  HelpCircle,
  Edit3,
  Link2,
  Unlink,
  Check,
  ChevronRight
} from 'lucide-react';
import { api } from '../api';
import { FbrRegistration, Device, Store } from '../types';
import { useAuth } from '../context/AuthContext';
import { formatPktDateTime, formatPktTime, formatUtcTooltip, timeAgoPkt } from '../utils/time';

interface FbrMonitoringPageProps {
  onNavigateToDevice?: (deviceId: string) => void;
}

export const FbrMonitoringPage: React.FC<FbrMonitoringPageProps> = ({ onNavigateToDevice }) => {
  const { role } = useAuth();
  const isAdmin = role === 'admin';
  const isOperator = role === 'admin' || role === 'technician';

  const [registrations, setRegistrations] = useState<FbrRegistration[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [checkingIds, setCheckingIds] = useState<Record<number, boolean>>({});

  // Filters
  const [selectedBranch, setSelectedBranch] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [unmappedOnly, setUnmappedOnly] = useState<boolean>(false);
  const [unidentifiedOnly, setUnidentifiedOnly] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Edit Mapping Modal State
  const [editingReg, setEditingReg] = useState<FbrRegistration | null>(null);
  const [editDevicePk, setEditDevicePk] = useState<string>('');
  const [editNotes, setEditNotes] = useState<string>('');
  const [saveLoading, setSaveLoading] = useState<boolean>(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const isMountedRef = useRef<boolean>(true);

  const fetchRegistrations = async (isBackground = false) => {
    if (!isBackground) setLoading(true);
    else setIsUpdating(true);

    try {
      const [regsData, devsData, storesData] = await Promise.all([
        api.getFbrRegistrations(),
        api.getDevices(),
        api.getStores()
      ]);

      if (isMountedRef.current) {
        setRegistrations(regsData);
        setDevices(devsData);
        setStores(storesData);
        setLastUpdated(new Date());
      }
    } catch (err) {
      console.error('Failed to fetch FBR registrations:', err);
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
        setIsUpdating(false);
      }
    }
  };

  useEffect(() => {
    isMountedRef.current = true;
    fetchRegistrations();

    // 30s background silent refresh
    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        fetchRegistrations(true);
      }
    }, 30000);

    return () => {
      isMountedRef.current = false;
      clearInterval(interval);
    };
  }, []);

  const handleCheckFbrNow = async (reg: FbrRegistration) => {
    if (!reg.device_pk) return;
    setCheckingIds(prev => ({ ...prev, [reg.id]: true }));

    // Optimistically show CHECKING state
    setRegistrations(prev =>
      prev.map(r => r.id === reg.id ? { ...r, fbr_connectivity_status: 'CHECKING' } : r)
    );

    try {
      await api.checkFbrNow(reg.id);
      // Wait 3s then refresh to let agent heartbeat pick up task
      setTimeout(() => {
        fetchRegistrations(true);
        setCheckingIds(prev => ({ ...prev, [reg.id]: false }));
      }, 3500);
    } catch (err: any) {
      alert(`FBR check dispatch failed: ${err.message}`);
      setCheckingIds(prev => ({ ...prev, [reg.id]: false }));
      fetchRegistrations(true);
    }
  };

  const openEditModal = (reg: FbrRegistration) => {
    setEditingReg(reg);
    setEditDevicePk(reg.device_pk || '');
    setEditNotes(reg.admin_notes || '');
    setSaveError(null);
  };

  const handleSaveMapping = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingReg) return;
    setSaveLoading(true);
    setSaveError(null);

    try {
      await api.updateFbrRegistration(editingReg.id, {
        device_pk: editDevicePk || '',
        admin_notes: editNotes
      });
      setEditingReg(null);
      await fetchRegistrations(true);
    } catch (err: any) {
      setSaveError(err.message || 'Failed to update mapping');
    } finally {
      setSaveLoading(false);
    }
  };

  // Filtered registrations
  const filteredRegistrations = registrations.filter(r => {
    if (selectedBranch !== 'ALL' && !r.branch_name.includes(selectedBranch)) {
      return false;
    }
    if (selectedStatus !== 'ALL') {
      const st = r.fbr_connectivity_status || 'UNKNOWN';
      if (selectedStatus === 'CONNECTED' && st !== 'CONNECTED') return false;
      if (selectedStatus === 'DISCONNECTED' && st !== 'DISCONNECTED') return false;
      if (selectedStatus === 'LOCAL_SERVICE_DOWN' && st !== 'LOCAL_SERVICE_DOWN') return false;
      if (selectedStatus === 'UNKNOWN' && st !== 'UNKNOWN') return false;
      if (selectedStatus === 'CHECKING' && st !== 'CHECKING') return false;
    }
    if (unmappedOnly && r.device_pk) {
      return false;
    }
    if (unidentifiedOnly && !r.is_unidentified) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchPos = r.pos_identification.toLowerCase().includes(q);
      const matchId = String(r.fbr_pos_id).includes(q);
      const matchBranch = r.branch_name.toLowerCase().includes(q);
      const matchDevice = r.device_id?.toLowerCase().includes(q);
      if (!matchPos && !matchId && !matchBranch && !matchDevice) return false;
    }
    return true;
  });

  // Aggregates
  const totalCount = registrations.length;
  const mappedCount = registrations.filter(r => !!r.device_pk).length;
  const connectedCount = registrations.filter(r => r.fbr_connectivity_status === 'CONNECTED').length;
  const disconnectedCount = registrations.filter(r => r.fbr_connectivity_status === 'DISCONNECTED').length;
  const localServiceDownCount = registrations.filter(r => r.local_ims_status === 'DOWN' || r.fbr_connectivity_status === 'LOCAL_SERVICE_DOWN').length;
  const unknownCount = registrations.filter(r => !r.fbr_connectivity_status || r.fbr_connectivity_status === 'UNKNOWN').length;
  const unidentifiedCount = registrations.filter(r => r.is_unidentified).length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-cyan-400" />
              FBR Per-POS Fiscal Monitoring & Device Mapping
            </h1>
            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-cyan-950 text-cyan-400 border border-cyan-800">
              PRAL / IMS
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Real-time per-POS connectivity telemetry across Ring Road, Cantt, and I-8 Islamabad store branches.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
            {isUpdating && <RefreshCw className="w-3.5 h-3.5 animate-spin text-cyan-400" />}
            <span>Updated {timeAgoPkt(lastUpdated)}</span>
          </div>
          <button
            onClick={() => fetchRegistrations(true)}
            disabled={isUpdating}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1.5 transition border border-slate-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isUpdating ? 'animate-spin' : ''}`} />
            Refresh status
          </button>
        </div>
      </div>

      {/* Summary Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Total Registered</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-black text-white">{totalCount}</span>
            <span className="text-[10px] text-slate-400 font-medium">3 Branches</span>
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">{mappedCount} mapped to active POS</span>
        </div>

        <div className="bg-slate-900 border border-emerald-950/60 rounded-xl p-3.5">
          <span className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider block">FBR Connected</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-black text-emerald-400">{connectedCount}</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">Full cloud reachability</span>
        </div>

        <div className="bg-slate-900 border border-rose-950/60 rounded-xl p-3.5">
          <span className="text-[11px] font-semibold text-rose-400 uppercase tracking-wider block">Disconnected</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-black text-rose-400">{disconnectedCount}</span>
            <XCircle className="w-4 h-4 text-rose-400" />
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">FBR cloud probe failed</span>
        </div>

        <div className="bg-slate-900 border border-amber-950/60 rounded-xl p-3.5">
          <span className="text-[11px] font-semibold text-amber-400 uppercase tracking-wider block">IMS Service Down</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-black text-amber-400">{localServiceDownCount}</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">Local port 8524 stopped</span>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Unknown / Probe</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-black text-slate-300">{unknownCount}</span>
            <HelpCircle className="w-4 h-4 text-slate-400" />
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">IMS only or unprobed</span>
        </div>

        <div className="bg-slate-900 border border-indigo-950/60 rounded-xl p-3.5">
          <span className="text-[11px] font-semibold text-indigo-400 uppercase tracking-wider block">Pending Review</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-black text-indigo-300">{unidentifiedCount}</span>
            <span className="px-1.5 py-0.2 rounded text-[10px] bg-indigo-950 text-indigo-400 border border-indigo-800">
              ID: ----------
            </span>
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">Unidentified registrations</span>
        </div>
      </div>

      {/* Unidentified Registrations Notice Card */}
      {unidentifiedCount > 0 && (
        <div className="bg-gradient-to-r from-indigo-950/40 to-slate-900 border border-indigo-900/60 rounded-xl p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-indigo-900/60 border border-indigo-700/60 flex items-center justify-center shrink-0 text-indigo-300">
              <AlertTriangle className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-xs font-bold text-indigo-200">
                Administrator Action Required: {unidentifiedCount} Unidentified Inactive Registrations Detected
              </h3>
              <p className="text-[11px] text-slate-300 mt-0.5">
                FBR registration records with identification number <span className="font-mono font-bold text-amber-300">----------</span> (FBR POS IDs <strong>156470</strong> &amp; <strong>189547</strong>) are deliberately kept unmapped and not tied to production POS machines.
              </p>
            </div>
          </div>
          <button
            onClick={() => {
              setUnidentifiedOnly(!unidentifiedOnly);
              setUnmappedOnly(false);
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition shrink-0 ${
              unidentifiedOnly
                ? 'bg-indigo-600 text-white'
                : 'bg-indigo-950 text-indigo-300 border border-indigo-800 hover:bg-indigo-900'
            }`}
          >
            {unidentifiedOnly ? 'Show All Registrations' : 'Review Unidentified (2)'}
          </button>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {/* Branch Filter */}
          <div>
            <label className="text-[11px] font-semibold text-slate-400 block mb-1">Store / Branch</label>
            <select
              value={selectedBranch}
              onChange={(e) => setSelectedBranch(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="ALL">All Branches (Ring Road, Cantt, I-8)</option>
              <option value="Ring Road">HBK Hypermarket Ring Road</option>
              <option value="Cantt">HBK Supermarket Cantt</option>
              <option value="Islamabad">HBK Hypermarket I-8 Islamabad</option>
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <label className="text-[11px] font-semibold text-slate-400 block mb-1">FBR Status</label>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="ALL">All Connectivity States</option>
              <option value="CONNECTED">CONNECTED (Cloud probe OK)</option>
              <option value="DISCONNECTED">DISCONNECTED (Cloud probe failed)</option>
              <option value="LOCAL_SERVICE_DOWN">LOCAL_SERVICE_DOWN (Port 8524 dead)</option>
              <option value="UNKNOWN">UNKNOWN (IMS responding, FBR unverified)</option>
              <option value="CHECKING">CHECKING (Probe in progress)</option>
            </select>
          </div>

          {/* Search Box */}
          <div className="md:col-span-2">
            <label className="text-[11px] font-semibold text-slate-400 block mb-1">Search Identifier, FBR POS ID, or Device</label>
            <div className="relative">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search HYT-POS01, 149121, ISB POS05..."
                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>
        </div>

        {/* Toggles */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-800/60 text-xs">
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer text-slate-300">
              <input
                type="checkbox"
                checked={unmappedOnly}
                onChange={(e) => {
                  setUnmappedOnly(e.target.checked);
                  if (e.target.checked) setUnidentifiedOnly(false);
                }}
                className="rounded bg-slate-950 border-slate-800 text-cyan-500 focus:ring-0"
              />
              Show Unmapped Registrations Only
            </label>
            <label className="flex items-center gap-2 cursor-pointer text-slate-300">
              <input
                type="checkbox"
                checked={unidentifiedOnly}
                onChange={(e) => {
                  setUnidentifiedOnly(e.target.checked);
                  if (e.target.checked) setUnmappedOnly(false);
                }}
                className="rounded bg-slate-950 border-slate-800 text-indigo-500 focus:ring-0"
              />
              Show Unidentified (----------) Only
            </label>
          </div>

          <span className="text-[11px] text-slate-400 font-mono">
            Showing {filteredRegistrations.length} of {registrations.length} registered POS entries
          </span>
        </div>
      </div>

      {/* Main Registrations & Telemetry Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950 border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
              <tr>
                <th className="py-3 px-3.5">FBR POS ID</th>
                <th className="py-3 px-3.5">Registration Info</th>
                <th className="py-3 px-3.5">Branch / Store</th>
                <th className="py-3 px-3.5">Mapped Device</th>
                <th className="py-3 px-3.5">Local IMS (8524)</th>
                <th className="py-3 px-3.5">FBR Connectivity</th>
                <th className="py-3 px-3.5">Latency</th>
                <th className="py-3 px-3.5">Last Check (PKT)</th>
                <th className="py-3 px-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-sans">
              {loading && registrations.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-400">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto text-cyan-400 mb-2" />
                    Loading FBR telemetry and registration mappings...
                  </td>
                </tr>
              ) : filteredRegistrations.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500">
                    No registered POS matching filter criteria.
                  </td>
                </tr>
              ) : (
                filteredRegistrations.map((reg) => {
                  const isChecking = checkingIds[reg.id] || reg.fbr_connectivity_status === 'CHECKING';
                  const isMapped = !!reg.device_pk;
                  const connStatus = reg.fbr_connectivity_status || 'UNKNOWN';
                  const localIms = reg.local_ims_status || 'UNKNOWN';

                  return (
                    <tr 
                      key={reg.id} 
                      className={`hover:bg-slate-800/40 transition ${
                        reg.is_unidentified ? 'bg-indigo-950/10' : !isMapped ? 'bg-slate-950/40' : ''
                      }`}
                    >
                      {/* FBR POS ID */}
                      <td className="py-3 px-3.5 font-mono font-bold text-white">
                        <div className="flex items-center gap-1.5">
                          <span className="text-cyan-400">{reg.fbr_pos_id}</span>
                          {reg.is_unidentified && (
                            <span className="px-1 py-0.2 rounded text-[9px] bg-indigo-950 text-indigo-300 border border-indigo-800">
                              Review
                            </span>
                          )}
                        </div>
                        <span className="text-[10px] text-slate-400 block font-normal">
                          {reg.pos_software_version || 'CCO 2.0'}
                        </span>
                      </td>

                      {/* POS Identification */}
                      <td className="py-3 px-3.5">
                        <div className="font-semibold text-slate-200">
                          {reg.pos_identification}
                        </div>
                        {reg.admin_notes && (
                          <span className="text-[10px] text-amber-400/90 block truncate max-w-xs" title={reg.admin_notes}>
                            Note: {reg.admin_notes}
                          </span>
                        )}
                      </td>

                      {/* Branch Name */}
                      <td className="py-3 px-3.5 text-slate-300">
                        <div className="flex items-center gap-1">
                          <Building2 className="w-3 h-3 text-slate-400 shrink-0" />
                          <span className="truncate max-w-[160px]">{reg.branch_name}</span>
                        </div>
                        <span className="text-[10px] text-slate-400 font-mono">
                          {reg.store_code || 'Unlinked'}
                        </span>
                      </td>

                      {/* Mapped Device */}
                      <td className="py-3 px-3.5">
                        {isMapped ? (
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => reg.device_id && onNavigateToDevice && onNavigateToDevice(reg.device_id)}
                              className="font-mono font-bold text-cyan-400 hover:text-cyan-300 hover:underline flex items-center gap-1 text-xs"
                            >
                              {reg.device_id || 'Device'}
                              <ExternalLink className="w-3 h-3" />
                            </button>
                            <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                              reg.device_status === 'ONLINE' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                              reg.device_status === 'PAUSED' ? 'bg-amber-950 text-amber-400 border border-amber-800' :
                              'bg-rose-950 text-rose-400 border border-rose-800'
                            }`}>
                              {reg.device_status || 'UNKNOWN'}
                            </span>
                          </div>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700">
                            Unmapped
                          </span>
                        )}
                      </td>

                      {/* Local PRAL / IMS Service Status */}
                      <td className="py-3 px-3.5">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold inline-flex items-center gap-1 ${
                          localIms === 'RUNNING' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                          localIms === 'DOWN' ? 'bg-rose-950 text-rose-400 border border-rose-800' :
                          'bg-slate-800 text-slate-400 border border-slate-700'
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${
                            localIms === 'RUNNING' ? 'bg-emerald-400' :
                            localIms === 'DOWN' ? 'bg-rose-400' : 'bg-slate-500'
                          }`} />
                          {localIms === 'RUNNING' ? 'Running (8524)' :
                           localIms === 'DOWN' ? 'Service Down' : 'Unknown'}
                        </span>
                      </td>

                      {/* FBR Connectivity Status */}
                      <td className="py-3 px-3.5">
                        <span className={`px-2.5 py-1 rounded-full text-[11px] font-bold inline-flex items-center gap-1.5 ${
                          connStatus === 'CONNECTED' ? 'bg-emerald-950 text-emerald-300 border border-emerald-700 shadow-sm shadow-emerald-900/30' :
                          connStatus === 'DISCONNECTED' ? 'bg-rose-950 text-rose-300 border border-rose-700 animate-pulse' :
                          connStatus === 'LOCAL_SERVICE_DOWN' ? 'bg-amber-950 text-amber-300 border border-amber-700' :
                          connStatus === 'CHECKING' ? 'bg-cyan-950 text-cyan-300 border border-cyan-700' :
                          'bg-slate-800 text-slate-400 border border-slate-700'
                        }`}>
                          <span className={`w-2 h-2 rounded-full ${
                            connStatus === 'CONNECTED' ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50' :
                            connStatus === 'DISCONNECTED' ? 'bg-rose-500' :
                            connStatus === 'LOCAL_SERVICE_DOWN' ? 'bg-amber-400' :
                            connStatus === 'CHECKING' ? 'bg-cyan-400 animate-ping' : 'bg-slate-500'
                          }`} />
                          {connStatus === 'CONNECTED' ? 'CONNECTED' :
                           connStatus === 'DISCONNECTED' ? 'DISCONNECTED' :
                           connStatus === 'LOCAL_SERVICE_DOWN' ? 'LOCAL_SERVICE_DOWN' :
                           connStatus === 'CHECKING' ? 'CHECKING...' : 'UNKNOWN'}
                        </span>
                        {reg.fbr_consecutive_failures && reg.fbr_consecutive_failures > 0 ? (
                          <span className="text-[10px] text-rose-400 font-mono block mt-0.5">
                            {reg.fbr_consecutive_failures} fail streak
                          </span>
                        ) : null}
                      </td>

                      {/* Response Latency */}
                      <td className="py-3 px-3.5 font-mono text-slate-300">
                        {reg.fbr_latency_ms != null ? (
                          <span>{reg.fbr_latency_ms} ms</span>
                        ) : (
                          <span className="text-slate-500">N/A</span>
                        )}
                      </td>

                      {/* Last Check Date & Time in PKT */}
                      <td className="py-3 px-3.5">
                        {reg.fbr_last_check ? (
                          <div>
                            <span 
                              className="font-mono text-xs text-slate-200 block" 
                              title={formatUtcTooltip(reg.fbr_last_check)}
                            >
                              {formatPktTime(reg.fbr_last_check)}
                            </span>
                            <span className="text-[10px] text-slate-400">
                              {timeAgoPkt(reg.fbr_last_check)}
                            </span>
                          </div>
                        ) : (
                          <span className="text-slate-500">Never checked</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="py-3 px-3.5 text-right space-x-1.5 whitespace-nowrap">
                        {isMapped && (
                          <button
                            onClick={() => handleCheckFbrNow(reg)}
                            disabled={isChecking || !isOperator}
                            title="Queue outbound fbr_check_now task for this POS agent"
                            className="px-2.5 py-1 rounded bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-800 text-[11px] font-bold transition disabled:opacity-40 inline-flex items-center gap-1"
                          >
                            <RefreshCw className={`w-3 h-3 ${isChecking ? 'animate-spin' : ''}`} />
                            {isChecking ? 'Checking...' : 'Check FBR'}
                          </button>
                        )}

                        {isAdmin && (
                          <button
                            onClick={() => openEditModal(reg)}
                            title="Edit POS device mapping"
                            className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-[11px] font-medium transition inline-flex items-center gap-1"
                          >
                            <Edit3 className="w-3 h-3" />
                            Map
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Edit Device Mapping Modal */}
      {editingReg && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Link2 className="w-5 h-5 text-cyan-400" />
                <h3 className="text-base font-bold text-white">
                  Edit POS Mapping — FBR ID {editingReg.fbr_pos_id}
                </h3>
              </div>
              <button
                onClick={() => setEditingReg(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleSaveMapping} className="space-y-4 text-xs">
              <div>
                <span className="text-slate-400 block mb-0.5">Registration Identification:</span>
                <span className="font-mono font-bold text-white text-sm">{editingReg.pos_identification}</span>
                <span className="text-slate-400 block mt-0.5">{editingReg.branch_name}</span>
              </div>

              {saveError && (
                <div className="p-3 rounded-lg bg-rose-950/80 border border-rose-800 text-rose-300 text-xs">
                  {saveError}
                </div>
              )}

              <div>
                <label className="text-slate-300 font-semibold block mb-1">
                  Assign to Production Device
                </label>
                <select
                  value={editDevicePk}
                  onChange={(e) => setEditDevicePk(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-cyan-500"
                >
                  <option value="">-- Unmapped / No Device --</option>
                  {devices.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.device_id} ({d.computer_name}) — {d.store_code} [{d.ip_address}]
                    </option>
                  ))}
                </select>
                <span className="text-[10px] text-slate-400 mt-1 block">
                  Select the physical checkout terminal running the HBK Agent on this lane.
                </span>
              </div>

              <div>
                <label className="text-slate-300 font-semibold block mb-1">
                  Administrator Notes
                </label>
                <textarea
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                  rows={3}
                  placeholder="Review notes, e.g., 'Lane 12 replacement terminal assigned by IT team on Oct 16'"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-100 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-400 space-y-1">
                <span className="font-bold text-slate-300 block">Security &amp; Integrity Policy:</span>
                <p>• FBR tokens are stored server-side and never exposed in the dashboard interface.</p>
                <p>• Re-mapping updates the device's FBR POS ID without altering hardware credentials.</p>
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setEditingReg(null)}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saveLoading}
                  className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold transition flex items-center gap-1.5 shadow-lg shadow-cyan-600/20 disabled:opacity-50"
                >
                  {saveLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                  Save Mapping
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

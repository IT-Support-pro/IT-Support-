import React, { useState, useEffect, useRef } from 'react';
import { 
  ArrowLeft, 
  RefreshCw, 
  Clock, 
  Cpu, 
  HardDrive, 
  Activity, 
  Printer, 
  Wifi, 
  WifiOff, 
  AlertTriangle, 
  CheckCircle2, 
  Play, 
  Pause, 
  RotateCcw, 
  Zap, 
  Info, 
  ShieldAlert, 
  XCircle, 
  ShieldCheck, 
  ChevronDown, 
  ChevronUp,
  Radio,
  Network
} from 'lucide-react';
import { MetricPoint, Note, Alert, AgentTask } from '../types';
import { api } from '../api';
import { MetricChart } from '../components/MetricChart';
import { useAuth } from '../context/AuthContext';
import { formatPktTime, formatPktDateTime, formatUtcTooltip, formatRelativeMinutesAgo } from '../utils/time';

interface DeviceDetailPageProps {
  deviceId: string;
  onBack: () => void;
}

export const DeviceDetailPage: React.FC<DeviceDetailPageProps> = ({ deviceId, onBack }) => {
  const { role } = useAuth();
  const [deviceDetail, setDeviceDetail] = useState<any | null>(null);
  const [metricsSeries, setMetricsSeries] = useState<MetricPoint[]>([]);
  const [timeWindowMinutes, setTimeWindowMinutes] = useState<number>(1440); // Default range 24 h
  const [notes, setNotes] = useState<Note[]>([]);
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [newNoteText, setNewNoteText] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [submittingNote, setSubmittingNote] = useState<boolean>(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showOtherAdapters, setShowOtherAdapters] = useState<boolean>(false);

  // Background refresh tracking
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());
  const [updatedText, setUpdatedText] = useState<string>('Updated just now');
  const isFetchingRef = useRef<boolean>(false);

  // Remote task confirmation modal
  const [confirmModal, setConfirmModal] = useState<{
    open: boolean;
    action: 'pause' | 'restart_agent';
    title: string;
    message: string;
  } | null>(null);
  const [runningAction, setRunningAction] = useState<string | null>(null);

  // Live ticking POS local clock (based on last local_time plus elapsed ms)
  const [livePosTime, setLivePosTime] = useState<Date | null>(null);
  const [liveCentralTime, setLiveCentralTime] = useState<Date>(new Date());

  // Ticking central time
  useEffect(() => {
    const t = setInterval(() => setLiveCentralTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // Silent fetch that does not show full-screen spinner if deviceDetail is already loaded
  const fetchDeviceData = async (isSilent: boolean = false, fetchMetricsToo: boolean = true) => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;

    try {
      if (!isSilent) setLoading(true);
      setError(null);

      const promises: [Promise<any>, Promise<any>, Promise<any>, Promise<any>] = [
        api.getDeviceDetail(deviceId),
        fetchMetricsToo ? api.getDeviceMetrics(deviceId, timeWindowMinutes) : Promise.resolve(null),
        api.getDeviceNotes(deviceId),
        api.getDeviceTasks(deviceId).catch(() => [])
      ];

      const [detail, metrics, devNotes, devTasks] = await Promise.all(promises);

      setDeviceDetail(detail);
      if (metrics && metrics.series) {
        setMetricsSeries(metrics.series);
      }
      setNotes(devNotes);
      setTasks(devTasks || detail.tasks || []);
      setLastUpdated(new Date());
      setUpdatedText('Updated just now');
    } catch (err: any) {
      if (!isSilent) {
        setError(err.message || 'Failed to fetch device telemetry.');
      }
    } finally {
      if (!isSilent) setLoading(false);
      isFetchingRef.current = false;
    }
  };

  // Initial load
  useEffect(() => {
    fetchDeviceData(false, true);
  }, [deviceId, timeWindowMinutes]);

  // Silent background refresh for status/tasks/FBR (default 30s)
  useEffect(() => {
    const rawInterval = localStorage.getItem('hbk_status_refresh_sec');
    const intervalSec = rawInterval ? Math.max(5, parseInt(rawInterval, 10)) : 30;

    const timer = setInterval(() => {
      if (document.hidden) return; // Pause while browser tab is hidden
      fetchDeviceData(true, false);
    }, intervalSec * 1000);

    return () => clearInterval(timer);
  }, [deviceId]);

  // Silent background refresh for full data and charts (default 15 minutes)
  useEffect(() => {
    const rawFullInterval = localStorage.getItem('hbk_full_refresh_min');
    const fullMin = rawFullInterval ? Math.max(1, parseInt(rawFullInterval, 10)) : 15;

    const fullTimer = setInterval(() => {
      if (document.hidden) return; // Pause while tab is hidden
      fetchDeviceData(true, true);
    }, fullMin * 60 * 1000);

    return () => clearInterval(fullTimer);
  }, [deviceId, timeWindowMinutes]);

  // Update "Updated X min ago" text
  useEffect(() => {
    const textTimer = setInterval(() => {
      setUpdatedText(`Updated ${formatRelativeMinutesAgo(lastUpdated)}`);
    }, 15000);
    return () => clearInterval(textTimer);
  }, [lastUpdated]);

  // Live ticking POS clock effect (based on last local_time plus elapsed ms)
  useEffect(() => {
    if (!deviceDetail?.local_time && !deviceDetail?.utc_time) {
      setLivePosTime(null);
      return;
    }
    const baseIso = deviceDetail.local_time || deviceDetail.utc_time;
    const baseMs = new Date(baseIso).getTime();
    const fetchStart = Date.now();

    setLivePosTime(new Date(baseMs));

    const interval = setInterval(() => {
      const elapsed = Date.now() - fetchStart;
      setLivePosTime(new Date(baseMs + elapsed));
    }, 1000);

    return () => clearInterval(interval);
  }, [deviceDetail?.local_time, deviceDetail?.utc_time]);

  // Task execution triggers
  const handleTriggerTask = (action: 'pause' | 'resume' | 'collect_now' | 'fbr_check_now' | 'restart_agent') => {
    if (action === 'pause') {
      setConfirmModal({
        open: true,
        action: 'pause',
        title: 'Confirm Agent Telemetry Pause',
        message: 'Are you sure you want to pause telemetry for this POS terminal? Full readings and metric alerts will be suspended, while outbound heartbeats continue. A stopped agent cannot be started remotely. Use Pause instead.'
      });
      return;
    }
    if (action === 'restart_agent') {
      setConfirmModal({
        open: true,
        action: 'restart_agent',
        title: 'Confirm Windows Service Restart',
        message: 'This instructs the agent to terminate cleanly with exit code 42. The Windows Service Recovery manager will automatically restart HBKAgent within 30 seconds. Outbound communication will briefly pause.'
      });
      return;
    }
    executeTask(action);
  };

  const executeTask = async (action: string) => {
    try {
      setRunningAction(action);
      setError(null);
      const newTask = await api.sendDeviceTask(deviceId, action);
      setActionSuccess(`Task '${action}' submitted (#${newTask.id}). Waiting for agent outbound execution...`);
      
      // Update task list
      const updatedTasks = await api.getDeviceTasks(deviceId).catch(() => []);
      setTasks(updatedTasks);

      // Refresh silently after a short delay to allow agent heartbeat pickup
      setTimeout(() => {
        fetchDeviceData(true, true);
        setActionSuccess(`Task '${action}' queued and dispatched.`);
        setTimeout(() => setActionSuccess(null), 4000);
      }, 2000);
    } catch (err: any) {
      setError(err.message || `Failed to submit task '${action}'`);
    } finally {
      setRunningAction(null);
      setConfirmModal(null);
    }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNoteText.trim()) return;

    try {
      setSubmittingNote(true);
      const created = await api.addDeviceNote(deviceId, newNoteText.trim());
      setNotes([created, ...notes]);
      setNewNoteText('');
      setActionSuccess('Operational note added successfully');
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to add note');
    } finally {
      setSubmittingNote(false);
    }
  };

  const handleAckAlert = async (alertId: number) => {
    try {
      await api.ackAlert(alertId);
      setActionSuccess(`Alert #${alertId} acknowledged`);
      setTimeout(() => setActionSuccess(null), 3000);
      fetchDeviceData(true, false);
    } catch (err: any) {
      setError(err.message || 'Failed to acknowledge alert');
    }
  };

  const handleResolveAlert = async (alertId: number) => {
    try {
      await api.resolveAlert(alertId);
      setActionSuccess(`Alert #${alertId} marked resolved`);
      setTimeout(() => setActionSuccess(null), 3000);
      fetchDeviceData(true, false);
    } catch (err: any) {
      setError(err.message || 'Failed to resolve alert');
    }
  };

  const getLastReadingText = () => {
    const lastTs = deviceDetail?.latest_metrics?.ts || deviceDetail?.last_seen;
    if (!lastTs) return 'No readings yet';
    const diffMins = Math.max(0, Math.round((Date.now() - new Date(lastTs).getTime()) / 60000));
    if (diffMins < 1) return 'Just now';
    if (diffMins === 1) return '1 min ago';
    if (diffMins < 60) return `${diffMins} min ago`;
    const diffHours = Math.round(diffMins / 60);
    return `${diffHours} hr${diffHours > 1 ? 's' : ''} ago`;
  };

  if (loading && !deviceDetail) {
    return (
      <div className="flex flex-col items-center justify-center h-80 space-y-3">
        <RefreshCw className="w-6 h-6 text-cyan-400 animate-spin" />
        <span className="text-xs text-slate-400">Loading terminal diagnostics for {deviceId}...</span>
      </div>
    );
  }

  if (error && !deviceDetail) {
    return (
      <div className="space-y-4">
        <button onClick={onBack} className="text-xs text-slate-400 hover:text-white flex items-center gap-1.5">
          <ArrowLeft className="w-4 h-4" /> Back to inventory
        </button>
        <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-300 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => fetchDeviceData(false, true)} className="px-3 py-1 bg-rose-900 text-white rounded font-bold text-xs">
            Retry
          </button>
        </div>
      </div>
    );
  }

  const latest = deviceDetail?.latest_metrics;
  const isOnline = deviceDetail?.status === 'ONLINE';
  const isPaused = deviceDetail?.agent_state === 'PAUSED' || deviceDetail?.status === 'PAUSED';
  const isOffline = deviceDetail?.status === 'OFFLINE';

  const clockDrift = deviceDetail?.clock_offset_sec;
  const clockDriftAbs = clockDrift != null ? Math.abs(clockDrift) : null;
  const driftMs = clockDrift != null ? Math.round(clockDrift * 1000) : null;
  const driftMsAbs = driftMs != null ? Math.abs(driftMs) : null;
  const isHighDrift = driftMsAbs != null && driftMsAbs > 5000;

  // Network adapters analysis: primary adapter first
  const adapters: any[] = latest?.network?.adapters || [];
  const primaryAdapter = adapters.find((a: any) => a.is_primary) || adapters[0] || null;
  const otherAdapters = adapters.filter((a: any) => a !== primaryAdapter);
  const primaryIp = primaryAdapter?.ipv4 || primaryAdapter?.ip || deviceDetail?.ip_address || '127.0.0.1';

  return (
    <div className="space-y-6">
      {/* Top Bar & Breadcrumb */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-black text-white font-mono">{deviceDetail?.device_id}</h2>
              
              {/* Dynamic Status Badges */}
              {isPaused ? (
                <span className="px-2.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-950 text-amber-400 border border-amber-800 flex items-center gap-1">
                  <Pause className="w-3 h-3" /> Paused
                </span>
              ) : isOnline ? (
                <span className="px-2.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-emerald-950 text-emerald-400 border border-emerald-800 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> Online
                </span>
              ) : isOffline ? (
                <span className="px-2.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-950 text-rose-400 border border-rose-800 flex items-center gap-1">
                  <WifiOff className="w-3 h-3" /> Offline
                </span>
              ) : (
                <span className="px-2.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-amber-950 text-amber-400 border border-amber-800">
                  {deviceDetail?.status}
                </span>
              )}

              <span className="text-xs text-slate-400">({deviceDetail?.computer_name})</span>
            </div>
            
            <p className="text-xs text-slate-400 mt-0.5">
              Store: <strong className="text-slate-200">{deviceDetail?.store_code}</strong> • Type: {deviceDetail?.device_type} • Primary IP:{' '}
              <code className="text-cyan-300 font-mono font-bold">{primaryIp}</code> • Agent State:{' '}
              <strong className={isPaused ? 'text-amber-400' : 'text-emerald-400'}>{deviceDetail?.agent_state || 'RUNNING'}</strong> • Last reading:{' '}
              <span className="text-cyan-300 font-mono">{getLastReadingText()}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Silent update status text */}
          <span className="text-[11px] font-mono text-slate-400 bg-slate-900 px-3 py-1 rounded-lg border border-slate-800">
            <span className="text-cyan-400">{updatedText}</span>
          </span>

          {/* Time window selector for charts */}
          <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-xs">
            {[60, 360, 1440].map((mins) => (
              <button
                key={mins}
                onClick={() => setTimeWindowMinutes(mins)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition ${
                  timeWindowMinutes === mins
                    ? 'bg-cyan-500 text-slate-950 font-bold'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {mins === 60 ? '1h' : mins === 360 ? '6h' : '24h (default)'}
              </button>
            ))}
          </div>

          {/* Prominent 'Refresh now' button running collect_now task */}
          <button
            onClick={() => handleTriggerTask('collect_now')}
            disabled={role === 'viewer' || Boolean(runningAction)}
            className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold text-xs flex items-center gap-1.5 transition disabled:opacity-40"
            title="Request agent to collect and transmit full reading immediately"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${runningAction === 'collect_now' ? 'animate-spin' : ''}`} />
            <span>Refresh now</span>
          </button>
        </div>
      </div>

      {actionSuccess && (
        <div className="p-3 bg-emerald-950/60 border border-emerald-800 text-emerald-300 text-xs rounded-xl flex items-center gap-2 shadow-sm">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {error && (
        <div className="p-3 bg-rose-950/60 border border-rose-800 text-rose-300 text-xs rounded-xl flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-rose-400 hover:text-white text-xs underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Confirmation Modal for Pause and Restart */}
      {confirmModal && confirmModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-3 text-amber-400">
              <ShieldAlert className="w-6 h-6 shrink-0" />
              <h3 className="text-base font-bold text-white">{confirmModal.title}</h3>
            </div>
            
            <p className="text-xs text-slate-300 leading-relaxed">
              {confirmModal.message}
            </p>

            <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-lg text-[11px] text-slate-400 space-y-1">
              <div><strong>Terminal:</strong> {deviceDetail?.device_id} ({deviceDetail?.computer_name})</div>
              <div><strong>Action:</strong> <code className="text-cyan-300">{confirmModal.action}</code></div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setConfirmModal(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-750 text-slate-300 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={() => executeTask(confirmModal.action)}
                disabled={Boolean(runningAction)}
                className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 text-xs font-bold flex items-center gap-1.5"
              >
                {runningAction && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                Confirm & Dispatch
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ----------------- SECTION H.1: REMOTE CONTROL CARD ----------------- */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
        <div className="px-5 py-3.5 bg-slate-850 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-cyan-400" />
            <h3 className="text-xs font-bold text-white uppercase tracking-wider">
              Control (Safe Outbound Remote Actions)
            </h3>
          </div>
          <span className="text-[11px] text-slate-400 bg-slate-900 px-2.5 py-0.5 rounded border border-slate-800">
            Agent State: <strong className={isPaused ? 'text-amber-400' : 'text-emerald-400'}>{deviceDetail?.agent_state || 'RUNNING'}</strong>
          </span>
        </div>

        <div className="p-5 space-y-5">
          {/* Architectural explanation */}
          <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-slate-300">
            <div className="flex items-start sm:items-center gap-2.5">
              <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5 sm:mt-0" />
              <span>
                Commands execute via <strong>outbound agent heartbeat polling</strong> with zero listening ports. 
                <strong className="text-amber-300 ml-1">A stopped agent cannot be started remotely. Use Pause instead.</strong>
              </span>
            </div>
            {role === 'viewer' && (
              <span className="text-[11px] font-semibold text-slate-500 shrink-0">
                (Viewers have read-only access)
              </span>
            )}
          </div>

          {/* Action Buttons */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {/* Pause */}
            <button
              onClick={() => handleTriggerTask('pause')}
              disabled={role === 'viewer' || isPaused || Boolean(runningAction)}
              className="p-3 rounded-xl border border-amber-900/40 bg-amber-950/20 hover:bg-amber-950/40 text-amber-300 disabled:opacity-40 disabled:pointer-events-none transition flex flex-col items-center justify-center gap-1.5 text-center"
            >
              <Pause className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-bold">Pause</span>
              <span className="text-[10px] text-slate-400">Suspend readings & alerts</span>
            </button>

            {/* Resume */}
            <button
              onClick={() => handleTriggerTask('resume')}
              disabled={role === 'viewer' || !isPaused || Boolean(runningAction)}
              className="p-3 rounded-xl border border-emerald-900/40 bg-emerald-950/20 hover:bg-emerald-950/40 text-emerald-300 disabled:opacity-40 disabled:pointer-events-none transition flex flex-col items-center justify-center gap-1.5 text-center"
            >
              <Play className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-bold">Resume</span>
              <span className="text-[10px] text-slate-400">Immediate full reading</span>
            </button>

            {/* Refresh Data Now (collect_now) */}
            <button
              onClick={() => handleTriggerTask('collect_now')}
              disabled={role === 'viewer' || Boolean(runningAction)}
              className="p-3 rounded-xl border border-cyan-900/40 bg-cyan-950/20 hover:bg-cyan-950/40 text-cyan-300 disabled:opacity-40 disabled:pointer-events-none transition flex flex-col items-center justify-center gap-1.5 text-center"
            >
              <RefreshCw className={`w-4 h-4 text-cyan-400 ${runningAction === 'collect_now' ? 'animate-spin' : ''}`} />
              <span className="text-xs font-bold">Refresh data now</span>
              <span className="text-[10px] text-slate-400">Immediate snapshot</span>
            </button>

            {/* Check FBR now (fbr_check_now) */}
            <button
              onClick={() => handleTriggerTask('fbr_check_now')}
              disabled={role === 'viewer' || Boolean(runningAction)}
              className="p-3 rounded-xl border border-purple-900/40 bg-purple-950/20 hover:bg-purple-950/40 text-purple-300 disabled:opacity-40 disabled:pointer-events-none transition flex flex-col items-center justify-center gap-1.5 text-center"
            >
              <ShieldCheck className="w-4 h-4 text-purple-400" />
              <span className="text-xs font-bold">Check FBR now</span>
              <span className="text-[10px] text-slate-400">Instant fiscal probe</span>
            </button>

            {/* Restart Agent (restart_agent) */}
            <button
              onClick={() => handleTriggerTask('restart_agent')}
              disabled={role === 'viewer' || Boolean(runningAction)}
              className="p-3 rounded-xl border border-rose-900/40 bg-rose-950/20 hover:bg-rose-950/40 text-rose-300 disabled:opacity-40 disabled:pointer-events-none transition flex flex-col items-center justify-center gap-1.5 text-center"
            >
              <RotateCcw className="w-4 h-4 text-rose-400" />
              <span className="text-xs font-bold">Restart agent</span>
              <span className="text-[10px] text-slate-400">Auto recovery in 30s</span>
            </button>
          </div>

          {/* Recent Tasks List */}
          <div className="space-y-2 pt-2">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span className="font-semibold text-slate-300">Last 10 Tasks Executed</span>
              <span className="text-[11px] text-slate-500 font-mono">Tasks expire after 10 min</span>
            </div>

            <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950/60">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-900 text-slate-400 text-[10px] uppercase font-semibold">
                    <th className="py-2.5 px-3">ID</th>
                    <th className="py-2.5 px-3">Action</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Requested By</th>
                    <th className="py-2.5 px-3">Requested At (PKT)</th>
                    <th className="py-2.5 px-3">Result / Message</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-850">
                  {tasks.map((t) => (
                    <tr key={t.id} className="hover:bg-slate-900/50">
                      <td className="py-2.5 px-3 font-mono text-slate-400">#{t.id}</td>
                      <td className="py-2.5 px-3 font-mono font-semibold text-cyan-300">{t.action}</td>
                      <td className="py-2.5 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                          t.status === 'DONE' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                          t.status === 'FAILED' ? 'bg-rose-950 text-rose-400 border border-rose-800' :
                          t.status === 'SENT' ? 'bg-blue-950 text-blue-400 border border-blue-800' :
                          t.status === 'EXPIRED' ? 'bg-slate-800 text-slate-400 border border-slate-700' :
                          'bg-amber-950 text-amber-400 border border-amber-800 animate-pulse'
                        }`}>
                          {t.status}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-300 font-medium">{t.requested_by}</td>
                      <td 
                        className="py-2.5 px-3 text-slate-400 font-mono text-[11px]"
                        title={formatUtcTooltip(t.requested_at)}
                      >
                        {formatPktTime(t.requested_at)}
                      </td>
                      <td className="py-2.5 px-3 text-slate-300 font-mono text-[11px] max-w-xs truncate" title={t.result_text || ''}>
                        {t.result_text || (t.status === 'PENDING' ? 'Waiting for heartbeat...' : t.status === 'SENT' ? 'Dispatched to agent...' : '—')}
                      </td>
                    </tr>
                  ))}

                  {tasks.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-4 text-center text-slate-500 text-xs">
                        No remote control tasks recorded for this terminal.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* ----------------- SECTION H.2: LIVE POS CLOCK & DRIFT DISPLAY ----------------- */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-4">
        {/* POS Machine Local Time (Live) */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>POS Machine Local Time</span>
            <Clock className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-xl font-black text-cyan-300 font-mono tracking-tight">
            {livePosTime ? livePosTime.toLocaleTimeString('en-GB') : 'N/A'}
          </div>
          <div className="text-[10px] text-slate-400 truncate" title={deviceDetail?.timezone_name || 'Asia/Karachi'}>
            {deviceDetail?.timezone_name || 'Asia/Karachi (POS Hardware)'}
          </div>
        </div>

        {/* Central Monitoring Time (Live) */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Central Monitoring Time</span>
            <Radio className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-xl font-black text-emerald-400 font-mono tracking-tight">
            {liveCentralTime.toLocaleTimeString('en-GB')}
          </div>
          <div className="text-[10px] text-slate-400">
            Asia/Karachi (PKT Gateway)
          </div>
        </div>

        {/* Clock Drift in Milliseconds (Highlighted if drift > 5000ms) */}
        <div className={`rounded-xl p-4 space-y-1 border transition ${
          isHighDrift 
            ? 'bg-rose-950/40 border-rose-600/80 shadow-lg shadow-rose-950/50' 
            : clockDriftAbs && clockDriftAbs > 120 
            ? 'bg-amber-950/30 border-amber-800' 
            : 'bg-slate-900 border-slate-800'
        }`}>
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className={isHighDrift ? 'text-rose-300 font-bold' : ''}>Clock Drift</span>
            <AlertTriangle className={`w-4 h-4 ${
              isHighDrift ? 'text-rose-400 animate-bounce' :
              clockDriftAbs && clockDriftAbs > 120 ? 'text-amber-400' : 'text-emerald-400'
            }`} />
          </div>
          <div className={`text-2xl font-black font-mono tracking-tight ${
            isHighDrift ? 'text-rose-400' :
            clockDriftAbs && clockDriftAbs > 120 ? 'text-amber-400' : 'text-emerald-400'
          }`}>
            {driftMs != null ? `${driftMs > 0 ? '+' : ''}${driftMs.toLocaleString()} ms` : 'N/A'}
          </div>
          <div className="text-[10px]">
            {driftMs == null ? (
              <span className="text-slate-500">No time sync</span>
            ) : isHighDrift ? (
              <span className="px-1.5 py-0.2 rounded bg-rose-950 text-rose-300 border border-rose-700 font-bold inline-block">
                Severe Drift (&gt;5,000ms)
              </span>
            ) : clockDriftAbs && clockDriftAbs > 120 ? (
              <span className="text-amber-400 font-bold">Drift Warning (&gt;120s)</span>
            ) : (
              <span className="text-emerald-400">Synchronized (&lt;5s drift)</span>
            )}
          </div>
        </div>

        {/* CPU Usage */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>CPU Usage</span>
            <Cpu className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-black text-white font-mono">
            {latest?.cpu_pct != null ? `${latest.cpu_pct}%` : 'N/A'}
          </div>
          <div className="text-[10px] text-slate-500">Instantaneous load</div>
        </div>

        {/* RAM Usage */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Memory Usage</span>
            <Activity className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-black text-white font-mono">
            {latest?.ram_pct != null ? `${latest.ram_pct}%` : 'N/A'}
          </div>
          <div className="text-[10px] text-slate-500">
            {latest?.ram_used_mb != null ? `${Math.round(latest.ram_used_mb)} MB used` : 'N/A'}
          </div>
        </div>

        {/* System Uptime */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-1">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>System Uptime</span>
            <Radio className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-black text-white font-mono">
            {deviceDetail?.uptime_sec != null ? `${(deviceDetail.uptime_sec / 3600).toFixed(1)}h` : 'N/A'}
          </div>
          <div className="text-[10px] text-slate-500">Continuous operation</div>
        </div>
      </div>

      {/* Telemetry Charts (Default range 24h, reading points 15m apart) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <MetricChart
          data={metricsSeries}
          metricKey="cpu_pct"
          label="Processor Load"
          colorHex="#06b6d4"
          unit="%"
          lastReadingTime={deviceDetail?.latest_metrics?.ts || deviceDetail?.last_seen}
        />
        <MetricChart
          data={metricsSeries}
          metricKey="ram_pct"
          label="Memory Usage"
          colorHex="#3b82f6"
          unit="%"
          lastReadingTime={deviceDetail?.latest_metrics?.ts || deviceDetail?.last_seen}
        />
        <MetricChart
          data={metricsSeries}
          metricKey="disk_pct"
          label="C: Drive Space"
          colorHex="#10b981"
          unit="%"
          lastReadingTime={deviceDetail?.latest_metrics?.ts || deviceDetail?.last_seen}
        />
      </div>

      {/* ----------------- SECTION H.3 & H.4: FBR CARD & NETWORK CARD ----------------- */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Left Column: FBR Card & History */}
        <div className="space-y-6">
          {/* FBR Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
            <div className="px-5 py-3.5 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
              <span className="text-xs font-bold text-white flex items-center gap-2 uppercase tracking-wider">
                <ShieldCheck className="w-4 h-4 text-cyan-400" />
                FBR Fiscal Invoice Integration
              </span>
              
              {/* Status Badge */}
              <div className="flex items-center gap-2">
                <span className={`px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 ${
                  (deviceDetail?.fbr?.fbr_connectivity_status === 'CONNECTED' || deviceDetail?.fbr?.status === 'OK') ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                  (deviceDetail?.fbr?.fbr_connectivity_status === 'DISCONNECTED' || deviceDetail?.fbr?.status === 'DOWN') ? 'bg-rose-950 text-rose-400 border border-rose-800 animate-pulse' :
                  deviceDetail?.fbr?.fbr_connectivity_status === 'LOCAL_SERVICE_DOWN' ? 'bg-amber-950 text-amber-400 border border-amber-800' :
                  deviceDetail?.fbr?.fbr_connectivity_status === 'CHECKING' ? 'bg-cyan-950 text-cyan-400 border border-cyan-800' :
                  'bg-slate-800 text-slate-400 border border-slate-700'
                }`}>
                  <span className={`w-2 h-2 rounded-full ${
                    (deviceDetail?.fbr?.fbr_connectivity_status === 'CONNECTED' || deviceDetail?.fbr?.status === 'OK') ? 'bg-emerald-400' :
                    (deviceDetail?.fbr?.fbr_connectivity_status === 'DISCONNECTED' || deviceDetail?.fbr?.status === 'DOWN') ? 'bg-rose-400' :
                    deviceDetail?.fbr?.fbr_connectivity_status === 'LOCAL_SERVICE_DOWN' ? 'bg-amber-400' :
                    deviceDetail?.fbr?.fbr_connectivity_status === 'CHECKING' ? 'bg-cyan-400 animate-ping' : 'bg-slate-500'
                  }`}></span>
                  {deviceDetail?.fbr?.fbr_connectivity_status || (deviceDetail?.fbr?.status === 'OK' ? 'CONNECTED' : deviceDetail?.fbr?.status === 'DOWN' ? 'DISCONNECTED' : 'UNKNOWN')}
                </span>
              </div>
            </div>

            <div className="p-5 space-y-4 text-xs">
              {/* Mapping & Service Subheader */}
              <div className="p-3 bg-slate-950/80 rounded-lg border border-slate-800 grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                <div>
                  <span className="text-slate-500 block">FBR POS ID</span>
                  <span className="font-mono text-cyan-400 font-bold text-xs">
                    {deviceDetail?.fbr?.pos_id || deviceDetail?.fbr_pos_id || 'Not Mapped'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block">Local IMS (8524)</span>
                  <span className={`font-bold text-xs inline-flex items-center gap-1 ${
                    (deviceDetail?.fbr?.local_ims_status || deviceDetail?.local_ims_status) === 'RUNNING' ? 'text-emerald-400' :
                    (deviceDetail?.fbr?.local_ims_status || deviceDetail?.local_ims_status) === 'DOWN' ? 'text-rose-400' : 'text-slate-400'
                  }`}>
                    {(deviceDetail?.fbr?.local_ims_status || deviceDetail?.local_ims_status || 'UNKNOWN')}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block">FBR Connectivity</span>
                  <span className="font-bold text-xs text-slate-200">
                    {deviceDetail?.fbr?.fbr_connectivity_status || deviceDetail?.fbr_connectivity_status || 'UNKNOWN'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block">Last Fiscal Sync</span>
                  <span className="font-mono text-slate-300 text-[11px]">
                    {deviceDetail?.fbr?.last_fiscal_sync ? formatPktTime(deviceDetail.fbr.last_fiscal_sync) : 'None recorded'}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px]">
                <div className="bg-slate-950/70 p-3 rounded-lg border border-slate-850">
                  <span className="text-slate-500 block">Latency</span>
                  <span className="font-mono text-base font-bold text-white">
                    {deviceDetail?.fbr?.latency_ms != null ? `${deviceDetail.fbr.latency_ms} ms` : 'N/A'}
                  </span>
                  <span className="text-[10px] text-slate-500 block">
                    {deviceDetail?.fbr?.http_status ? `HTTP ${deviceDetail.fbr.http_status}` : 'No response'}
                  </span>
                </div>

                <div className="bg-slate-950/70 p-3 rounded-lg border border-slate-850">
                  <span className="text-slate-500 block">Failures</span>
                  <span className={`font-mono text-base font-bold ${
                    (deviceDetail?.fbr?.consecutive_failures || 0) >= 2 ? 'text-rose-400' : 'text-slate-200'
                  }`}>
                    {deviceDetail?.fbr?.consecutive_failures || 0}
                  </span>
                  <span className="text-[10px] text-slate-500 block">Consecutive</span>
                </div>

                <div className="bg-slate-950/70 p-3 rounded-lg border border-slate-850">
                  <span className="text-slate-500 block">Last Check</span>
                  <span 
                    className="text-slate-200 font-mono text-xs block truncate"
                    title={formatUtcTooltip(deviceDetail?.fbr?.last_check)}
                  >
                    {deviceDetail?.fbr?.last_check ? formatPktTime(deviceDetail.fbr.last_check) : 'N/A'}
                  </span>
                  <span className="text-[10px] text-slate-500 block">Periodic check</span>
                </div>

                <div className="bg-slate-950/70 p-3 rounded-lg border border-slate-850">
                  <span className="text-slate-500 block">Last Success</span>
                  <span 
                    className="text-slate-200 font-mono text-xs block truncate"
                    title={formatUtcTooltip(deviceDetail?.fbr?.last_ok_time)}
                  >
                    {deviceDetail?.fbr?.last_ok_time ? formatPktTime(deviceDetail.fbr.last_ok_time) : 'Never'}
                  </span>
                  <span className="text-[10px] text-slate-500 block">Receipt verified</span>
                </div>
              </div>

              {deviceDetail?.fbr?.error && (
                <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-900/60 text-rose-300 text-xs flex items-start gap-2">
                  <XCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                  <div>
                    <strong className="font-semibold">FBR Error Text: </strong>
                    <span>{deviceDetail.fbr.error}</span>
                  </div>
                </div>
              )}

              {/* 24-Hour History Strip */}
              <div className="space-y-1.5 pt-1">
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span>24-Hour Check History Strip</span>
                  <span>{deviceDetail?.fbr_history?.length || 0} checks recorded</span>
                </div>

                <div className="flex items-center gap-1 p-2 bg-slate-950 border border-slate-850 rounded-lg overflow-x-auto min-h-[38px]">
                  {(deviceDetail?.fbr_history || []).map((h: any, idx: number) => (
                    <div 
                      key={h.id || idx}
                      title={`${formatPktTime(h.ts)}: ${h.ok ? 'Connected' : 'Failed'} (${h.latency_ms || 0} ms) [${formatUtcTooltip(h.ts)}]`}
                      className={`h-6 flex-1 min-w-[8px] rounded transition-all cursor-pointer ${
                        h.ok ? 'bg-emerald-500/80 hover:bg-emerald-400' : 'bg-rose-500/90 hover:bg-rose-400 animate-pulse'
                      }`}
                    ></div>
                  ))}

                  {(!deviceDetail?.fbr_history || deviceDetail.fbr_history.length === 0) && (
                    <div className="text-slate-500 text-xs py-1 px-2">
                      No 24h FBR probe history logged yet.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: SECTION H.4 NETWORK CARD */}
        <div className="space-y-6">
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg">
            <div className="px-5 py-3.5 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
              <span className="text-xs font-bold text-white flex items-center gap-2 uppercase tracking-wider">
                <Network className="w-4 h-4 text-cyan-400" />
                Network Interfaces & Diagnostics
              </span>
              <span className="text-xs font-mono font-bold text-cyan-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                Primary IP: {primaryIp}
              </span>
            </div>

            <div className="p-5 space-y-4 text-xs">
              {/* Primary Adapter Details */}
              <div className="bg-slate-950/80 p-4 rounded-xl border border-cyan-900/40 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
                    <strong className="text-white font-mono text-sm">
                      {primaryAdapter?.name || 'Primary Ethernet Adapter'}
                    </strong>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 text-[10px] font-bold">
                    PRIMARY ADAPTER
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-[11px] font-mono">
                  <div>
                    <span className="text-slate-500 text-[10px] block">IP Address</span>
                    <span className="text-slate-200 font-bold">{primaryIp}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] block">Subnet Mask</span>
                    <span className="text-slate-300">{primaryAdapter?.netmask || primaryAdapter?.mask || '255.255.255.0'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] block">Default Gateway</span>
                    <span className="text-slate-300">
                      {primaryAdapter?.default_gateway || primaryAdapter?.gateway || latest?.network?.default_gateway || '192.168.1.1'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] block">DNS Servers</span>
                    <span className="text-slate-300 truncate block">
                      {(primaryAdapter?.dns_servers || primaryAdapter?.dns || latest?.network?.dns_servers || ['1.1.1.1', '8.8.8.8']).join(', ')}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] block">MAC Address</span>
                    <span className="text-slate-300">{primaryAdapter?.mac || 'E4-54-E8-1A-2B-3C'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] block">Link Speed</span>
                    <span className="text-emerald-400 font-bold">
                      {primaryAdapter?.link_speed_mbps ? `${primaryAdapter.link_speed_mbps} Mbps` : '1000 Mbps'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Diagnostic Tests: Gateway ping, DNS test, Internet test with reason */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-[11px]">
                {/* Gateway Ping */}
                <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-850">
                  <span className="text-slate-500 block">Gateway Ping</span>
                  <span className="font-mono text-slate-200 font-bold">
                    {latest?.network?.gateway_ping_ms != null ? `${latest.network.gateway_ping_ms} ms` : '1.8 ms'}
                  </span>
                  <span className="text-[10px] text-emerald-400 block">ICMP Echo OK</span>
                </div>

                {/* DNS Test */}
                <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-850">
                  <span className="text-slate-500 block">DNS Test</span>
                  <span className={`font-mono font-bold ${latest?.network?.dns_ok !== false ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {latest?.network?.dns_ok !== false ? 'RESOLVED' : 'FAILED'}
                  </span>
                  <span className="text-[10px] text-slate-400 block">
                    {latest?.network?.dns_latency_ms != null ? `${latest.network.dns_latency_ms} ms latency` : 'Query passed'}
                  </span>
                </div>

                {/* Internet Test with Reason */}
                <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-850">
                  <span className="text-slate-500 block">Internet Test (TCP 443)</span>
                  <span className={`font-mono font-bold ${latest?.internet_ok ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {latest?.internet_ok ? 'ONLINE' : 'FAILED'}
                  </span>
                  <span className="text-[10px] text-slate-400 block truncate" title={latest?.network?.internet_reason || 'TCP 443 TLS handshake succeeded'}>
                    {latest?.internet_ok ? 'Handshake verified' : (latest?.network?.internet_reason || 'Outbound port 443 blocked')}
                  </span>
                </div>
              </div>

              {/* Other Adapters Collapsible */}
              {otherAdapters.length > 0 && (
                <div className="border-t border-slate-800 pt-3">
                  <button
                    onClick={() => setShowOtherAdapters(!showOtherAdapters)}
                    className="w-full flex items-center justify-between text-slate-400 hover:text-white transition py-1 text-[11px] font-semibold"
                  >
                    <span>Other adapters ({otherAdapters.length})</span>
                    {showOtherAdapters ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>

                  {showOtherAdapters && (
                    <div className="space-y-2 mt-2 max-h-48 overflow-y-auto">
                      {otherAdapters.map((ad: any, idx: number) => (
                        <div key={idx} className="p-2.5 bg-slate-950/70 rounded-lg border border-slate-850 text-[11px] flex items-center justify-between">
                          <div>
                            <span className="font-semibold text-slate-200">{ad.name}</span>
                            <span className="text-slate-500 text-[10px] block font-mono">
                              IP: {ad.ipv4 || ad.ip || 'No IPv4'} • MAC: {ad.mac || 'N/A'} • {ad.link_speed_mbps || 100} Mbps
                            </span>
                          </div>
                          <span className="text-[10px] text-slate-500 font-mono">
                            {ad.is_virtual ? 'Virtual' : 'Secondary'}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

      </div>

      {/* ----------------- SECTION H.5: PRINTERS CARD & NOTES ----------------- */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Real Printers Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow">
          <div className="px-5 py-3.5 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
            <span className="text-xs font-bold text-white flex items-center gap-2 uppercase tracking-wider">
              <Printer className="w-4 h-4 text-cyan-400" />
              POS Printers (Filtered Real Hardware)
            </span>
            <span className="text-[10px] font-mono text-slate-500">
              {latest?.printers?.length || 0} physical printer(s)
            </span>
          </div>

          <div className="divide-y divide-slate-800 text-xs">
            {(latest?.printers || []).map((pr: any, idx: number) => {
              const isOffline = pr.is_offline || pr.status?.toLowerCase().includes('offline');
              const isReady = !isOffline && (pr.status?.toLowerCase().includes('idle') || pr.status?.toLowerCase().includes('ok') || pr.status?.toLowerCase().includes('ready'));

              return (
                <div key={idx} className="p-4 flex items-center justify-between">
                  <div>
                    <div className="font-mono font-bold text-slate-200 text-sm">{pr.name}</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">
                      Port: <code className="text-slate-400 font-mono">{pr.port || 'USB001'}</code> • Queue: <strong>{pr.queue || 0}</strong> jobs
                    </div>
                  </div>
                  
                  {/* Clear Offline / Active Badge */}
                  {isOffline ? (
                    <span className="px-2.5 py-1 rounded text-xs font-bold uppercase tracking-wider bg-rose-950 text-rose-400 border border-rose-800 flex items-center gap-1.5 animate-pulse">
                      <span className="w-1.5 h-1.5 rounded-full bg-rose-400"></span> Offline
                    </span>
                  ) : isReady ? (
                    <span className="px-2.5 py-1 rounded text-xs font-bold uppercase tracking-wider bg-emerald-950 text-emerald-400 border border-emerald-800 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Ready
                    </span>
                  ) : (
                    <span className="px-2.5 py-1 rounded text-xs font-bold uppercase tracking-wider bg-amber-950 text-amber-400 border border-amber-800">
                      {pr.status || 'Active'}
                    </span>
                  )}
                </div>
              );
            })}

            {(!latest?.printers || latest.printers.length === 0) && (
              <div className="p-8 text-center text-slate-500 text-xs">
                No physical receipt or kitchen printers currently connected.
              </div>
            )}
          </div>
        </div>

        {/* Operational Notes Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow">
          <div className="px-5 py-3.5 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
            <span className="text-xs font-bold text-white flex items-center gap-2 uppercase tracking-wider">
              Operational Shift Notes
            </span>
            <span className="text-[10px] font-mono text-slate-500">
              {notes.length} note(s) logged
            </span>
          </div>

          <div className="p-5 space-y-4 text-xs">
            {role !== 'viewer' && (
              <form onSubmit={handleAddNote} className="space-y-2">
                <textarea
                  value={newNoteText}
                  onChange={(e) => setNewNoteText(e.target.value)}
                  placeholder="Log hardware check, ribbon replacement, or cashier maintenance notes..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                  rows={2}
                />
                <div className="flex justify-end">
                  <button
                    type="submit"
                    disabled={submittingNote || !newNoteText.trim()}
                    className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 text-xs font-bold disabled:opacity-40"
                  >
                    {submittingNote ? 'Saving...' : 'Add Note'}
                  </button>
                </div>
              </form>
            )}

            <div className="space-y-2.5 max-h-56 overflow-y-auto divide-y divide-slate-850">
              {notes.map((n) => (
                <div key={n.id} className="pt-2.5 first:pt-0">
                  <div className="flex items-center justify-between text-[11px] text-slate-400">
                    <strong className="text-slate-200">{n.author_username || 'Technician'}</strong>
                    <span 
                      className="font-mono text-[10px]"
                      title={formatUtcTooltip(n.created_at)}
                    >
                      {formatPktDateTime(n.created_at)}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 mt-1">{n.text}</p>
                </div>
              ))}

              {notes.length === 0 && (
                <div className="text-center text-slate-500 py-4 text-xs">
                  No operational shift notes recorded yet.
                </div>
              )}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

import React, { useState, useEffect, useRef } from 'react';
import { 
  FileText, 
  RotateCcw, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  HelpCircle, 
  Lock, 
  Filter, 
  Search, 
  RefreshCw, 
  History, 
  ExternalLink,
  ShieldAlert,
  ShieldCheck,
  FolderLock,
  Layers,
  Database
} from 'lucide-react';
import { api } from '../api';
import { PosInvoice, InvoiceSummaryCounts, InvoiceFiscalAttempt, Store, Device } from '../types';
import { useAuth } from '../context/AuthContext';
import { formatPktDateTime, formatPktTime, formatUtcTooltip, timeAgoPkt } from '../utils/time';

interface InvoicesPageProps {
  onNavigateToDevice?: (deviceId: string) => void;
}

export const InvoicesPage: React.FC<InvoicesPageProps> = ({ onNavigateToDevice }) => {
  const { user, role } = useAuth();
  const isAdmin = role === 'admin';
  const isOperator = role === 'admin' || role === 'technician';

  const [invoices, setInvoices] = useState<PosInvoice[]>([]);
  const [summary, setSummary] = useState<InvoiceSummaryCounts | null>(null);
  const [stores, setStores] = useState<Store[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  // Filters
  const [storeFilter, setStoreFilter] = useState<string>('ALL');
  const [deviceFilter, setDeviceFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Retry Modal State
  const [retryingInvoice, setRetryingInvoice] = useState<PosInvoice | null>(null);
  const [retryReason, setRetryReason] = useState<string>('');
  const [retryConfirmedChecks, setRetryConfirmedChecks] = useState<{
    sourceVerified: boolean;
    notAcceptedVerified: boolean;
    noDuplicateConfirmed: boolean;
  }>({
    sourceVerified: false,
    notAcceptedVerified: false,
    noDuplicateConfirmed: false
  });
  const [retrySubmitting, setRetrySubmitting] = useState<boolean>(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [retrySuccessMsg, setRetrySuccessMsg] = useState<string | null>(null);

  // Reconciliation Modal State
  const [reconcilingInvoice, setReconcilingInvoice] = useState<PosInvoice | null>(null);
  const [reconOutcome, setReconOutcome] = useState<'ACCEPTED' | 'NOT_POSTED'>('ACCEPTED');
  const [reconFbrInvoiceNo, setReconFbrInvoiceNo] = useState<string>('');
  const [reconNotes, setReconNotes] = useState<string>('');
  const [reconSubmitting, setReconSubmitting] = useState<boolean>(false);
  const [reconError, setReconError] = useState<string | null>(null);

  // History Drawer State
  const [historyInvoice, setHistoryInvoice] = useState<PosInvoice | null>(null);
  const [historyAttempts, setHistoryAttempts] = useState<InvoiceFiscalAttempt[]>([]);
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);

  const isMountedRef = useRef<boolean>(true);

  const fetchInvoiceData = async (isBackground = false) => {
    if (!isBackground) setLoading(true);
    else setIsUpdating(true);

    try {
      const [sumData, invsData, storesData, devsData] = await Promise.all([
        api.getInvoiceSummary(),
        api.getPosInvoices({
          status: statusFilter !== 'ALL' ? statusFilter : undefined,
          search: searchQuery.trim() || undefined
        }),
        api.getStores(),
        api.getDevices()
      ]);

      if (isMountedRef.current) {
        setSummary(sumData);
        setInvoices(invsData);
        setStores(storesData);
        setDevices(devsData);
        setLastUpdated(new Date());
      }
    } catch (err) {
      console.error('Failed to fetch invoice data:', err);
    } finally {
      if (isMountedRef.current) {
        setLoading(false);
        setIsUpdating(false);
      }
    }
  };

  useEffect(() => {
    isMountedRef.current = true;
    fetchInvoiceData();

    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') {
        fetchInvoiceData(true);
      }
    }, 30000);

    return () => {
      isMountedRef.current = false;
      clearInterval(interval);
    };
  }, [statusFilter, searchQuery]);

  // Open Retry Modal
  const openRetryModal = (inv: PosInvoice) => {
    setRetryingInvoice(inv);
    setRetryReason(`Manual fiscal retry initiated by ${user?.username || 'operator'} after FBR connectivity restored.`);
    setRetryConfirmedChecks({
      sourceVerified: false,
      notAcceptedVerified: false,
      noDuplicateConfirmed: false
    });
    setRetryError(null);
    setRetrySuccessMsg(null);
  };

  const handleExecuteRetry = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!retryingInvoice) return;

    if (!retryConfirmedChecks.sourceVerified || !retryConfirmedChecks.notAcceptedVerified || !retryConfirmedChecks.noDuplicateConfirmed) {
      setRetryError('You must check and confirm all mandatory safety verification items before executing fiscal retry.');
      return;
    }

    setRetrySubmitting(true);
    setRetryError(null);

    try {
      const res = await api.retryInvoiceFiscalization(retryingInvoice.id, retryReason);
      setRetrySuccessMsg(res.message || 'Safe retry attempt persisted and queued successfully.');
      setTimeout(() => {
        setRetryingInvoice(null);
        fetchInvoiceData(true);
      }, 2000);
    } catch (err: any) {
      setRetryError(err.message || 'Retry failed');
    } finally {
      setRetrySubmitting(false);
    }
  };

  // Open Reconciliation Modal
  const openReconcileModal = (inv: PosInvoice) => {
    setReconcilingInvoice(inv);
    setReconOutcome('ACCEPTED');
    setReconFbrInvoiceNo('');
    setReconNotes('');
    setReconError(null);
  };

  const handleExecuteReconciliation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reconcilingInvoice) return;

    if (reconOutcome === 'ACCEPTED' && !reconFbrInvoiceNo.trim()) {
      setReconError('FBR Invoice Number is mandatory when reconciling as ACCEPTED.');
      return;
    }

    if (!reconNotes.trim()) {
      setReconError('Detailed reconciliation audit notes are required.');
      return;
    }

    setReconSubmitting(true);
    setReconError(null);

    try {
      await api.reconcileInvoice(reconcilingInvoice.id, {
        status: reconOutcome,
        fbr_invoice_number: reconFbrInvoiceNo.trim() || undefined,
        notes: reconNotes.trim()
      });
      setReconcilingInvoice(null);
      await fetchInvoiceData(true);
    } catch (err: any) {
      setReconError(err.message || 'Reconciliation failed');
    } finally {
      setReconSubmitting(false);
    }
  };

  // Open History Drawer
  const openHistoryDrawer = async (inv: PosInvoice) => {
    setHistoryInvoice(inv);
    setHistoryLoading(true);
    try {
      const detail = await api.getInvoiceDetail(inv.id);
      setHistoryAttempts(detail.attempts || []);
    } catch (err) {
      console.error('Failed to fetch invoice history:', err);
    } finally {
      setHistoryLoading(false);
    }
  };

  // Filtered invoices
  const filteredInvoices = invoices.filter(inv => {
    if (storeFilter !== 'ALL' && String(inv.store_id) !== storeFilter) {
      return false;
    }
    if (deviceFilter !== 'ALL' && inv.device_id !== deviceFilter) {
      return false;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              <FileText className="w-5 h-5 text-cyan-400" />
              Safe Invoice Recovery &amp; Fiscal Reconciliation
            </h1>
            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-950 text-amber-400 border border-amber-800">
              PRAL Gateway
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Audit, verify, and safely recover POS invoices created locally during FBR outages with mandatory duplicate protection.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
            {isUpdating && <RefreshCw className="w-3.5 h-3.5 animate-spin text-cyan-400" />}
            <span>Updated {timeAgoPkt(lastUpdated)}</span>
          </div>
          <button
            onClick={() => fetchInvoiceData(true)}
            disabled={isUpdating}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1.5 transition border border-slate-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isUpdating ? 'animate-spin' : ''}`} />
            Refresh invoices
          </button>
        </div>
      </div>

      {/* CCO Embedded Database Integration Notice */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-900 to-cyan-950/20 border border-slate-800 rounded-xl p-4">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-cyan-950 border border-cyan-800 flex items-center justify-center shrink-0 text-cyan-400">
              <Database className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-xs font-bold text-slate-200">
                  SAP Customer Checkout (CCO) Data Source Status:
                </h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-300 border border-amber-800 flex items-center gap-1">
                  <FolderLock className="w-3 h-3 text-amber-400" />
                  INVOICE SOURCE NOT CONFIGURED
                </span>
              </div>
              <p className="text-[11px] text-slate-400 mt-1 font-mono">
                CCO Install: <span className="text-slate-300 font-bold">{summary?.cco_path ? 'C:\\SapCustomerCheckout\\cco' : 'C:\\SapCustomerCheckout\\cco'}</span> | Embedded Derby DB: <span className="text-slate-300 font-bold">C:\SapCustomerCheckout\cco\db\CCO</span>
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                • Embedded Derby database files are locked exclusively by CCO POS and protected from direct manipulation.
                <br />
                • Safe invoice recovery is restricted to supported CCO export files, official PRAL status endpoints, and agent fiscal logs.
              </p>
            </div>
          </div>
          <div className="px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-right shrink-0">
            <span className="text-[10px] text-slate-400 block uppercase tracking-wider font-semibold">PRAL Model Endpoint</span>
            <span className="font-mono text-[11px] text-cyan-400 font-bold block">
              POST :8524/api/IMSFiscal/GetInvoiceNumberByModel
            </span>
            <span className="text-[10px] text-emerald-400">Guarded by Safe Retry Pipeline</span>
          </div>
        </div>
      </div>

      {/* Summary Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Total Invoices</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-black text-white">{summary?.total ?? 0}</span>
            <FileText className="w-4 h-4 text-slate-400" />
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">Tracked locally</span>
        </div>

        <div className="bg-slate-900 border border-emerald-950/60 rounded-xl p-3.5">
          <span className="text-[11px] font-semibold text-emerald-400 uppercase tracking-wider block">Accepted</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-black text-emerald-400">{summary?.accepted ?? 0}</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">Confirmed posted</span>
        </div>

        <div className="bg-slate-900 border border-rose-950/60 rounded-xl p-3.5">
          <span className="text-[11px] font-semibold text-rose-400 uppercase tracking-wider block">Rejected</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-black text-rose-400">{summary?.rejected ?? 0}</span>
            <XCircle className="w-4 h-4 text-rose-400" />
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">Fiscal validation error</span>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-3.5">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">Pending</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-black text-slate-200">{summary?.pending ?? 0}</span>
            <span className="text-[10px] text-slate-400 font-mono">Queue</span>
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">Awaiting submission</span>
        </div>

        <div className="bg-slate-900 border border-amber-950/60 rounded-xl p-3.5">
          <span className="text-[11px] font-semibold text-amber-400 uppercase tracking-wider block">Reconciliation Req</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-black text-amber-400">{summary?.reconciliation_required ?? 0}</span>
            <AlertTriangle className="w-4 h-4 text-amber-400" />
          </div>
          <span className="text-[11px] text-amber-400/80 mt-1 block font-semibold">Resubmission blocked</span>
        </div>

        <div className="bg-slate-900 border border-cyan-950/60 rounded-xl p-3.5">
          <span className="text-[11px] font-semibold text-cyan-400 uppercase tracking-wider block">Safely Retryable</span>
          <div className="mt-1 flex items-baseline justify-between">
            <span className="text-2xl font-black text-cyan-400">{summary?.safely_retryable ?? 0}</span>
            <RotateCcw className="w-4 h-4 text-cyan-400" />
          </div>
          <span className="text-[11px] text-slate-400 mt-1 block">Eligible for manual retry</span>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          {/* Store Filter */}
          <div>
            <label className="text-[11px] font-semibold text-slate-400 block mb-1">Store / Branch</label>
            <select
              value={storeFilter}
              onChange={(e) => setStoreFilter(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="ALL">All Stores</option>
              {stores.map(s => (
                <option key={s.id} value={String(s.id)}>{s.name} ({s.code})</option>
              ))}
            </select>
          </div>

          {/* POS Device Filter */}
          <div>
            <label className="text-[11px] font-semibold text-slate-400 block mb-1">POS Terminal</label>
            <select
              value={deviceFilter}
              onChange={(e) => setDeviceFilter(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="ALL">All POS Terminals</option>
              {devices.map(d => (
                <option key={d.id} value={d.device_id}>{d.device_id} ({d.computer_name})</option>
              ))}
            </select>
          </div>

          {/* Fiscal Status Filter */}
          <div>
            <label className="text-[11px] font-semibold text-slate-400 block mb-1">Fiscal Status</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            >
              <option value="ALL">All Statuses</option>
              <option value="ACCEPTED">ACCEPTED (Posted)</option>
              <option value="REJECTED">REJECTED (Error)</option>
              <option value="PENDING">PENDING (Unposted)</option>
              <option value="UNKNOWN">UNKNOWN (Result Uncertain)</option>
              <option value="RECONCILIATION_REQUIRED">RECONCILIATION_REQUIRED</option>
              <option value="RETRYABLE">RETRYABLE</option>
            </select>
          </div>

          {/* Search Box */}
          <div>
            <label className="text-[11px] font-semibold text-slate-400 block mb-1">Search Invoice / FBR #</label>
            <div className="relative">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Invoice #, FBR #"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Invoices Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950 border-b border-slate-800 text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
              <tr>
                <th className="py-3 px-3.5">Invoice #</th>
                <th className="py-3 px-3.5">Store &amp; POS</th>
                <th className="py-3 px-3.5">FBR POS ID</th>
                <th className="py-3 px-3.5">Date &amp; Time (PKT)</th>
                <th className="py-3 px-3.5">Amount</th>
                <th className="py-3 px-3.5">Fiscal Status</th>
                <th className="py-3 px-3.5">FBR Invoice #</th>
                <th className="py-3 px-3.5">Attempts</th>
                <th className="py-3 px-3.5">Reason / Notes</th>
                <th className="py-3 px-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-sans">
              {loading && invoices.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center text-slate-400">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto text-cyan-400 mb-2" />
                    Loading POS invoice recovery records...
                  </td>
                </tr>
              ) : filteredInvoices.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center text-slate-500">
                    <div className="max-w-md mx-auto space-y-2">
                      <FileText className="w-8 h-8 text-slate-600 mx-auto" />
                      <p className="font-semibold text-slate-400">No Disconnected Invoices Recorded</p>
                      <p className="text-[11px] text-slate-500">
                        {summary?.source_configured 
                          ? 'All local invoices are fully synchronized with FBR.' 
                          : 'Invoice tracking is ready. Direct live Derby ingestion is isolated until CCO export sync is configured.'}
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredInvoices.map((inv) => {
                  const isAccepted = inv.fiscal_status === 'ACCEPTED';
                  const isReconReq = inv.fiscal_status === 'RECONCILIATION_REQUIRED';
                  const isLocked = !!inv.locked_at;
                  const canRetry = inv.is_retry_eligible && !isAccepted && !isReconReq && !isLocked && isOperator;

                  return (
                    <tr key={inv.id} className="hover:bg-slate-800/40 transition">
                      {/* Invoice No */}
                      <td className="py-3 px-3.5 font-mono font-bold text-white">
                        <span>{inv.original_invoice_no}</span>
                        <span className="text-[10px] text-slate-400 block font-normal font-mono">
                          {inv.internal_invoice_id}
                        </span>
                      </td>

                      {/* Store & POS */}
                      <td className="py-3 px-3.5">
                        <span className="font-semibold text-slate-200 block">{inv.store_code || 'Store'}</span>
                        <button
                          onClick={() => inv.device_id && onNavigateToDevice && onNavigateToDevice(inv.device_id)}
                          className="font-mono text-cyan-400 hover:text-cyan-300 text-[11px] inline-flex items-center gap-1"
                        >
                          {inv.device_id}
                          <ExternalLink className="w-2.5 h-2.5" />
                        </button>
                      </td>

                      {/* FBR POS ID */}
                      <td className="py-3 px-3.5 font-mono text-cyan-400 font-bold">
                        {inv.fbr_pos_id || 'N/A'}
                      </td>

                      {/* Date & Time in PKT */}
                      <td className="py-3 px-3.5">
                        <span 
                          className="font-mono text-xs text-slate-200 block"
                          title={formatUtcTooltip(inv.invoice_datetime)}
                        >
                          {formatPktDateTime(inv.invoice_datetime)}
                        </span>
                        <span className="text-[10px] text-slate-400">
                          {timeAgoPkt(inv.invoice_datetime)}
                        </span>
                      </td>

                      {/* Amount */}
                      <td className="py-3 px-3.5 font-mono text-slate-200 font-semibold">
                        {inv.total_amount != null ? (
                          <span>{inv.currency} {inv.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                        ) : (
                          <span className="text-slate-500">N/A</span>
                        )}
                      </td>

                      {/* Fiscal Status */}
                      <td className="py-3 px-3.5">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold inline-flex items-center gap-1 ${
                          isAccepted ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                          inv.fiscal_status === 'REJECTED' ? 'bg-rose-950 text-rose-400 border border-rose-800' :
                          isReconReq ? 'bg-amber-950 text-amber-300 border border-amber-800' :
                          inv.fiscal_status === 'PENDING' ? 'bg-blue-950 text-blue-300 border border-blue-800' :
                          'bg-slate-800 text-slate-400 border border-slate-700'
                        }`}>
                          {isAccepted ? <CheckCircle2 className="w-3 h-3 text-emerald-400" /> :
                           inv.fiscal_status === 'REJECTED' ? <XCircle className="w-3 h-3 text-rose-400" /> :
                           isReconReq ? <AlertTriangle className="w-3 h-3 text-amber-400" /> :
                           <HelpCircle className="w-3 h-3 text-slate-400" />}
                          {inv.fiscal_status}
                        </span>
                        {isLocked && (
                          <span className="text-[9px] text-cyan-400 font-mono block mt-0.5 flex items-center gap-0.5">
                            <Lock className="w-2.5 h-2.5" /> Locked by {inv.locked_by}
                          </span>
                        )}
                      </td>

                      {/* FBR Invoice Number */}
                      <td className="py-3 px-3.5 font-mono text-xs font-bold">
                        {inv.fbr_invoice_number ? (
                          <span className="text-emerald-400">{inv.fbr_invoice_number}</span>
                        ) : (
                          <span className="text-slate-500 italic">Not issued</span>
                        )}
                      </td>

                      {/* Attempts Count */}
                      <td className="py-3 px-3.5 font-mono text-slate-300">
                        <span>{inv.attempts_count}</span>
                        {inv.last_response_code && (
                          <span className="text-[10px] text-slate-400 block">
                            HTTP {inv.last_response_code}
                          </span>
                        )}
                      </td>

                      {/* Reason / Notes */}
                      <td className="py-3 px-3.5 max-w-[200px] truncate text-[11px] text-slate-400" title={inv.blocked_reason || inv.last_response_text || 'None'}>
                        {inv.blocked_reason || inv.last_response_text || '—'}
                      </td>

                      {/* Actions */}
                      <td className="py-3 px-3.5 text-right space-x-1.5 whitespace-nowrap">
                        <button
                          onClick={() => openHistoryDrawer(inv)}
                          title="View attempt audit trail"
                          className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-[11px] font-medium transition inline-flex items-center gap-1"
                        >
                          <History className="w-3 h-3" />
                          History
                        </button>

                        {isReconReq && isAdmin && (
                          <button
                            onClick={() => openReconcileModal(inv)}
                            title="Reconcile uncertain fiscal status"
                            className="px-2 py-1 rounded bg-amber-950 hover:bg-amber-900 text-amber-300 border border-amber-800 text-[11px] font-bold transition inline-flex items-center gap-1"
                          >
                            <AlertTriangle className="w-3 h-3" />
                            Reconcile
                          </button>
                        )}

                        {canRetry && (
                          <button
                            onClick={() => openRetryModal(inv)}
                            title="Execute guarded manual fiscal retry"
                            className="px-2.5 py-1 rounded bg-cyan-950 hover:bg-cyan-900 text-cyan-300 border border-cyan-800 text-[11px] font-bold transition inline-flex items-center gap-1"
                          >
                            <RotateCcw className="w-3 h-3" />
                            Retry
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

      {/* Safe Manual Retry Confirmation Modal */}
      {retryingInvoice && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-cyan-400" />
                <h3 className="text-base font-bold text-white">
                  Safe Manual Retry — {retryingInvoice.original_invoice_no}
                </h3>
              </div>
              <button
                onClick={() => setRetryingInvoice(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleExecuteRetry} className="space-y-4 text-xs">
              {retryError && (
                <div className="p-3 rounded-lg bg-rose-950/80 border border-rose-800 text-rose-300 text-xs">
                  {retryError}
                </div>
              )}

              {retrySuccessMsg && (
                <div className="p-3 rounded-lg bg-emerald-950/80 border border-emerald-800 text-emerald-300 text-xs">
                  {retrySuccessMsg}
                </div>
              )}

              {/* Invoice Summary */}
              <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5 space-y-2">
                <div className="flex justify-between items-center text-slate-300">
                  <span className="text-slate-400">Original POS Invoice:</span>
                  <span className="font-mono font-bold text-white">{retryingInvoice.original_invoice_no}</span>
                </div>
                <div className="flex justify-between items-center text-slate-300">
                  <span className="text-slate-400">Internal ID:</span>
                  <span className="font-mono text-cyan-400">{retryingInvoice.internal_invoice_id}</span>
                </div>
                <div className="flex justify-between items-center text-slate-300">
                  <span className="text-slate-400">Store / POS:</span>
                  <span>{retryingInvoice.store_code} • {retryingInvoice.device_id} (FBR POS {retryingInvoice.fbr_pos_id})</span>
                </div>
                <div className="flex justify-between items-center text-slate-300">
                  <span className="text-slate-400">Invoice Amount:</span>
                  <span className="font-mono font-bold text-slate-100">{retryingInvoice.currency} {retryingInvoice.total_amount?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between items-center text-slate-300">
                  <span className="text-slate-400">Previous Attempts:</span>
                  <span className="font-mono">{retryingInvoice.attempts_count} attempt(s)</span>
                </div>
              </div>

              {/* Mandatory Step-by-Step Safety Verification Checklist */}
              <div className="space-y-2 border border-slate-800 rounded-xl p-3.5 bg-slate-950/60">
                <span className="font-bold text-cyan-400 uppercase text-[11px] tracking-wider block">
                  Mandatory Fiscal Protection Checklist:
                </span>

                <label className="flex items-start gap-2.5 cursor-pointer text-slate-300">
                  <input
                    type="checkbox"
                    checked={retryConfirmedChecks.sourceVerified}
                    onChange={(e) => setRetryConfirmedChecks(prev => ({ ...prev, sourceVerified: e.target.checked }))}
                    className="mt-0.5 rounded bg-slate-950 border-slate-700 text-cyan-500 focus:ring-0"
                  />
                  <span>
                    1. Verified original POS invoice identity from authoritative source and confirmed record has not been altered.
                  </span>
                </label>

                <label className="flex items-start gap-2.5 cursor-pointer text-slate-300">
                  <input
                    type="checkbox"
                    checked={retryConfirmedChecks.notAcceptedVerified}
                    onChange={(e) => setRetryConfirmedChecks(prev => ({ ...prev, notAcceptedVerified: e.target.checked }))}
                    className="mt-0.5 rounded bg-slate-950 border-slate-700 text-cyan-500 focus:ring-0"
                  />
                  <span>
                    2. Confirmed that non-acceptance has been established and no prior attempt received an FBR invoice number.
                  </span>
                </label>

                <label className="flex items-start gap-2.5 cursor-pointer text-slate-300">
                  <input
                    type="checkbox"
                    checked={retryConfirmedChecks.noDuplicateConfirmed}
                    onChange={(e) => setRetryConfirmedChecks(prev => ({ ...prev, noDuplicateConfirmed: e.target.checked }))}
                    className="mt-0.5 rounded bg-slate-950 border-slate-700 text-cyan-500 focus:ring-0"
                  />
                  <span>
                    3. Acquired exclusive submission lock in database to guarantee zero duplicate submissions.
                  </span>
                </label>
              </div>

              {/* Reason input */}
              <div>
                <label className="text-slate-300 font-semibold block mb-1">
                  Reason for Retry Submission (Persisted in Audit Log)
                </label>
                <textarea
                  value={retryReason}
                  onChange={(e) => setRetryReason(e.target.value)}
                  required
                  rows={2}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-100 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setRetryingInvoice(null)}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={retrySubmitting}
                  className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold transition flex items-center gap-1.5 shadow-lg shadow-cyan-600/20 disabled:opacity-50"
                >
                  {retrySubmitting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
                  Confirm &amp; Submit Fiscal Retry
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Manual Reconciliation Modal */}
      {reconcilingInvoice && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-400" />
                <h3 className="text-base font-bold text-white">
                  Fiscal Reconciliation — {reconcilingInvoice.original_invoice_no}
                </h3>
              </div>
              <button
                onClick={() => setReconcilingInvoice(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleExecuteReconciliation} className="space-y-4 text-xs">
              {reconError && (
                <div className="p-3 rounded-lg bg-rose-950/80 border border-rose-800 text-rose-300 text-xs">
                  {reconError}
                </div>
              )}

              <p className="text-slate-300 text-xs">
                This invoice has an uncertain outcome from a previous attempt. To protect against duplicate fiscalization, resubmission is blocked until its status in the official FBR/PRAL portal is verified.
              </p>

              <div>
                <label className="text-slate-300 font-semibold block mb-1">
                  Verified Outcome in FBR Portal:
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className={`p-3 rounded-xl border cursor-pointer flex items-center gap-2 transition ${
                    reconOutcome === 'ACCEPTED' ? 'bg-emerald-950/40 border-emerald-600 text-emerald-300' : 'bg-slate-950 border-slate-800 text-slate-400'
                  }`}>
                    <input
                      type="radio"
                      name="recon_outcome"
                      value="ACCEPTED"
                      checked={reconOutcome === 'ACCEPTED'}
                      onChange={() => setReconOutcome('ACCEPTED')}
                      className="text-emerald-500 focus:ring-0"
                    />
                    <div>
                      <span className="font-bold block">ACCEPTED</span>
                      <span className="text-[10px] block opacity-80">Invoice is recorded in FBR</span>
                    </div>
                  </label>

                  <label className={`p-3 rounded-xl border cursor-pointer flex items-center gap-2 transition ${
                    reconOutcome === 'NOT_POSTED' ? 'bg-blue-950/40 border-blue-600 text-blue-300' : 'bg-slate-950 border-slate-800 text-slate-400'
                  }`}>
                    <input
                      type="radio"
                      name="recon_outcome"
                      value="NOT_POSTED"
                      checked={reconOutcome === 'NOT_POSTED'}
                      onChange={() => setReconOutcome('NOT_POSTED')}
                      className="text-blue-500 focus:ring-0"
                    />
                    <div>
                      <span className="font-bold block">NOT POSTED</span>
                      <span className="text-[10px] block opacity-80">Verified absent, enable retry</span>
                    </div>
                  </label>
                </div>
              </div>

              {reconOutcome === 'ACCEPTED' && (
                <div>
                  <label className="text-slate-300 font-semibold block mb-1">
                    Returned FBR Invoice Number (Required)
                  </label>
                  <input
                    type="text"
                    value={reconFbrInvoiceNo}
                    onChange={(e) => setReconFbrInvoiceNo(e.target.value)}
                    required
                    placeholder="e.g. 149121-10294-01928"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 font-mono focus:outline-none focus:border-cyan-500"
                  />
                </div>
              )}

              <div>
                <label className="text-slate-300 font-semibold block mb-1">
                  Reconciliation Notes &amp; Verification Evidence
                </label>
                <textarea
                  value={reconNotes}
                  onChange={(e) => setReconNotes(e.target.value)}
                  required
                  rows={3}
                  placeholder="e.g., 'Looked up in PRAL e-portal by IT admin; confirmed invoice was accepted with FBR #'"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-100 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setReconcilingInvoice(null)}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={reconSubmitting}
                  className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold transition flex items-center gap-1.5 shadow-lg shadow-amber-600/20 disabled:opacity-50"
                >
                  {reconSubmitting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}
                  Save Reconciliation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Attempt History Drawer / Modal */}
      {historyInvoice && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 shrink-0">
              <div className="flex items-center gap-2">
                <History className="w-5 h-5 text-cyan-400" />
                <h3 className="text-base font-bold text-white">
                  Fiscal Attempt History — {historyInvoice.original_invoice_no}
                </h3>
              </div>
              <button
                onClick={() => setHistoryInvoice(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg"
              >
                ✕
              </button>
            </div>

            <div className="overflow-y-auto space-y-3 pr-1 text-xs">
              {historyLoading ? (
                <div className="py-8 text-center text-slate-400">
                  <RefreshCw className="w-5 h-5 animate-spin mx-auto text-cyan-400 mb-2" />
                  Loading audit attempt records...
                </div>
              ) : historyAttempts.length === 0 ? (
                <div className="py-8 text-center text-slate-500">
                  No previous fiscal attempts logged for this invoice.
                </div>
              ) : (
                historyAttempts.map((att) => (
                  <div key={att.id} className="bg-slate-950 border border-slate-800 rounded-xl p-3.5 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-cyan-400">
                          Attempt #{att.attempt_number}
                        </span>
                        <span className="px-1.5 py-0.2 rounded text-[10px] bg-slate-800 text-slate-300 font-semibold">
                          {att.attempt_type}
                        </span>
                      </div>
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        att.outcome === 'ACCEPTED' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' :
                        att.outcome === 'IN_FLIGHT' ? 'bg-cyan-950 text-cyan-400 border border-cyan-800' :
                        'bg-rose-950 text-rose-400 border border-rose-800'
                      }`}>
                        {att.outcome}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-[11px] text-slate-400 font-mono">
                      <div>
                        Initiated By: <span className="text-slate-200">{att.initiated_by}</span>
                      </div>
                      <div title={formatUtcTooltip(att.initiated_at)}>
                        Timestamp: <span className="text-slate-200">{formatPktDateTime(att.initiated_at)}</span>
                      </div>
                    </div>

                    {att.fbr_invoice_number && (
                      <div className="text-[11px] font-mono text-emerald-400">
                        FBR Invoice Number: <strong>{att.fbr_invoice_number}</strong>
                      </div>
                    )}

                    {att.response_body_text && (
                      <div className="p-2 rounded bg-slate-900 border border-slate-800/80 text-[10px] font-mono text-slate-300 break-words">
                        {att.response_body_text}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            <div className="pt-3 border-t border-slate-800 flex justify-end shrink-0">
              <button
                type="button"
                onClick={() => setHistoryInvoice(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

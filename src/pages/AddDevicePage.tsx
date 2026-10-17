import React, { useState, useEffect } from 'react';
import { 
  PlusCircle, 
  Store as StoreIcon, 
  Terminal, 
  Copy, 
  Check, 
  Key, 
  FileText, 
  AlertTriangle, 
  ShieldCheck, 
  ArrowRight,
  RefreshCw,
  Laptop
} from 'lucide-react';
import { Store } from '../types';
import { api, getBaseApiUrl } from '../api';

interface AddDevicePageProps {
  onDeviceRegistered?: () => void;
}

export const AddDevicePage: React.FC<AddDevicePageProps> = ({ onDeviceRegistered }) => {
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Form input
  const [selectedStoreId, setSelectedStoreId] = useState<number | ''>('');
  const [deviceId, setDeviceId] = useState<string>('POS-12');
  const [deviceType, setDeviceType] = useState<'POS' | 'PC' | 'PRINTER' | 'SERVER'>('POS');
  const [generating, setGenerating] = useState<boolean>(false);

  // Generated Result
  const [generatedResult, setGeneratedResult] = useState<{
    enrollmentKey: string;
    storeCode: string;
    storeName: string;
    deviceId: string;
    deviceType: string;
    gatewayUrl: string;
    powershellCmd: string;
    configToml: string;
  } | null>(null);

  const [copiedKey, setCopiedKey] = useState<boolean>(false);
  const [copiedPs, setCopiedPs] = useState<boolean>(false);
  const [copiedToml, setCopiedToml] = useState<boolean>(false);

  useEffect(() => {
    const loadStores = async () => {
      try {
        setLoading(true);
        const data = await api.getStores();
        setStores(data);
        if (data.length > 0) {
          setSelectedStoreId(data[0].id);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to fetch stores list');
      } finally {
        setLoading(false);
      }
    };
    loadStores();
  }, []);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedStoreId) return;

    try {
      setGenerating(true);
      setError(null);
      const res = await api.createEnrollmentKey(Number(selectedStoreId));
      const chosenStore = stores.find(s => s.id === Number(selectedStoreId));
      const storeCode = chosenStore ? chosenStore.code : 'STORE';
      const storeName = chosenStore ? chosenStore.name : 'Hypermarket';
      const gatewayUrl = getBaseApiUrl();

      const psScript = `# Run this in Administrator PowerShell on the target terminal (${deviceId})
$ErrorActionPreference = "Stop"
Write-Host ">>> Installing HBK IT Monitoring Agent on ${deviceId} (${storeCode})..." -ForegroundColor Cyan

# 1. Target directory
$InstallDir = "C:\\HBK-Agent"
if (!(Test-Path $InstallDir)) { New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null }

# 2. Write configuration file (config.toml)
@'
[gateway]
url = "${gatewayUrl}"
verify_tls = true

[device]
device_id = "${deviceId}"
store = "${storeCode}"
device_type = "${deviceType}"
enrollment_key = "${res.enrollment_key}"

[collect]
heartbeat_sec = 30
metrics_sec = 60
services = ["Spooler", "HBK-POS-Service"]
ping_targets = ["8.8.8.8", "1.1.1.1"]

[limits]
max_buffer_mb = 20
'@ | Out-File -FilePath "$InstallDir\\config.toml" -Encoding utf8

# 3. Enroll and start service
cd $InstallDir
Write-Host ">>> Enrollment key injected. Run agent service start:" -ForegroundColor Green
Write-Host ".\\hbk-agent.exe install; .\\hbk-agent.exe start" -ForegroundColor Yellow
`;

      const tomlContent = `[gateway]
url = "${gatewayUrl}"
verify_tls = true

[device]
device_id = "${deviceId}"
store = "${storeCode}"
device_type = "${deviceType}"
enrollment_key = "${res.enrollment_key}"  # Key is consumed on first contact and stripped automatically

[collect]
heartbeat_sec = 30
metrics_sec = 60
services = ["Spooler"]                    # Add SAP CCO / POS retail service names here
ping_targets = ["8.8.8.8", "1.1.1.1"]

[limits]
max_buffer_mb = 20
`;

      setGeneratedResult({
        enrollmentKey: res.enrollment_key,
        storeCode,
        storeName,
        deviceId,
        deviceType,
        gatewayUrl,
        powershellCmd: psScript,
        configToml: tomlContent
      });
    } catch (err: any) {
      setError(err.message || 'Failed to generate enrollment key');
    } finally {
      setGenerating(false);
    }
  };

  const copyToClipboard = (text: string, type: 'key' | 'ps' | 'toml') => {
    navigator.clipboard.writeText(text);
    if (type === 'key') {
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
    } else if (type === 'ps') {
      setCopiedPs(true);
      setTimeout(() => setCopiedPs(false), 2000);
    } else {
      setCopiedToml(true);
      setTimeout(() => setCopiedToml(false), 2000);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
          <PlusCircle className="w-5 h-5 text-emerald-400" />
          Enroll New Terminal / Machine
        </h2>
        <p className="text-xs text-slate-400 mt-0.5">
          Generate a one-time enrollment key and instant PowerShell installer script for Windows POS terminals.
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-300 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-slate-400 hover:text-white text-xs">
            Dismiss
          </button>
        </div>
      )}

      {/* Enrollment Configuration Form */}
      {!generatedResult ? (
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-5">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <Laptop className="w-4 h-4 text-cyan-400" />
            Device Configuration Parameters
          </h3>

          <form onSubmit={handleGenerate} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Store selection */}
              <div>
                <label className="text-[11px] font-medium text-slate-300 block mb-1">Assigned Store</label>
                <select
                  required
                  value={selectedStoreId}
                  onChange={(e) => setSelectedStoreId(e.target.value ? Number(e.target.value) : '')}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
                >
                  {stores.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.code} - {s.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Device ID */}
              <div>
                <label className="text-[11px] font-medium text-slate-300 block mb-1">
                  Device ID (e.g. POS-12, LANE-04)
                </label>
                <input
                  type="text"
                  required
                  value={deviceId}
                  onChange={(e) => setDeviceId(e.target.value.toUpperCase())}
                  placeholder="POS-12"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
                />
              </div>

              {/* Device Type */}
              <div>
                <label className="text-[11px] font-medium text-slate-300 block mb-1">Device Type</label>
                <select
                  value={deviceType}
                  onChange={(e) => setDeviceType(e.target.value as any)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
                >
                  <option value="POS">POS Terminal (Checkout Lane)</option>
                  <option value="PC">Back-Office PC</option>
                  <option value="PRINTER">Network / Receipt Printer</option>
                  <option value="SERVER">Local Store Server</option>
                </select>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-400 space-y-1">
              <span className="font-semibold text-slate-200 block">Security Provisioning Process:</span>
              <p>
                A single-use cryptographic enrollment key will be created for the selected store. Once the agent on the target machine contacts the gateway, the key is permanently verified and invalidated in the gateway database.
              </p>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="submit"
                disabled={generating || !selectedStoreId || !deviceId}
                className="px-5 py-2.5 bg-gradient-to-r from-emerald-500 to-cyan-600 hover:from-emerald-400 hover:to-cyan-500 text-slate-950 font-black text-xs rounded-xl flex items-center gap-2 transition shadow-lg shadow-emerald-500/20 disabled:opacity-50"
              >
                {generating ? (
                  <span>Generating Secure Enrollment Artifacts...</span>
                ) : (
                  <>
                    <Key className="w-4 h-4" />
                    <span>Generate Enrollment Key & Installer</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      ) : (
        /* Generated Key & Script Output Screen */
        <div className="space-y-6">
          {/* Key Banner - Shown Only Once */}
          <div className="bg-amber-950/40 border border-amber-600/70 rounded-2xl p-5 space-y-3 shadow-xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-amber-300 text-xs font-bold uppercase tracking-wider">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                Single-Use Enrollment Key (Shown Once)
              </div>
              <span className="text-[10px] text-amber-400 bg-amber-950 px-2 py-0.5 rounded border border-amber-800">
                Store: {generatedResult.storeCode}
              </span>
            </div>

            <div className="flex items-center gap-3">
              <code className="flex-1 bg-slate-950 border border-amber-900/60 rounded-xl px-4 py-3 text-sm font-mono font-black text-amber-300 select-all overflow-x-auto">
                {generatedResult.enrollmentKey}
              </code>
              <button
                onClick={() => copyToClipboard(generatedResult.enrollmentKey, 'key')}
                className="px-4 py-3 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs rounded-xl flex items-center gap-1.5 transition shrink-0"
              >
                {copiedKey ? <Check className="w-4 h-4 text-slate-950" /> : <Copy className="w-4 h-4" />}
                {copiedKey ? 'Copied!' : 'Copy Key'}
              </button>
            </div>

            <p className="text-[11px] text-amber-200/80">
              ⚠️ Store this key securely or run the installer command immediately. The gateway only stores the cryptographic SHA-256 hash; the raw key cannot be retrieved again after closing this window.
            </p>
          </div>

          {/* 1. Exact PowerShell Install Command */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
            <div className="px-5 py-3.5 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-bold text-white uppercase tracking-wider">
                  Option 1: Complete PowerShell Installation Script
                </span>
              </div>
              <button
                onClick={() => copyToClipboard(generatedResult.powershellCmd, 'ps')}
                className="px-3 py-1 bg-cyan-600 hover:bg-cyan-500 text-slate-950 text-xs font-bold rounded-lg flex items-center gap-1.5 transition"
              >
                {copiedPs ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                {copiedPs ? 'Copied Script' : 'Copy PowerShell'}
              </button>
            </div>

            <pre className="p-4 bg-slate-950 text-xs font-mono text-cyan-300 overflow-x-auto leading-relaxed border-b border-slate-800">
              {generatedResult.powershellCmd}
            </pre>
          </div>

          {/* 2. Ready config.toml */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
            <div className="px-5 py-3.5 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-bold text-white uppercase tracking-wider">
                  Option 2: Ready-to-Drop config.toml (Place next to hbk-agent.exe)
                </span>
              </div>
              <button
                onClick={() => copyToClipboard(generatedResult.configToml, 'toml')}
                className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition"
              >
                {copiedToml ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                {copiedToml ? 'Copied config.toml' : 'Copy config.toml'}
              </button>
            </div>

            <pre className="p-4 bg-slate-950 text-xs font-mono text-slate-300 overflow-x-auto leading-relaxed border-b border-slate-800">
              {generatedResult.configToml}
            </pre>
          </div>

          <div className="flex justify-between items-center pt-2">
            <button
              onClick={() => {
                setGeneratedResult(null);
                setDeviceId('');
              }}
              className="text-xs text-slate-400 hover:text-white"
            >
              ← Enroll another machine
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

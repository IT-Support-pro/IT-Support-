import React, { useState, useEffect, useCallback } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoginPage } from './pages/LoginPage';
import { OverviewPage } from './pages/OverviewPage';
import { DevicesPage } from './pages/DevicesPage';
import { DeviceDetailPage } from './pages/DeviceDetailPage';
import { AlertsPage } from './pages/AlertsPage';
import { StoresPage } from './pages/StoresPage';
import { UsersPage } from './pages/UsersPage';
import { AddDevicePage } from './pages/AddDevicePage';
import { FbrMonitoringPage } from './pages/FbrMonitoringPage';
import { InvoicesPage } from './pages/InvoicesPage';
import { Navbar } from './components/Navbar';
import { api } from './api';
import { RefreshCw } from 'lucide-react';

function DashboardContent() {
  const { isAuthenticated, isLoading, role } = useAuth();
  const [activePage, setActivePage] = useState<string>('overview');
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('POS-12');
  const [filterStoreCode, setFilterStoreCode] = useState<string>('');
  const [firingAlertsCount, setFiringAlertsCount] = useState<number>(0);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);
  const [refreshTick, setRefreshTick] = useState<number>(0);

  const fetchGlobalAlertCounts = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const overview = await api.getOverview();
      setFiringAlertsCount(overview.firing_alerts ?? 0);
    } catch {
      // Ignore background refresh errors
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchGlobalAlertCounts();
  }, [fetchGlobalAlertCounts, refreshTick]);

  // 10s Auto-refresh timer
  useEffect(() => {
    if (!autoRefresh || !isAuthenticated) return;
    const interval = setInterval(() => {
      setRefreshTick(prev => prev + 1);
    }, 10000);
    return () => clearInterval(interval);
  }, [autoRefresh, isAuthenticated]);

  const handleManualRefresh = () => {
    setRefreshTick(prev => prev + 1);
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center space-y-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-white font-black animate-pulse">
          HBK
        </div>
        <span className="text-xs text-slate-400">Verifying security session...</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-cyan-500 selection:text-black">
      {/* Navbar with role controls, live status, and auto-refresh */}
      <Navbar
        activePage={activePage}
        setActivePage={(page) => {
          if (page === 'devices') setFilterStoreCode('');
          setActivePage(page);
        }}
        firingAlertsCount={firingAlertsCount}
        autoRefresh={autoRefresh}
        setAutoRefresh={setAutoRefresh}
        onRefresh={handleManualRefresh}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activePage === 'overview' && (
          <OverviewPage
            onNavigateToDevice={(deviceId) => {
              setSelectedDeviceId(deviceId);
              setActivePage('device-detail');
            }}
            onNavigateToAlerts={() => setActivePage('alerts')}
            onNavigateToDevices={() => {
              setFilterStoreCode('');
              setActivePage('devices');
            }}
          />
        )}

        {activePage === 'devices' && (
          <DevicesPage
            key={filterStoreCode}
            initialStoreFilter={filterStoreCode}
            onSelectDevice={(deviceId) => {
              setSelectedDeviceId(deviceId);
              setActivePage('device-detail');
            }}
          />
        )}

        {activePage === 'device-detail' && (
          <DeviceDetailPage
            key={selectedDeviceId}
            deviceId={selectedDeviceId}
            onBack={() => setActivePage('devices')}
          />
        )}

        {activePage === 'alerts' && (
          <AlertsPage
            onNavigateToDevice={(deviceId) => {
              setSelectedDeviceId(deviceId);
              setActivePage('device-detail');
            }}
          />
        )}

        {activePage === 'stores' && (
          <StoresPage
            onSelectStore={(storeCode) => {
              setFilterStoreCode(storeCode);
              setActivePage('devices');
            }}
          />
        )}

        {activePage === 'fbr' && (
          <FbrMonitoringPage
            onNavigateToDevice={(deviceId) => {
              setSelectedDeviceId(deviceId);
              setActivePage('device-detail');
            }}
          />
        )}

        {activePage === 'invoices' && (
          <InvoicesPage
            onNavigateToDevice={(deviceId) => {
              setSelectedDeviceId(deviceId);
              setActivePage('device-detail');
            }}
          />
        )}

        {activePage === 'users' && role === 'admin' && (
          <UsersPage />
        )}

        {activePage === 'add-device' && role === 'admin' && (
          <AddDevicePage
            onDeviceRegistered={() => {
              setActivePage('devices');
            }}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 py-4 text-center text-xs text-slate-600">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>HBK IT Monitoring System • Retail Hypermarket POS Fleet</span>
          <span className="font-mono text-[11px] text-slate-500">Read-Only Telemetry Ingest • Hermes AI Ready</span>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <DashboardContent />
    </AuthProvider>
  );
}

import React, { useState, useEffect } from 'react';
import { 
  Users, 
  UserPlus, 
  ShieldCheck, 
  RefreshCw, 
  Lock, 
  Store as StoreIcon, 
  CheckCircle2, 
  AlertCircle,
  Key
} from 'lucide-react';
import { User, Store } from '../types';
import { api } from '../api';

export const UsersPage: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // New user form state
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [role, setRole] = useState<'admin' | 'technician' | 'viewer'>('technician');

  // Assign stores state
  const [assigningUser, setAssigningUser] = useState<User | null>(null);
  const [selectedStoreIds, setSelectedStoreIds] = useState<number[]>([]);

  const fetchUsersAndStores = async () => {
    try {
      setLoading(true);
      setError(null);
      const [uList, sList] = await Promise.all([
        api.getUsers(),
        api.getStores()
      ]);
      setUsers(uList);
      setStores(sList);
    } catch (err: any) {
      setError(err.message || 'Failed to load user management data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsersAndStores();
  }, []);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 10) {
      setError('Password must be at least 10 characters long.');
      return;
    }

    try {
      setError(null);
      await api.createUser({ username, password, role });
      setSuccess(`User '${username}' created successfully.`);
      setShowCreateModal(false);
      setUsername('');
      setPassword('');
      fetchUsersAndStores();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to create user');
    }
  };

  const handleOpenAssign = (user: User) => {
    setAssigningUser(user);
    setSelectedStoreIds(user.assigned_store_ids || []);
  };

  const handleToggleStore = (storeId: number) => {
    if (selectedStoreIds.includes(storeId)) {
      setSelectedStoreIds(selectedStoreIds.filter(id => id !== storeId));
    } else {
      setSelectedStoreIds([...selectedStoreIds, storeId]);
    }
  };

  const handleSaveAssignments = async () => {
    if (!assigningUser) return;
    try {
      setError(null);
      await api.assignUserStores(assigningUser.id, selectedStoreIds);
      setSuccess(`Store permissions updated for '${assigningUser.username}'`);
      setAssigningUser(null);
      fetchUsersAndStores();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to update store assignments');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Users className="w-5 h-5 text-cyan-400" />
            User & Role-Based Access Control (RBAC)
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Admin full access • Technicians assigned store scope • Viewers read-only.
          </p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold text-xs flex items-center gap-1.5 transition shadow"
          >
            <UserPlus className="w-3.5 h-3.5" />
            Create User
          </button>
          <button
            onClick={fetchUsersAndStores}
            className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 hover:text-white text-xs flex items-center gap-1.5 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          </button>
        </div>
      </div>

      {success && (
        <div className="p-3 bg-emerald-950/60 border border-emerald-800 text-emerald-300 text-xs rounded-xl flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          {success}
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-300 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="text-slate-400 hover:text-white text-xs">
            Dismiss
          </button>
        </div>
      )}

      {/* Users Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-950/70 text-slate-400 uppercase text-[10px] tracking-wider font-semibold">
              <th className="py-3 px-4">User ID</th>
              <th className="py-3 px-4">Username</th>
              <th className="py-3 px-4">Role</th>
              <th className="py-3 px-4">Status</th>
              <th className="py-3 px-4">Assigned Stores</th>
              <th className="py-3 px-4">Created Date</th>
              <th className="py-3 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/80">
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-slate-850/50 transition">
                <td className="py-3.5 px-4 font-mono text-slate-500">#{u.id}</td>
                <td className="py-3.5 px-4 font-bold text-white flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-slate-800 flex items-center justify-center text-[10px] text-cyan-300">
                    {u.username.substring(0, 2).toUpperCase()}
                  </div>
                  {u.username}
                </td>
                <td className="py-3.5 px-4">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                    u.role === 'admin' ? 'bg-cyan-950 text-cyan-400 border border-cyan-800' :
                    u.role === 'technician' ? 'bg-blue-950 text-blue-400 border border-blue-800' :
                    'bg-slate-800 text-slate-300'
                  }`}>
                    {u.role}
                  </span>
                </td>
                <td className="py-3.5 px-4">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    u.is_active ? 'bg-emerald-950 text-emerald-400' : 'bg-rose-950 text-rose-400'
                  }`}>
                    {u.is_active ? 'Active' : 'Disabled'}
                  </span>
                </td>
                <td className="py-3.5 px-4">
                  {u.role === 'admin' ? (
                    <span className="text-slate-400 font-mono text-[11px]">All Stores (Global)</span>
                  ) : (
                    <div className="flex flex-wrap gap-1">
                      {(u.assigned_store_ids || []).map((sid) => {
                        const st = stores.find(s => s.id === sid);
                        return (
                          <span key={sid} className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-slate-950 text-slate-300 border border-slate-800">
                            {st?.code || sid}
                          </span>
                        );
                      })}
                      {(!u.assigned_store_ids || u.assigned_store_ids.length === 0) && (
                        <span className="text-slate-600 italic">None assigned</span>
                      )}
                    </div>
                  )}
                </td>
                <td className="py-3.5 px-4 text-slate-400 text-[11px]">
                  {new Date(u.created_at).toLocaleDateString()}
                </td>
                <td className="py-3.5 px-4 text-right">
                  {u.role !== 'admin' && (
                    <button
                      onClick={() => handleOpenAssign(u)}
                      className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-750 text-cyan-300 text-[11px] font-semibold"
                    >
                      Assign Stores
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <UserPlus className="w-4 h-4 text-cyan-400" />
              Add New User
            </h3>

            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="text-[11px] font-medium text-slate-300 block mb-1">Username</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. tech_karachi"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-medium text-slate-300 block mb-1">Password (min 10 characters)</label>
                <input
                  type="password"
                  required
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="text-[11px] font-medium text-slate-300 block mb-1">Role</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value as any)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
                >
                  <option value="technician">technician (assigned stores, ack/resolve)</option>
                  <option value="viewer">viewer (assigned stores, read-only)</option>
                  <option value="admin">admin (global management)</option>
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 text-xs font-bold"
                >
                  Create User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Assign Stores Modal */}
      {assigningUser && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <StoreIcon className="w-4 h-4 text-cyan-400" />
              Assign Stores to {assigningUser.username}
            </h3>

            <p className="text-xs text-slate-400">
              Select which hypermarket branches this technician can view, acknowledge alerts for, and monitor.
            </p>

            <div className="space-y-2 max-h-60 overflow-y-auto p-1">
              {stores.map((s) => {
                const isSelected = selectedStoreIds.includes(s.id);
                return (
                  <div
                    key={s.id}
                    onClick={() => handleToggleStore(s.id)}
                    className={`p-3 rounded-xl border cursor-pointer flex items-center justify-between text-xs transition ${
                      isSelected
                        ? 'bg-cyan-950/40 border-cyan-800 text-white'
                        : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div>
                      <span className="font-mono font-bold text-cyan-300 mr-2">{s.code}</span>
                      <span>{s.name}</span>
                    </div>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {}}
                      className="rounded border-slate-700 text-cyan-500"
                    />
                  </div>
                );
              })}
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setAssigningUser(null)}
                className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 text-xs"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveAssignments}
                className="px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-slate-950 text-xs font-bold"
              >
                Save Store Assignments
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

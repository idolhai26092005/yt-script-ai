import React, { useEffect, useReducer, useState } from 'react';
import {
  listAdminKeys, createAdminKey, revokeAdminKey,
  fetchAdminTrendingTopics, createTrendingTopic, updateTrendingTopic,
  deleteTrendingTopic, toggleTrendingTopic, reorderTrendingTopics,
  getErrorMessage
} from '../services/api';
import type { APIKeyResponse, TrendingTopicResponse } from '../services/api';

interface AdminPanelProps {
  navigate: (path: string) => void;
}

interface AdminState {
  adminSecret: string;
  isLoggedIn: boolean;
  keys: APIKeyResponse[];
  loading: boolean;
  error: string | null;
  owner: string;
  quotaLimit: number;
  expiryDays: string;
  newlyCreatedKey: string | null;
  copySuccess: boolean;
  copiedHashId: number | null;
}

const initialState: AdminState = {
  adminSecret: '',
  isLoggedIn: false,
  keys: [],
  loading: false,
  error: null,
  owner: '',
  quotaLimit: 100,
  expiryDays: '30',
  newlyCreatedKey: null,
  copySuccess: false,
  copiedHashId: null,
};

type AdminAction =
  | { type: 'SET_ADMIN_SECRET'; payload: string }
  | { type: 'SET_IS_LOGGED_IN'; payload: boolean }
  | { type: 'SET_KEYS'; payload: APIKeyResponse[] }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'SET_OWNER'; payload: string }
  | { type: 'SET_QUOTA_LIMIT'; payload: number }
  | { type: 'SET_EXPIRY_DAYS'; payload: string }
  | { type: 'SET_NEWLY_CREATED_KEY'; payload: string | null }
  | { type: 'SET_COPY_SUCCESS'; payload: boolean }
  | { type: 'SET_COPIED_HASH_ID'; payload: number | null }
  | { type: 'LOGOUT' }
  | { type: 'RESET_FORM' }
  | { type: 'LOGIN_SUCCESS'; secret: string; keys: APIKeyResponse[] };

function adminReducer(state: AdminState, action: AdminAction): AdminState {
  switch (action.type) {
    case 'SET_ADMIN_SECRET':
      return { ...state, adminSecret: action.payload };
    case 'SET_IS_LOGGED_IN':
      return { ...state, isLoggedIn: action.payload };
    case 'SET_KEYS':
      return { ...state, keys: action.payload };
    case 'SET_LOADING':
      return { ...state, loading: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    case 'SET_OWNER':
      return { ...state, owner: action.payload };
    case 'SET_QUOTA_LIMIT':
      return { ...state, quotaLimit: action.payload };
    case 'SET_EXPIRY_DAYS':
      return { ...state, expiryDays: action.payload };
    case 'SET_NEWLY_CREATED_KEY':
      return { ...state, newlyCreatedKey: action.payload };
    case 'SET_COPY_SUCCESS':
      return { ...state, copySuccess: action.payload };
    case 'SET_COPIED_HASH_ID':
      return { ...state, copiedHashId: action.payload };
    case 'LOGOUT':
      return { ...initialState };
    case 'RESET_FORM':
      return { ...state, owner: '' };
    case 'LOGIN_SUCCESS':
      return {
        ...state,
        adminSecret: action.secret,
        isLoggedIn: true,
        keys: action.keys,
        loading: false,
        error: null,
      };
    default:
      return state;
  }
}

export const AdminPanel: React.FC<AdminPanelProps> = ({ navigate }) => {
  const [state, dispatch] = useReducer(adminReducer, initialState);

  const {
    adminSecret,
    isLoggedIn,
    keys,
    loading,
    error,
    owner,
    quotaLimit,
    expiryDays,
    newlyCreatedKey,
    copySuccess,
    copiedHashId,
  } = state;

  const [subTab, setSubTab] = useState<'keys' | 'topics'>('keys');
  const [topics, setTopics] = useState<TrendingTopicResponse[]>([]);
  const [loadingTopics, setLoadingTopics] = useState(false);
  const [topicName, setTopicName] = useState('');
  const [topicDescription, setTopicDescription] = useState('');
  const [topicIcon, setTopicIcon] = useState('🔥');
  const [topicDisplayOrder, setTopicDisplayOrder] = useState(0);
  const [editingTopicId, setEditingTopicId] = useState<number | null>(null);

  const fetchTopics = async (secret: string) => {
    setLoadingTopics(true);
    try {
      const data = await fetchAdminTrendingTopics(secret);
      setTopics(data || []);
    } catch (err: unknown) {
      console.error('Error fetching admin topics:', err);
    } finally {
      setLoadingTopics(false);
    }
  };

  const handleCreateOrUpdateTopic = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topicName.trim()) return;

    try {
      if (editingTopicId !== null) {
        await updateTrendingTopic(adminSecret, editingTopicId, {
          name: topicName.trim(),
          description: topicDescription.trim(),
          icon: topicIcon.trim(),
          display_order: topicDisplayOrder,
        });
      } else {
        await createTrendingTopic(adminSecret, {
          name: topicName.trim(),
          description: topicDescription.trim(),
          icon: topicIcon.trim(),
          display_order: topicDisplayOrder,
        });
      }
      clearTopicForm();
      fetchTopics(adminSecret);
    } catch (err: unknown) {
      alert(getErrorMessage(err, 'Lỗi lưu chủ đề nóng.'));
    }
  };

  const handleDeleteTopic = async (id: number) => {
    if (!window.confirm('Bạn có chắc chắn muốn xóa chủ đề này?')) return;
    try {
      await deleteTrendingTopic(adminSecret, id);
      fetchTopics(adminSecret);
    } catch (err: unknown) {
      alert(getErrorMessage(err, 'Không thể xóa chủ đề.'));
    }
  };

  const handleToggleTopic = async (id: number) => {
    try {
      await toggleTrendingTopic(adminSecret, id);
      fetchTopics(adminSecret);
    } catch (err: unknown) {
      alert(getErrorMessage(err, 'Không thể đổi trạng thái hiển thị.'));
    }
  };

  const handleReorderTopic = async (id: number, direction: 'up' | 'down') => {
    const idx = topics.findIndex((t) => t.id === id);
    if (idx === -1) return;
    
    const newIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (newIdx < 0 || newIdx >= topics.length) return;

    const updated = [...topics];
    const temp = updated[idx];
    updated[idx] = updated[newIdx];
    updated[newIdx] = temp;

    const ids = updated.map((t) => t.id);
    try {
      await reorderTrendingTopics(adminSecret, ids);
      fetchTopics(adminSecret);
    } catch (err: unknown) {
      alert(getErrorMessage(err, 'Lỗi sắp xếp lại chủ đề.'));
    }
  };

  const clearTopicForm = () => {
    setTopicName('');
    setTopicDescription('');
    setTopicIcon('🔥');
    setTopicDisplayOrder(0);
    setEditingTopicId(null);
  };

  useEffect(() => {
    // Admin secret is stored in-memory only for security, no auto-login from local storage.
  }, []);

  const fetchKeys = async (secret: string) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const data = await listAdminKeys(secret);
      dispatch({ type: 'SET_KEYS', payload: data });
    } catch (err: unknown) {
      dispatch({ type: 'SET_ERROR', payload: getErrorMessage(err, 'Lỗi tải danh sách API Key') });
      dispatch({ type: 'SET_IS_LOGGED_IN', payload: false });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (!adminSecret.trim()) return;
    dispatch({ type: 'SET_IS_LOGGED_IN', payload: true });
    fetchKeys(adminSecret.trim());
    fetchTopics(adminSecret.trim());
  };

  const handleLogout = () => {
    dispatch({ type: 'LOGOUT' });
  };

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!owner.trim()) return;

    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    dispatch({ type: 'SET_NEWLY_CREATED_KEY', payload: null });

    try {
      const limitVal = quotaLimit > 0 ? quotaLimit : 100;
      let expiryDate: string | null = null;
      if (expiryDays !== 'never') {
        const days = parseInt(expiryDays, 10) || 30;
        const d = new Date();
        d.setDate(d.getDate() + days);
        expiryDate = d.toISOString();
      }

      const data = await createAdminKey(adminSecret, {
        owner: owner.trim(),
        quota_limit: limitVal,
        expiry: expiryDate,
      });
      dispatch({ type: 'SET_NEWLY_CREATED_KEY', payload: data.plain_key });
      dispatch({ type: 'RESET_FORM' });
      fetchKeys(adminSecret);
    } catch (err: unknown) {
      dispatch({ type: 'SET_ERROR', payload: getErrorMessage(err, 'Không thể tạo API Key') });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  const handleRevokeKey = async (id: number) => {
    if (!window.confirm('Bạn có chắc chắn muốn thu hồi API Key này? Thao tác này KHÔNG THỂ khôi phục.')) return;
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      await revokeAdminKey(adminSecret, id);
      fetchKeys(adminSecret);
    } catch (err: unknown) {
      dispatch({ type: 'SET_ERROR', payload: getErrorMessage(err, 'Không thể thu hồi API Key') });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  };

  const handleCopyNewKey = () => {
    if (!newlyCreatedKey) return;
    navigator.clipboard.writeText(newlyCreatedKey);
    dispatch({ type: 'SET_COPY_SUCCESS', payload: true });
    setTimeout(() => dispatch({ type: 'SET_COPY_SUCCESS', payload: false }), 2000);
  };

  const handleCopyHash = (id: number, hash: string) => {
    navigator.clipboard.writeText(hash);
    dispatch({ type: 'SET_COPIED_HASH_ID', payload: id });
    setTimeout(() => dispatch({ type: 'SET_COPIED_HASH_ID', payload: null }), 2000);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-slate-800/80 pb-4 gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <span>⚙️</span>
            <span>Trang quản trị (Admin Panel)</span>
          </h2>
          <p className="text-xs text-slate-400">Cấu hình các tham số hệ thống và quản lý người dùng.</p>
        </div>
        <button
          onClick={() => navigate('/home')}
          className="text-xs bg-slate-850 hover:bg-slate-800 text-slate-300 font-semibold px-4 py-2 rounded-xl border border-slate-850 hover:border-slate-800 transition shadow cursor-pointer self-start"
        >
          ← Quay lại Trang chủ
        </button>
      </div>

      {!isLoggedIn ? (
        <div className="max-w-md mx-auto bg-slate-900/40 backdrop-blur-md p-6 rounded-2xl border border-slate-850 shadow-2xl mt-12">
          <div className="flex justify-center mb-6">
            <div className="h-12 w-12 rounded-xl bg-purple-500/10 flex items-center justify-center border border-purple-500/20 text-purple-400">
              <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
          </div>
          <h3 className="text-lg font-bold text-center text-slate-100 mb-6">Xác thực quyền Admin</h3>
          
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                Admin Secret Key
              </label>
              <input
                type="password"
                value={adminSecret}
                onChange={(e) => dispatch({ type: 'SET_ADMIN_SECRET', payload: e.target.value })}
                placeholder="Nhập secret key để quản trị..."
                className="w-full bg-[#080B11] border border-slate-800 focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/50 rounded-xl px-4 py-3 text-sm text-slate-200 outline-none transition duration-200"
              />
            </div>
            <button
              type="submit"
              className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 font-semibold text-sm py-3 rounded-xl transition duration-200 shadow-lg shadow-purple-900/20 cursor-pointer text-white"
            >
              Đăng nhập Admin
            </button>
          </form>
          {error && <p className="text-xs text-rose-400 text-center mt-4">{error}</p>}
        </div>
      ) : (
        <div className="space-y-6">
          {/* Subtab selection */}
          <div className="flex border-b border-slate-800/80 mb-6 bg-slate-900/10 p-1.5 rounded-xl border border-slate-800/60 max-w-md">
            <button
              type="button"
              onClick={() => setSubTab('keys')}
              className={`flex-1 text-center py-2.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                subTab === 'keys'
                  ? 'bg-purple-600/20 text-purple-300 border border-purple-800/40'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Quản lý API Keys
            </button>
            <button
              type="button"
              onClick={() => setSubTab('topics')}
              className={`flex-1 text-center py-2.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                subTab === 'topics'
                  ? 'bg-purple-600/20 text-purple-300 border border-purple-800/40'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Quản lý Chủ đề nóng
            </button>
          </div>

          {subTab === 'keys' ? (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Left Panel: Create Key Form */}
              <div className="lg:col-span-1 bg-slate-900/40 backdrop-blur-md p-6 rounded-2xl border border-slate-800 shadow-xl h-fit">
                <h3 className="text-md font-bold text-slate-200 mb-4 flex items-center gap-2">
                  <svg className="h-5 w-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Cấp phát API Key mới
                </h3>

                <form onSubmit={handleCreateKey} className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                      Tên người sở hữu (Owner)
                    </label>
                    <input
                      type="text"
                      required
                      value={owner}
                      onChange={(e) => dispatch({ type: 'SET_OWNER', payload: e.target.value })}
                      placeholder="Ví dụ: Hai Nam Nguyen..."
                      className="w-full bg-[#080B11] border border-slate-800 focus:border-purple-500/50 rounded-xl px-4 py-2.5 text-xs text-slate-200 outline-none transition"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                      Giới hạn lượt dùng (Quota Limit)
                    </label>
                    <input
                      type="number"
                      required
                      min={1}
                      value={quotaLimit}
                      onChange={(e) => dispatch({ type: 'SET_QUOTA_LIMIT', payload: parseInt(e.target.value) || 0 })}
                      placeholder="100"
                      className="w-full bg-[#080B11] border border-slate-800 focus:border-purple-500/50 rounded-xl px-4 py-2.5 text-xs text-slate-200 outline-none transition"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                      Thời hạn sử dụng
                    </label>
                    <select
                      value={expiryDays}
                      onChange={(e) => dispatch({ type: 'SET_EXPIRY_DAYS', payload: e.target.value })}
                      className="w-full bg-[#080B11] border border-slate-800 focus:border-purple-500/50 rounded-xl px-4 py-2.5 text-xs text-slate-200 outline-none transition cursor-pointer"
                    >
                      <option value="7">7 ngày</option>
                      <option value="30">30 ngày</option>
                      <option value="90">90 ngày</option>
                      <option value="never">Không giới hạn</option>
                    </select>
                  </div>

                  <button
                    type="submit"
                    className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold text-xs py-2.5 rounded-xl transition duration-200 shadow-md cursor-pointer"
                  >
                    Sinh API Key
                  </button>
                </form>

                {newlyCreatedKey && (
                  <div className="mt-6 p-4 bg-purple-950/20 border border-purple-800/40 rounded-xl space-y-2 animate-fadeIn">
                    <span className="block text-xs text-purple-300 font-semibold uppercase">API KEY MỚI SINH</span>
                    <p className="text-[10px] text-slate-400 leading-tight">
                      Vui lòng sao chép khóa này ngay bây giờ. Vì lý do bảo mật, nó sẽ <strong>không bao giờ</strong> được hiển thị lại!
                    </p>
                    <div className="flex items-center gap-2 bg-[#080B11] p-2.5 rounded-xl border border-slate-800">
                      <code className="text-xs text-purple-300 font-mono select-all break-all flex-1">{newlyCreatedKey}</code>
                      <button
                        type="button"
                        onClick={handleCopyNewKey}
                        className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition cursor-pointer"
                      >
                        {copySuccess ? (
                          <svg className="h-4 w-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                          </svg>
                        ) : (
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Right Panel: List Keys */}
              <div className="lg:col-span-2 space-y-6">
                <div className="bg-slate-900/40 backdrop-blur-md p-6 rounded-2xl border border-slate-800 shadow-xl">
                  <div className="flex justify-between items-center mb-6">
                    <h3 className="text-md font-bold text-slate-200">Danh sách khóa đang hoạt động</h3>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => fetchKeys(adminSecret)}
                        className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition cursor-pointer"
                        title="Làm mới"
                      >
                        <svg className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 8.89M9 11l3-3 3 3m-3-3v12" />
                        </svg>
                      </button>
                      <button
                        type="button"
                        onClick={handleLogout}
                        className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-rose-950/40 text-rose-400 hover:bg-rose-950/60 border border-rose-900/40 transition cursor-pointer"
                      >
                        Đăng xuất
                      </button>
                    </div>
                  </div>

                  {error && (
                    <div className="mb-4 bg-rose-950/20 border border-rose-900/40 rounded-xl p-3 text-xs text-rose-400">
                      {error}
                    </div>
                  )}

                  {loading && keys.length === 0 ? (
                    <div className="text-center py-10 space-y-2">
                      <div className="h-6 w-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
                      <p className="text-xs text-slate-500">Đang tải danh sách...</p>
                    </div>
                  ) : keys.length === 0 ? (
                    <div className="text-center py-12 text-slate-500 text-xs">
                      Chưa có API Key nào được tạo. Sử dụng form bên trái để tạo khóa đầu tiên.
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse">
                        <thead>
                          <tr className="border-b border-slate-800/80 text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
                            <th className="pb-3 pl-2">Người sở hữu</th>
                            <th className="pb-3">Hash (SHA-256)</th>
                            <th className="pb-3">Sử dụng / Giới hạn</th>
                            <th className="pb-3">Trạng thái / Hết hạn</th>
                            <th className="pb-3 text-right pr-2">Hành động</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/40 text-xs">
                          {keys.map((k) => {
                            const isExpired = k.expiry && new Date(k.expiry) < new Date();
                            const percent = Math.min(100, Math.round((k.quota_used / k.quota_limit) * 100));
                            
                            return (
                              <tr key={k.id} className="hover:bg-slate-800/20 transition-all" suppressHydrationWarning>
                                <td className="py-3 pl-2 font-medium text-slate-200">{k.owner}</td>
                                <td className="py-3 font-mono text-[10px] text-slate-500">
                                  <div className="flex items-center gap-1.5">
                                    <span title={k.key_hash}>{k.key_hash.substring(0, 10)}...</span>
                                    <button
                                      type="button"
                                      onClick={() => handleCopyHash(k.id, k.key_hash)}
                                      className="p-1 rounded bg-slate-800/40 hover:bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700/30 hover:border-slate-700 transition cursor-pointer"
                                      title="Sao chép Hash"
                                    >
                                      {copiedHashId === k.id ? (
                                        <svg className="h-3 w-3 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
                                        </svg>
                                      ) : (
                                        <svg className="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 112-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
                                        </svg>
                                      )}
                                    </button>
                                  </div>
                                </td>
                                <td className="py-3 pr-4">
                                  <div className="space-y-1">
                                    <div className="flex justify-between text-[10px] font-semibold text-slate-400">
                                      <span>{k.quota_used} / {k.quota_limit}</span>
                                      <span>{percent}%</span>
                                    </div>
                                    <div className="w-full bg-[#080B11] h-1.5 rounded-full overflow-hidden border border-slate-800">
                                      <div
                                        className={`h-full rounded-full transition-all duration-300 ${
                                          percent > 90 ? 'bg-rose-500' : percent > 60 ? 'bg-amber-500' : 'bg-purple-500'
                                        }`}
                                        style={{ width: `${percent}%` }}
                                      ></div>
                                    </div>
                                  </div>
                                </td>
                                <td className="py-3">
                                  <div className="flex flex-col gap-1">
                                    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold ${
                                      k.is_active && !isExpired ? 'text-emerald-400' : 'text-slate-500'
                                    }`}>
                                      <span className={`h-1.5 w-1.5 rounded-full ${
                                        k.is_active && !isExpired ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'
                                      }`}></span>
                                      {k.is_active && !isExpired ? 'Hoạt động' : k.is_active ? 'Hết hạn' : 'Đã thu hồi'}
                                    </span>
                                    <span className="text-[10px] text-slate-500">
                                      {k.expiry ? new Date(k.expiry).toLocaleDateString('vi-VN') : 'Vô thời hạn'}
                                    </span>
                                  </div>
                                </td>
                                <td className="py-3 text-right pr-2">
                                  {k.is_active ? (
                                    <button
                                      type="button"
                                      onClick={() => handleRevokeKey(k.id)}
                                      className="px-2 py-1 text-[10px] font-bold rounded-lg bg-rose-950/20 text-rose-400 hover:bg-rose-950/40 border border-rose-900/30 transition cursor-pointer"
                                    >
                                      Thu hồi
                                    </button>
                                  ) : (
                                    <span className="text-[10px] text-slate-600 italic">N/A</span>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Left Panel: Create/Edit Topic Form */}
              <div className="lg:col-span-1 bg-slate-900/40 backdrop-blur-md p-6 rounded-2xl border border-slate-800 shadow-xl h-fit">
                <h3 className="text-md font-bold text-slate-200 mb-4 flex items-center gap-2">
                  <span>🔥</span>
                  <span>{editingTopicId !== null ? 'Cập nhật chủ đề nóng' : 'Thêm chủ đề nóng mới'}</span>
                </h3>

                <form onSubmit={handleCreateOrUpdateTopic} className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                      Tên chủ đề (Name)
                    </label>
                    <input
                      type="text"
                      required
                      value={topicName}
                      onChange={(e) => setTopicName(e.target.value)}
                      placeholder="Ví dụ: La Mã cổ đại..."
                      className="w-full bg-[#080B11] border border-slate-800 focus:border-purple-500/50 rounded-xl px-4 py-2.5 text-xs text-slate-200 outline-none transition"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                      Mô tả chủ đề (Description)
                    </label>
                    <textarea
                      value={topicDescription}
                      onChange={(e) => setTopicDescription(e.target.value)}
                      placeholder="Mô tả tóm tắt nội dung..."
                      className="w-full h-24 bg-[#080B11] border border-slate-800 focus:border-purple-500/50 rounded-xl px-4 py-2.5 text-xs text-slate-200 outline-none transition resize-none"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                        Emoji Icon
                      </label>
                      <input
                        type="text"
                        value={topicIcon}
                        onChange={(e) => setTopicIcon(e.target.value)}
                        className="w-full bg-[#080B11] border border-slate-800 focus:border-purple-500/50 rounded-xl px-4 py-2.5 text-xs text-slate-200 outline-none transition"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                        Thứ tự (Order)
                      </label>
                      <input
                        type="number"
                        value={topicDisplayOrder}
                        onChange={(e) => setTopicDisplayOrder(parseInt(e.target.value, 10) || 0)}
                        className="w-full bg-[#080B11] border border-slate-800 focus:border-purple-500/50 rounded-xl px-4 py-2.5 text-xs text-slate-200 outline-none transition"
                      />
                    </div>
                  </div>

                  <div className="flex gap-2 pt-2">
                    <button
                      type="submit"
                      className="flex-1 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold text-xs py-2.5 rounded-xl transition duration-200 shadow-md cursor-pointer"
                    >
                      {editingTopicId !== null ? 'Lưu cập nhật' : 'Thêm chủ đề'}
                    </button>
                    {editingTopicId !== null && (
                      <button
                        type="button"
                        onClick={clearTopicForm}
                        className="bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs px-4 py-2.5 rounded-xl border border-slate-700 transition"
                      >
                        Hủy
                      </button>
                    )}
                  </div>
                </form>
              </div>

              {/* Right Panel: List Topics */}
              <div className="lg:col-span-2 space-y-6">
                <div className="bg-slate-900/40 backdrop-blur-md p-6 rounded-2xl border border-slate-800 shadow-xl">
                  <div className="flex justify-between items-center mb-6">
                    <h3 className="text-md font-bold text-slate-200">Danh sách chủ đề nóng</h3>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={() => fetchTopics(adminSecret)}
                        className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition cursor-pointer"
                        title="Làm mới"
                      >
                        <svg className={`h-4 w-4 ${loadingTopics ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 8.89M9 11l3-3 3 3m-3-3v12" />
                        </svg>
                      </button>
                      <button
                        type="button"
                        onClick={handleLogout}
                        className="px-3 py-1.5 text-xs font-semibold rounded-xl bg-rose-950/40 text-rose-400 hover:bg-rose-950/60 border border-rose-900/40 transition cursor-pointer"
                      >
                        Đăng xuất
                      </button>
                    </div>
                  </div>

                  {loadingTopics && topics.length === 0 ? (
                    <div className="text-center py-10 space-y-2">
                      <div className="h-6 w-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
                      <p className="text-xs text-slate-500">Đang tải danh sách chủ đề...</p>
                    </div>
                  ) : topics.length === 0 ? (
                    <div className="text-center py-12 text-slate-500 text-xs">
                      Chưa có chủ đề nóng nào được cấu hình.
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse">
                        <thead>
                          <tr className="border-b border-slate-800/80 text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
                            <th className="pb-3 pl-2 w-12 text-center">Icon</th>
                            <th className="pb-3">Chủ đề</th>
                            <th className="pb-3 w-16 text-center">Thứ tự</th>
                            <th className="pb-3 w-24 text-center">Trạng thái</th>
                            <th className="pb-3 text-right pr-2">Hành động</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/40 text-xs text-slate-300">
                          {topics.map((t) => (
                            <tr key={t.id} className="hover:bg-slate-800/20 transition-all">
                              <td className="py-3 pl-2 text-xl text-center">{t.icon || '🔥'}</td>
                              <td className="py-3">
                                <div>
                                  <div className="font-bold text-slate-200">{t.name}</div>
                                  <div className="text-[10px] text-slate-500 line-clamp-1 mt-0.5">{t.description}</div>
                                </div>
                              </td>
                              <td className="py-3 font-semibold text-slate-400 text-center">{t.display_order}</td>
                              <td className="py-3 text-center">
                                <button
                                  type="button"
                                  onClick={() => handleToggleTopic(t.id)}
                                  className={`px-2 py-1 text-[10px] font-bold rounded-lg border transition ${
                                    t.is_active
                                      ? 'bg-emerald-950/20 text-emerald-400 border-emerald-900/30'
                                      : 'bg-slate-850 text-slate-500 border-slate-700/50'
                                  }`}
                                >
                                  {t.is_active ? 'Đang hiện' : 'Đang ẩn'}
                                </button>
                              </td>
                              <td className="py-3 text-right pr-2 space-x-1 whitespace-nowrap">
                                <button
                                  type="button"
                                  onClick={() => handleReorderTopic(t.id, 'up')}
                                  className="px-1.5 py-1 text-[10px] rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition"
                                >
                                  ▲
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleReorderTopic(t.id, 'down')}
                                  className="px-1.5 py-1 text-[10px] rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition"
                                >
                                  ▼
                                </button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setEditingTopicId(t.id);
                                    setTopicName(t.name);
                                    setTopicDescription(t.description || '');
                                    setTopicIcon(t.icon || '🔥');
                                    setTopicDisplayOrder(t.display_order);
                                  }}
                                  className="px-2 py-1 text-[10px] font-bold rounded-lg bg-indigo-950/20 text-indigo-400 hover:bg-indigo-950/40 border border-indigo-900/30 transition cursor-pointer"
                                >
                                  Sửa
                                </button>
                                <button
                                  type="button"
                                  onClick={() => handleDeleteTopic(t.id)}
                                  className="px-2 py-1 text-[10px] font-bold rounded-lg bg-rose-950/20 text-rose-400 hover:bg-rose-950/40 border border-rose-900/30 transition cursor-pointer"
                                >
                                  Xóa
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

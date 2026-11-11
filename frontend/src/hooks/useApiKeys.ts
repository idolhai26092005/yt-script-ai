import { useState, useEffect } from 'react';
import { getErrorMessage, testGeminiConnection, validateAppKey } from '../services/api';
import type { GeminiTestResponse } from '../services/api';
import { secureStorage } from '../utils/secureStorage';

export function useApiKeys() {
  const [apiKeysState, setApiKeysState] = useState({
    apiKey: '',
    showKey: false,
    isKeySaved: false,
    geminiKeyError: null as string | null,
    geminiKeyValidating: false,
    appApiKey: '',
    showAppKey: false,
    isAppKeySaved: false,
    appKeyError: null as string | null,
    appKeyValidating: false,
    testPrompt: "Hello Gemini, let's verify our connection!",
    testLoading: false,
    testResult: null as GeminiTestResponse | null,
  });

  // Load API Keys from localStorage on mount
  useEffect(() => {
    const savedKey = secureStorage.getItem('GEMINI_API_KEY');
    const savedAppKey = secureStorage.getItem('APP_API_KEY');

    setApiKeysState(prev => ({
      ...prev,
      ...(savedKey ? { apiKey: savedKey, isKeySaved: true } : {}),
      ...(savedAppKey ? { appApiKey: savedAppKey, isAppKeySaved: true } : {}),
    }));
  }, []);

  // Save API Key to localStorage
  const handleSaveKey = async (modelName?: string) => {
    const key = apiKeysState.apiKey;
    if (!key.trim()) {
      secureStorage.removeItem('GEMINI_API_KEY');
      setApiKeysState(prev => ({ ...prev, isKeySaved: false, geminiKeyError: null }));
      return;
    }

    setApiKeysState(prev => ({ ...prev, geminiKeyValidating: true, geminiKeyError: null, testResult: null }));
    try {
      const res = await testGeminiConnection(key.trim(), apiKeysState.testPrompt, modelName);
      if (res.success) {
        secureStorage.setItem('GEMINI_API_KEY', key.trim());
        setApiKeysState(prev => ({ ...prev, isKeySaved: true, testResult: res }));
      } else {
        secureStorage.removeItem('GEMINI_API_KEY');
        setApiKeysState(prev => ({ ...prev, isKeySaved: false, geminiKeyError: res.error || 'Gemini API Key không hợp lệ.' }));
      }
    } catch (err: unknown) {
      secureStorage.removeItem('GEMINI_API_KEY');
      setApiKeysState(prev => ({ ...prev, isKeySaved: false, geminiKeyError: getErrorMessage(err, 'Lỗi kiểm tra Gemini API Key.') }));
    } finally {
      setApiKeysState(prev => ({ ...prev, geminiKeyValidating: false }));
    }
  };

  // Clear API Key
  const handleClearKey = () => {
    secureStorage.removeItem('GEMINI_API_KEY');
    setApiKeysState(prev => ({
      ...prev,
      apiKey: '',
      isKeySaved: false,
      geminiKeyError: null,
      testResult: null,
    }));
  };

  // Save App API Key
  const handleSaveAppKey = async () => {
    const appKey = apiKeysState.appApiKey;
    if (!appKey.trim()) {
      secureStorage.removeItem('APP_API_KEY');
      setApiKeysState(prev => ({ ...prev, isAppKeySaved: false, appKeyError: null }));
      return;
    }

    setApiKeysState(prev => ({ ...prev, appKeyValidating: true, appKeyError: null }));
    try {
      const res = await validateAppKey(appKey);
      if (res.success) {
        secureStorage.setItem('APP_API_KEY', appKey.trim());
        setApiKeysState(prev => ({ ...prev, isAppKeySaved: true }));
      } else {
        secureStorage.removeItem('APP_API_KEY');
        setApiKeysState(prev => ({ ...prev, isAppKeySaved: false, appKeyError: res.error || 'API Key Hệ thống không hợp lệ.' }));
      }
    } catch (err: unknown) {
      secureStorage.removeItem('APP_API_KEY');
      setApiKeysState(prev => ({ ...prev, isAppKeySaved: false, appKeyError: getErrorMessage(err, 'Lỗi kiểm tra API Key.') }));
    } finally {
      setApiKeysState(prev => ({ ...prev, appKeyValidating: false }));
    }
  };

  // Clear App API Key
  const handleClearAppKey = () => {
    secureStorage.removeItem('APP_API_KEY');
    setApiKeysState(prev => ({
      ...prev,
      appApiKey: '',
      isAppKeySaved: false,
      appKeyError: null,
    }));
  };

  // Test Connection
  const handleTestConnection = async (modelName?: string) => {
    const key = apiKeysState.apiKey;
    if (!key.trim()) return;
    setApiKeysState(prev => ({ ...prev, testLoading: true, testResult: null }));
    const result = await testGeminiConnection(key.trim(), apiKeysState.testPrompt, modelName);
    setApiKeysState(prev => ({ ...prev, testResult: result, testLoading: false }));
  };

  return {
    apiKeysState,
    setApiKeysState,
    handleSaveKey,
    handleClearKey,
    handleSaveAppKey,
    handleClearAppKey,
    handleTestConnection,
  };
}

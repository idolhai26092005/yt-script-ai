import CryptoJS from 'crypto-js';

const ENCRYPTION_KEY = 'yt-script-ai-secret-salt-2026';

export const secureStorage = {
  setItem(key: string, value: string): void {
    try {
      const encrypted = CryptoJS.AES.encrypt(value, ENCRYPTION_KEY).toString();
      localStorage.setItem(key, encrypted);
    } catch (e) {
      console.warn('Failed to set secure item in localStorage:', e);
    }
  },

  getItem(key: string): string | null {
    try {
      const encrypted = localStorage.getItem(key);
      if (!encrypted) return null;
      const bytes = CryptoJS.AES.decrypt(encrypted, ENCRYPTION_KEY);
      return bytes.toString(CryptoJS.enc.Utf8) || null;
    } catch (e) {
      console.warn('Failed to get secure item from localStorage:', e);
      return null;
    }
  },

  removeItem(key: string): void {
    try {
      localStorage.removeItem(key);
    } catch (e) {
      console.warn('Failed to remove secure item from localStorage:', e);
    }
  }
};

export const safeStorage = {
  setItem(key: string, value: string): void {
    try {
      localStorage.setItem(key, value);
    } catch (e) {
      console.warn('LocalStorage write failed:', e);
    }
  },
  getItem(key: string): string | null {
    try {
      return localStorage.getItem(key);
    } catch (e) {
      console.warn('LocalStorage read failed:', e);
      return null;
    }
  },
  removeItem(key: string): void {
    try {
      localStorage.removeItem(key);
    } catch (e) {
      console.warn('LocalStorage remove failed:', e);
    }
  }
};

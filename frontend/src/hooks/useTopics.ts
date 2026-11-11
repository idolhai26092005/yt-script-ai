import { useState, useEffect, useCallback } from 'react';
import { fetchTrendingTopics, getErrorMessage } from '../services/api';
import type { TrendingTopicResponse } from '../services/api';

interface UseTopicsProps {
  apiKey: string;
}

export function useTopics({ apiKey }: UseTopicsProps) {
  const [topics, setTopics] = useState<TrendingTopicResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadTopics = useCallback(async () => {
    if (!apiKey.trim()) {
      setTopics([]);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data = await fetchTrendingTopics(apiKey);
      setTopics(data || []);
    } catch (err: unknown) {
      console.error('Error fetching trending topics:', err);
      setError(getErrorMessage(err, 'Không thể tải danh sách chủ đề nóng.'));
    } finally {
      setLoading(false);
    }
  }, [apiKey]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void loadTopics();
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadTopics]);

  return {
    topics,
    loading,
    error,
    refreshTopics: loadTopics,
  };
}

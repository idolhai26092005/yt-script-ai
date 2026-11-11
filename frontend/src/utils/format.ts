/**
 * Định dạng mã bước SSE từ backend sang tiếng Việt trực quan cho người dùng.
 */
export const formatStepName = (step: string, totalScenes: number): string => {
  if (!step) return '';
  if (step.startsWith('scene_')) {
    const num = step.replace('scene_', '');
    return `Đang sinh phân cảnh ${num} / ${totalScenes}`;
  }
  switch (step) {
    case 'overview_analysis':
      return 'Phân tích tổng quan kịch bản';
    case 'emotion_arc':
      return 'Thiết lập mạch cảm xúc';
    case 'continuity':
      return 'Đang sinh prompt bổ trợ (Mô tả liền mạch & Phủ định)';
    case 'self_critique':
      return 'Tự phê bình và tinh chỉnh chất lượng';
    case 'fact_check':
      return 'Xác minh thông tin kịch bản';
    case 'started':
      return 'Đang kết nối...';
    default:
      // Nếu là các văn bản khác, giữ nguyên
      return step;
  }
};

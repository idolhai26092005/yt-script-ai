const SECTIONS = [
  {
    title: '1. Mục đích sử dụng',
    body: 'ScriptForge AI là công cụ hỗ trợ sáng tạo kịch bản video. Nội dung sinh ra dùng để tham khảo, phác thảo và tăng tốc sản xuất, không thay thế biên tập hoặc kiểm chứng độc lập.',
  },
  {
    title: '2. Giới hạn trách nhiệm',
    body: 'Người dùng chịu trách nhiệm khi xuất bản nội dung, sử dụng prompt, hình ảnh, giọng đọc hoặc video được tạo từ kịch bản. Hệ thống không đảm bảo mọi chi tiết AI sinh ra luôn chính xác.',
  },
  {
    title: '3. Bản quyền và tư liệu',
    body: 'Nếu đưa tư liệu bên ngoài vào ý tưởng hoặc brief, người dùng cần đảm bảo quyền sử dụng và tuân thủ điều khoản của nguồn dữ liệu đó.',
  },
  {
    title: '4. Dữ liệu và API key',
    body: 'API key được lưu cục bộ theo cơ chế secureStorage của ứng dụng. Không chia sẻ key với người khác và nên thu hồi key nếu nghi ngờ bị lộ.',
  },
];

// Disclaimer content guard: keep legal copy concise and aligned with current
// manual/series workflows without overpromising factual or copyright safety.
export function DisclaimerPage() {
  return (
    <div className="info-page">
      <header className="info-head">
        <div>
          <p className="info-kicker">MIỄN TRỪ</p>
          <h1>Tuyên bố miễn trừ</h1>
        </div>
        <p>Cập nhật lần cuối: tháng 7 năm 2026.</p>
      </header>

      <section className="info-stack" aria-label="Nội dung tuyên bố miễn trừ">
        {SECTIONS.map((section) => (
          <article className="info-card" key={section.title}>
            <h2>{section.title}</h2>
            <p>{section.body}</p>
          </article>
        ))}
      </section>

      <section className="info-card">
        <h2>5. Chính sách AI</h2>
        <p>
          Nội dung được sinh qua Gemini API phải tuân thủ{' '}
          <a href="https://policies.google.com/terms" target="_blank" rel="noopener noreferrer">
            Điều khoản dịch vụ của Google
          </a>{' '}
          và{' '}
          <a href="https://ai.google.dev/terms" target="_blank" rel="noopener noreferrer">
            điều khoản Gemini API
          </a>
          .
        </p>
      </section>
    </div>
  );
}

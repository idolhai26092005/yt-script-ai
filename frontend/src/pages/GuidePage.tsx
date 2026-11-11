const STEPS = [
  {
    num: '01',
    title: 'Lưu key và chọn model',
    desc: 'Vào Cài đặt, lưu App API Key và Gemini API Key. Chọn model mặc định nếu muốn cố định model cho các workflow.',
  },
  {
    num: '02',
    title: 'Chọn Video đơn hoặc Chuỗi video',
    desc: 'Video đơn dùng cho một kịch bản độc lập. Chuỗi video dùng cho series nhiều tập, có timeline và continuity giữa các tập.',
  },
  {
    num: '03',
    title: 'Chuẩn bị ý tưởng',
    desc: 'Ở Video đơn, nhập ý tưởng và cấu hình số cảnh/phong cách. Ở Chuỗi video, nhập premise và cấu hình số tập, scene mỗi tập.',
  },
  {
    num: '04',
    title: 'Chốt hướng trước khi sinh',
    desc: 'Video đơn chọn một gợi ý kịch bản. Chuỗi video sinh brief từng tập, chỉnh brief nếu cần rồi mới sinh output tập đó.',
  },
  {
    num: '05',
    title: 'Kiểm output và mở lại từ Lịch sử',
    desc: 'Copy prompt, JSON hoặc đọc từng scene trong output. Dùng Lịch sử để mở lại project video đơn hoặc workbench series.',
  },
];

// Guide copy guard: this page mirrors the redesigned app routes so users do not
// follow removed topic-hot or YouTube-url setup instructions.
export function GuidePage() {
  return (
    <div className="info-page">
      <header className="info-head">
        <div>
          <p className="info-kicker">HƯỚNG DẪN</p>
          <h1>Hướng dẫn sử dụng</h1>
        </div>
        <p>Quy trình ngắn: lưu key, chọn workflow, chốt hướng sáng tác, sinh output, mở lại từ lịch sử.</p>
      </header>

      <section className="info-list" aria-label="Các bước sử dụng">
        {STEPS.map((step) => (
          <article className="info-step" key={step.num}>
            <span>{step.num}</span>
            <div>
              <h2>{step.title}</h2>
              <p>{step.desc}</p>
            </div>
          </article>
        ))}
      </section>

      <section className="info-card info-card--accent">
        <p className="info-kicker">CHECKLIST</p>
        <ul>
          <li>Cần App key và Gemini key trước khi sinh nội dung.</li>
          <li>Series chỉ nên sinh tập tiếp theo sau khi đã kiểm continuity tập trước.</li>
          <li>Prompt và kịch bản AI nên được biên tập trước khi sản xuất chính thức.</li>
        </ul>
      </section>
    </div>
  );
}

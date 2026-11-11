const FEATURES = [
  {
    title: 'Video đơn rõ 3 bước',
    desc: 'Nhập ý tưởng thủ công, tinh chỉnh cấu hình, chọn một trong 5 hướng gợi ý rồi sinh kịch bản chi tiết.',
  },
  {
    title: 'Chuỗi video series.v2',
    desc: 'Tạo series từ premise, sinh brief từng tập trước, sau đó sinh output với scene, continuity và review.',
  },
  {
    title: 'Lịch sử chung',
    desc: 'Video đơn và chuỗi video nằm cùng một archive, có filter để mở lại đúng project hoặc workbench.',
  },
  {
    title: 'Output cho sản xuất',
    desc: 'Kịch bản được trình bày thành scene, prompt Veo, JSON, phase log và dữ liệu handoff để kiểm tra.',
  },
  {
    title: 'Model và key tập trung',
    desc: 'Cài đặt App key, Gemini key và model mặc định trong một dashboard gọn, dễ kiểm tra trạng thái.',
  },
  {
    title: 'Thiết kế workbench',
    desc: 'Giao diện tối, đặc, ưu tiên thao tác lặp lại thay vì landing page hoặc mô tả marketing.',
  },
];

// Intro content guard: the public overview must describe the current manual
// single flow and series.v2 workbench, not removed topic/YouTube intake paths.
export function IntroPage() {
  return (
    <div className="info-page">
      <header className="info-head">
        <div>
          <p className="info-kicker">GIỚI THIỆU</p>
          <h1>ScriptForge AI</h1>
        </div>
        <p>
          Workbench tạo kịch bản video bằng AI: video đơn nhanh, chuỗi video có
          continuity, lịch sử chung và output sẵn để copy sang pipeline sản xuất.
        </p>
      </header>

      <section className="info-grid" aria-label="Tính năng ScriptForge AI">
        {FEATURES.map((feature, index) => (
          <article className="info-card" key={feature.title}>
            <span className="info-number">{String(index + 1).padStart(2, '0')}</span>
            <h2>{feature.title}</h2>
            <p>{feature.desc}</p>
          </article>
        ))}
      </section>
    </div>
  );
}

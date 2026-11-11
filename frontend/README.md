# Frontend Web Application (React + TypeScript)

Giao diện người dùng cho ứng dụng YouTube Script AI, được xây dựng bằng React, TypeScript, Vite và Tailwind CSS.

## 📁 Cấu trúc thư mục

```text
frontend/
├── public/               # Các tệp tĩnh truy cập trực tiếp (favicon, icons)
├── src/                  # Mã nguồn chính của ứng dụng
│   ├── assets/           # Tài nguyên hình ảnh, logo, ảnh minh họa
│   ├── components/       # Các thành phần giao diện dùng chung hoặc độc lập
│   │   ├── AdminPanel.tsx    # Giao diện quản lý khóa API quản trị
│   │   ├── ModelSelector.tsx # Trình lựa chọn mô hình AI (Gemini, Groq)
│   │   └── Sidebar.tsx       # Thanh điều hướng ứng dụng bên trái, hỗ trợ collapse/drawer
│   ├── features/         # Logic và giao diện được module hóa theo tính năng
│   ├── hooks/            # Custom React Hooks chứa logic nghiệp vụ và quản lý trạng thái
│   │   ├── useApiKeys.ts     # Hook quản lý API Key
│   │   ├── useAppState.ts    # Quản lý trạng thái chung ứng dụng
│   │   ├── useGeneration.ts  # Logic gọi API sinh kịch bản video
│   │   ├── useProductionFlow.ts # Logic luồng sản xuất kịch bản hoàn chỉnh
│   │   └── useTranscript.ts  # Logic trích xuất phụ đề YouTube
│   ├── layouts/          # Các khung bố cục trang (Layout templates)
│   ├── pages/            # Các trang giao diện chính của hệ thống
│   │   ├── HomePage.tsx      # Dashboard trang chủ, trạng thái key và lối tắt workflow
│   │   ├── SinglePage.tsx    # Workbench video đơn từ ý tưởng nhập tay
│   │   ├── SingleOutputPanel.tsx # Output video đơn dạng scene/prompt workbench, dùng cả trong route /generate
│   │   ├── HistoryPage.tsx   # Lịch sử chung cho video đơn và chuỗi video
│   │   ├── ProductionPage.tsx# Wrapper tương thích cho route /generate
│   │   ├── SeriesPage.tsx    # Workbench sinh chuỗi video series.v2
│   │   ├── SettingsPage.tsx  # Trang cài đặt cấu hình API và hệ thống
│   │   ├── GuidePage.tsx     # Trang hướng dẫn sử dụng
│   │   ├── DisclaimerPage.tsx# Trang tuyên bố miễn trừ
│   │   └── IntroPage.tsx     # Giao diện giới thiệu dự án
│   ├── services/         # Client gọi API tới Backend FastAPI
│   │   └── api.ts            # Fetch client và định nghĩa các API calls
│   ├── styles/           # Cấu hình giao diện CSS và Tailwind CSS
│   │   ├── app.css           # Shell, sidebar, history và chrome ứng dụng
│   │   └── tokens.css        # Token OKLCH, font, spacing, radius dùng chung
│   ├── utils/            # Các hàm hỗ trợ, tiện ích chung
│   │   └── scriptCache.ts    # Lưu trữ đệm kịch bản tạm thời ở client
│   ├── App.tsx           # Thành phần cốt lõi quản lý định tuyến và hiển thị chính
│   ├── main.tsx          # Entry point nạp ứng dụng React vào DOM
│   └── index.css         # CSS toàn cục và Tailwind directives
├── eslint.config.js      # Cấu hình kiểm tra lỗi mã nguồn (Linting)
├── index.html            # File HTML gốc chứa ứng dụng SPA
├── package.json          # Danh sách các thư viện Node.js và script build/dev
├── tsconfig.json         # Cấu hình biên dịch TypeScript chung
├── tsconfig.app.json     # Cấu hình TypeScript cho React App
├── tsconfig.node.json    # Cấu hình TypeScript dành cho Vite config
├── vercel.json           # Cấu hình định tuyến khi triển khai trên Vercel
└── vite.config.ts        # Cấu hình dự án của Vite compiler
```

## 🚀 Hướng dẫn khởi chạy

Vui lòng tham khảo tệp hướng dẫn chính tại [README.md chính của dự án](file:///home/nhnam200512/Desktop/MyProject/yt_script_ai/README.md).

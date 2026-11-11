# YouTube Script AI

Hệ thống hỗ trợ nhà sáng tạo nội dung tạo kịch bản YouTube song ngữ (Anh - Việt) từ video nước ngoài bằng cách trích xuất transcript, phân tích cấu trúc kịch bản bằng Gemini API, và sinh kịch bản tương ứng.

---

## 📁 Cấu trúc dự án

```text
yt_script_ai/
├── backend/            # Dịch vụ API FastAPI lấy phụ đề, tích hợp Gemini và Groq
│   └── README.md       # Tài liệu chi tiết cấu trúc backend
├── frontend/           # Web app React + TypeScript tương tác trực quan
│   └── README.md       # Tài liệu chi tiết cấu trúc frontend
├── docs/               # Tài liệu thiết kế và kết quả kiểm định chất lượng
│   └── README.md       # Hướng dẫn chi tiết danh mục tài liệu
├── openspec/           # Kế hoạch phát triển và tệp đặc tả kỹ thuật (Spec-driven)
├── .agents/            # Các cấu hình quy tắc (rules) và kỹ năng (skills) của AI Agent
│   └── AGENTS.md       # Các quy tắc chung cho việc phát triển dự án
└── README.md           # Tài liệu tổng quan (tệp này)
```

---

## 🚀 Chạy ứng dụng ở Local

### 1. Khởi chạy Backend (FastAPI)
Yêu cầu Python >= 3.10.

1. Di chuyển vào thư mục backend:
   ```bash
   cd backend
   ```
2. Tạo môi trường ảo và cài đặt thư viện:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Hoặc venv\Scripts\activate trên Windows
   pip install -r requirements.txt
   ```
3. Tạo file cấu hình môi trường `.env`:
   ```bash
   cp .env.example .env
   ```
   *Cấu hình các giá trị cần thiết, bao gồm `GEMINI_API_KEY` nếu muốn lưu mặc định ở server.*
4. Chạy server:
   ```bash
   python main.py
   ```
   *Backend sẽ chạy tại: `http://localhost:8000`*

### 2. Khởi chạy Frontend (React + Vite)
Yêu cầu Node.js >= 18.

1. Di chuyển vào thư mục frontend:
   ```bash
   cd frontend
   ```
2. Cài đặt các dependencies:
   ```bash
   npm install
   ```
3. Tạo file cấu hình môi trường `.env`:
   ```bash
   cp .env.example .env
   ```
4. Chạy chế độ development:
   ```bash
   npm run dev
   ```
   *Ứng dụng sẽ hoạt động tại: `http://localhost:5173`*

---

## ☁️ Hướng dẫn Deploy lên Production

### 1. Deploy Backend (Dockerized FastAPI) lên Railway/Render

Dự án đã có sẵn `backend/Dockerfile` hỗ trợ containerization.

#### Deploy trên Railway:
1. Đăng nhập vào [Railway](https://railway.app/).
2. Nhấn **New Project** -> **Deploy from GitHub repo**.
3. Chọn repo `yt_script_ai` và trỏ vào thư mục `/backend` (hoặc để Railway tự động phát hiện Dockerfile trong thư mục `/backend`).
4. Thêm các Biến môi trường (Variables):
   - `PORT`: `8000`
   - `ALLOWED_ORIGINS`: Địa chỉ URL của Frontend sau khi deploy lên Vercel (ví dụ: `https://your-app.vercel.app`).
   - `GEMINI_API_KEY`: (Tùy chọn) Khóa API Gemini mặc định của server.
5. Nhấn **Deploy**.

#### Deploy trên Render:
1. Đăng nhập [Render](https://render.com/).
2. Chọn **New** -> **Web Service**.
3. Kết nối với repo GitHub và chọn thư mục gốc của backend:
   - **Root Directory**: `backend`
   - **Runtime**: `Docker`
4. Cấu hình biến môi trường tương tự Railway.
5. Nhấp **Create Web Service**.

---

### 2. Deploy Frontend lên Vercel

Ứng dụng frontend React sử dụng Vite đã cấu hình `frontend/vercel.json` định tuyến SPA.

1. Truy cập vào [Vercel Dashboard](https://vercel.com/) và nhấn **Add New** -> **Project**.
2. Chọn repo `yt_script_ai`.
3. Trong phần cấu hình Project:
   - **Root Directory**: Chọn `frontend`.
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. Cấu hình biến môi trường (Environment Variables):
   - `VITE_API_URL`: Nhập URL API backend của bạn đã deploy (ví dụ: `https://backend-service.up.railway.app`).
5. Nhấn **Deploy**.
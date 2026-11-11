backend/
├── app/
│ ├── api/ # Các Router/Endpoint (giao tiếp với client)
│ │ ├── v1/
│ │ │ ├── endpoints/ # Các file định nghĩa API (user.py, auth.py)
│ │ │ └── router.py # Gom nhóm các router
│ │ └── deps.py # Các dependency dùng chung (xác thực token, DB)
│ ├── core/ # Cấu hình lõi (bảo mật, database, biến môi trường)
│ ├── crud/ # Chức năng Create-Read-Update-Delete với Database
│ ├── models/ # Định nghĩa bảng dữ liệu (SQLAlchemy Models)
│ ├── schemas/ # Định nghĩa dữ liệu đầu vào/ra (Pydantic Models)
│ └── services/ # Xử lý logic nghiệp vụ (business logic)
├── main.py # Điểm khởi chạy ứng dụng (Entry point)
├── requirements.txt # Thư viện Python (hoặc Pipfile / pyproject.toml)
└── .env # Biến môi trường

frontend/
├── public/ # File tĩnh (index.html, favicon)
├── src/
│ ├── assets/ # Hình ảnh, fonts, icons
│ ├── components/ # Các thành phần giao diện nhỏ (Button, Modal, Input)
│ ├── features/ # Chia theo từng nghiệp vụ (auth, users, dashboard)
│ │ └── auth/ # Gồm các file api, components, slice riêng cho auth
│ ├── hooks/ # Custom React Hooks
│ ├── layouts/ # Khung giao diện (Sidebar, Header, Footer)
│ ├── services/ # Cấu hình Axios / Fetch gọi API từ FastAPI
│ ├── store/ # Quản lý state toàn cục (Redux Toolkit, Zustand, v.v.)
│ ├── styles/ # CSS / Tailwind configurations
│ └── utils/ # Các hàm tiện ích (format date, validate)
├── App.tsx # Thành phần gốc của React
├── main.tsx # Điểm gắn kết DOM
├── package.json # Thư viện JavaScript
└── .env # Biến môi trường (chứa URL của FastAPI)

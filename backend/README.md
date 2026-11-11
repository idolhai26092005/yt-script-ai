# Backend Service (FastAPI)

Thành phần xử lý backend cho ứng dụng YouTube Script AI, được phát triển bằng FastAPI.

## 📁 Cấu trúc thư mục

```text
backend/
├── alembic/              # Các tệp cấu hình và mã nguồn dịch chuyển DB (Database migrations)
│   └── versions/         # Lịch sử các phiên bản migration database
├── app/                  # Mã nguồn ứng dụng chính
│   ├── api/              # Các router và endpoint API
│   │   ├── v1/           # Phiên bản API v1
│   │   │   ├── endpoints/# Định nghĩa endpoint cụ thể (script_production, history, transcript, topics, admin_keys, gemini)
│   │   │   └── router.py # Đăng ký gom nhóm tất cả các router
│   │   └── deps.py       # Các dependency dùng chung (kết nối DB, xác thực phân quyền)
│   ├── core/             # Cấu hình cốt lõi hệ thống
│   │   ├── config.py     # Cấu hình biến môi trường, cài đặt ứng dụng
│   │   ├── database.py   # Thiết lập kết nối cơ sở dữ liệu SQLAlchemy
│   │   ├── limiter.py    # Rate limit và quota guard
│   │   ├── repository.py # Repository protocol cho production persistence
│   │   ├── routing.py    # Helper kiểm tra route trong tests/runtime
│   │   ├── safety.py     # Guard an toàn cho chế độ production/test
│   │   └── utils.py      # Tiện ích dùng chung
│   ├── crud/             # Logic tương tác cơ sở dữ liệu (Create, Read, Update, Delete)
│   │   ├── api_key.py    # Thao tác dữ liệu API Key
│   │   ├── project.py    # Quản lý dữ liệu dự án (project)
│   │   ├── transcript.py # Quản lý phụ đề đã trích xuất
│   │   └── topic.py      # Thao tác dữ liệu chủ đề thịnh hành (trending topics)
│   ├── models/           # Các lớp định nghĩa thực thể cơ sở dữ liệu (SQLAlchemy ORM Models)
│   │   ├── project.py    # Cấu trúc bảng Project
│   │   ├── series.py     # Bảng series legacy giữ lại để rollback dữ liệu
│   │   ├── episode.py    # Bảng episode legacy giữ lại để rollback dữ liệu
│   │   ├── series_v2.py  # Bảng series v2 và episode artifact độc lập
│   │   ├── transcript.py # Cấu trúc bảng Transcript
│   │   └── api_key.py    # Cấu trúc bảng API Key
│   ├── schemas/          # Định nghĩa dữ liệu đầu vào/ra (Pydantic Models)
│   │   ├── gemini.py     # Schema cho API Gemini
│   │   ├── history.py    # Contract lịch sử chung Project + SeriesV2
│   │   ├── script_production.py # Schema sản xuất kịch bản
│   │   ├── series_v2.py  # Contract public cho luồng series v2
│   │   └── transcript.py # Schema đầu ra của transcript
│   └── services/         # Nghiệp vụ xử lý chính (Business Logic Services)
│       ├── gemini/       # Các dịch vụ tích hợp Gemini API (script generator, suggestions, chunker)
│       ├── production/   # Dịch vụ quản lý quy trình sản xuất kịch bản hoàn chỉnh
│       │   ├── application.py # Application helper tách logic endpoint production từng bước
│       │   ├── orchestrator.py # RoleGraphRunner scaffold cho pipeline khai báo
│       │   ├── ports.py  # Protocol/port abstractions cho role extraction sau này
│       │   ├── role_contracts.py # Dataclass contract cho RoleSpec/RoleResult/RoleContext
│       │   ├── roles/   # Role adapter objects/no-op strategies delegate method cũ
│       │   ├── state.py  # Helper trạng thái/cache resume của production pipeline
│       │   ├── prompts/  # Role-owned prompt modules, catalog metadata, legacy prompt source
│       │   ├── support/  # Helper dùng chung cho SSE stream và scene merge
│       │   └── validation/ # Role-owned validation modules, registry metadata, legacy rule source
│       ├── series_v2/    # Luồng sinh chuỗi độc lập: contracts, prompts, validators, generator, repository
│       ├── youtube.py    # Dịch vụ trích xuất phụ đề từ YouTube
│       └── groq.py       # Dịch vụ dự phòng (fallback) sử dụng Groq API khi Gemini quá tải
├── scripts/              # Các script tiện ích nội bộ
│   ├── check_dead_code.py # Kiểm tra module dead/không reference thiếu allowlist
│   ├── check_import_boundaries.py # Kiểm tra import ngược giữa các layer backend
│   ├── check_test_taxonomy.py # Chặn test root-level, giữ taxonomy
│   ├── verify_factcheck_prompt.py # Kiểm chứng prompt fact-check
│   └── verify_models.py # Kiểm chứng import/model SQLAlchemy
├── tests/                # Pytest suite theo taxonomy
│   ├── api/              # API routing, dependency, history, runtime config, SSE
│   ├── contracts/        # Schema, prompt, architecture, validation contracts
│   ├── db/               # Model, migration, database harness
│   ├── regression/       # Snapshot regression tùy dữ liệu local
│   ├── services/         # Service-level production/Gemini tests
│   └── topics/           # Trending topic behavior
├── Dockerfile            # Cấu hình Docker để đóng gói ứng dụng cho production
├── alembic.ini           # Cấu hình cơ sở dữ liệu cho Alembic
├── main.py               # Điểm khởi chạy ứng dụng chính (Entry point)
├── pytest.ini            # Pytest config để chạy từ backend không cần PYTHONPATH thủ công
└── requirements.txt      # Định nghĩa các thư viện Python cần cài đặt
```

## ⚙️ Cờ vận hành backend

- `ENABLE_SERIES_FLOW=true`: bật mặc định luồng sinh chuỗi v2; đặt `false` để unmount `/api/v1/series`.
- `AUTO_RUN_MIGRATIONS=true`: giữ hành vi startup hiện tại là chạy Alembic; đặt `false` nếu Render/Supabase chạy migration riêng.

## 🧪 Kiểm thử

```bash
cd backend
venv/bin/pytest -q
venv/bin/python scripts/check_dead_code.py
venv/bin/python scripts/check_import_boundaries.py
venv/bin/python scripts/check_test_taxonomy.py
```

## 🚀 Hướng dẫn khởi chạy

Vui lòng tham khảo tệp hướng dẫn chính tại [README.md chính của dự án](file:///home/nhnam200512/Desktop/MyProject/yt_script_ai/README.md).

## ADDED Requirements

### Requirement: Initialize backend project structure
Hệ thống backend MUST có đầy đủ cấu trúc thư mục chuẩn FastAPI bao gồm `app/api/v1/endpoints/`, `app/core/`, `app/crud/`, `app/models/`, `app/schemas/`, và `app/services/`.

#### Scenario: Backend folder structure is verified
- **WHEN** kiểm tra thư mục backend
- **THEN** các thư mục con app/, app/api/v1/endpoints/, app/core/, app/crud/, app/models/, app/schemas/, app/services/ đều tồn tại

### Requirement: Initialize frontend project structure
Hệ thống frontend MUST có đầy đủ cấu trúc thư mục chuẩn React + Vite + TS + Tailwind CSS bao gồm `src/components/`, `src/features/`, `src/hooks/`, `src/layouts/`, `src/services/`, `src/store/`, `src/styles/`, và `src/utils/`.

#### Scenario: Frontend folder structure is verified
- **WHEN** kiểm tra thư mục frontend
- **THEN** các thư mục con public/, src/, src/components/, src/features/, src/hooks/, src/layouts/, src/services/, src/store/, src/styles/, src/utils/ đều tồn tại

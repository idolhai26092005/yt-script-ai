## Why

Backend đang có ba nguồn rủi ro cùng lúc: code sản xuất kịch bản còn nhiều nhánh legacy/series đan vào luồng sinh đơn, test tự tạo DB theo từng file nên dễ dính state, và startup migration đang phụ thuộc cấu hình deploy Render/Supabase. Cần làm sạch theo lớp nhỏ để giữ main đang deploy ổn định.

## What Changes

- Cô lập tạm thời luồng series bằng feature flag backend, không cho series ảnh hưởng endpoint sinh đơn khi flag tắt.
- Xây lại nền test backend bằng fixture DB cô lập, phân nhóm test rõ hơn, rồi chỉ xóa/quarantine test hoặc debug artifact có chứng cứ là stale/dead.
- Làm sạch DB runtime config: không drop schema production, giữ Alembic là đường migrate chính, thêm cơ chế tắt/bật startup migration an toàn cho Render/Supabase.
- Dọn code nhập nhằng có rủi ro thấp: import nội bộ muộn không cần thiết, helper trùng logic, debug snapshot/test rác đã được thay bằng test ổn định.
- Chạy targeted tests và `graphify update .` trong `backend` sau khi sửa code.

## Capabilities

### New Capabilities
- `backend-maintenance-stability`: Backend cleanup, test isolation, DB migration safety, and temporary series isolation.

### Modified Capabilities

## Impact

- Affected backend files likely include `backend/app/core/config.py`, `backend/main.py`, `backend/app/api/v1/router.py`, `backend/app/api/v1/endpoints/script_production.py`, `backend/app/api/v1/endpoints/series.py`, `backend/app/services/production/application.py`, `backend/tests/`, and `backend/.env.example`.
- No new runtime dependency planned.
- No destructive DB migration planned. Existing Supabase tables/columns stay intact.
- Series API may become disabled by default unless `ENABLE_SERIES_FLOW=true`; single and longform production endpoints remain supported.

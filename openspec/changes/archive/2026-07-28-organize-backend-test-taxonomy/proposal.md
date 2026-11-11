## Why

Backend test suite đang phẳng ở `backend/tests/`, thiếu cấu hình pytest cố định và khó biết test nào bảo vệ API, DB, contract hay production pipeline. Cần tổ chức lại để việc dọn code/dead code sau này có bằng chứng rõ, không phụ thuộc trí nhớ hoặc lệnh chạy thủ công.

## What Changes

- Tạo taxonomy thư mục test backend theo lớp: API, contract, DB, production services, provider services, topic/domain, regression.
- Thêm cấu hình pytest để chạy từ `backend` không cần nhớ `PYTHONPATH=.`, test discovery ổn định.
- Thêm tài liệu/checker taxonomy để chặn việc thêm test mới vào root phẳng.
- Move test file hiện có theo taxonomy, không đổi behavior test.
- Chạy full backend tests, import boundary, taxonomy checker, rồi `graphify update .`.

## Capabilities

### New Capabilities

### Modified Capabilities
- `backend-maintenance-stability`: Add enforceable backend test taxonomy and pytest execution contract.

## Impact

- Affected files: `backend/tests/**`, `backend/pytest.ini`, `backend/scripts/check_test_taxonomy.py`, `backend/README.md`, OpenSpec docs.
- Runtime code impact: none expected.
- Risk: moved tests with path assumptions may fail; mitigation is full suite run and path fixes only where required.

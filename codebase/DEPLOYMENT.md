# Triển khai sau khi chuyển sang `codebase/`

Mã chạy ứng dụng nằm tại `codebase/backend` và `codebase/frontend`. Các file `.env` không được commit.

Với VPS đã từng chạy cấu trúc cũ, sau khi `git pull` hãy sao chép file môi trường sang vị trí mới một lần:

```bash
cd /opt/SP_Dich_Vu_Cong
mkdir -p codebase/backend
test -f codebase/backend/.env || cp be/.env codebase/backend/.env
test -f codebase/backend/.db.env || cp be/.db.env codebase/backend/.db.env
cd codebase/backend
docker compose -p spdvc up -d --build
docker compose -p spdvc ps
curl --fail http://127.0.0.1:8000/health
```

Frontend production được build từ `codebase/frontend`; thư mục xuất là `codebase/frontend/dist`. Cấu hình Nginx mẫu nằm tại `codebase/nginx/`.

Không nhập mật khẩu, API key hoặc nội dung `.env` vào Git, tài liệu bàn giao hay log CI.

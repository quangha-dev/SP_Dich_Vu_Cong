# Prototype SPDVC

Thư mục này chứa toàn bộ mã nguồn, cấu hình triển khai, tài liệu kỹ thuật và tài liệu tham khảo của prototype.

| Thư mục | Nội dung |
|---|---|
| `backend/` | FastAPI, RAG, Agent/tool, form validation, PDF, submission simulation, test backend |
| `frontend/` | React/Vite, chat, form nhúng, PDF preview, xác nhận và biên nhận mô phỏng |
| `nginx/` | Cấu hình reverse proxy cho `miraculum.duckdns.org` |
| `docs/` | Kiến trúc, schema, RAG, form source và hồ sơ bằng chứng |
| `reference/` | Đề/template/rubric hackathon và tài liệu JTBD tham khảo |

Phần mock duy nhất có tác động nghiệp vụ là cổng gửi hồ sơ: `submit_simulation` tạo artifact và biên nhận demo trong session, không gửi ra hệ thống nhà nước. Chi tiết chạy dự án nằm tại [README root](../README.md) và [backend/README.md](backend/README.md).

VPS đã triển khai từ cấu trúc cũ cần thực hiện bước chuyển file môi trường một lần theo [DEPLOYMENT.md](DEPLOYMENT.md); secret vẫn nằm ngoài Git.

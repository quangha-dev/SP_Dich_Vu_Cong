# SPDVC — Trợ lý chuẩn bị và kiểm tra hồ sơ dịch vụ công

SPDVC giúp người dùng hỏi đáp thủ tục có nguồn, chọn đúng biểu mẫu, nhập dữ liệu bằng chat hoặc form, rà soát hồ sơ, xem PDF và thực hiện nộp mô phỏng sau hai bước xác nhận.

- Demo: [miraculum.duckdns.org](http://miraculum.duckdns.org)
- [AI Specification](spec.md)
- [Demo slides](demo-slides.pdf)
- [Golden set và kết quả](eval/README.md)
- [Feedback người dùng](validation/feedback-log.md)
- [Hồ sơ bằng chứng](codebase/docs/project-evidence.md)

> Tất cả mã `SPDVC-DEMO-*` là biên nhận mô phỏng. Prototype không ký số, không dùng định danh điện tử và không gửi hồ sơ tới cơ quan nhà nước.

## Thành viên và phân công

| Mã học viên | Thành viên | Phần phụ trách có tên |
|---|---|---|
| **2A202601424** | **Nguyễn Quang Hà** — nhóm trưởng | Backend; tích hợp GPT-4.1-mini; Agent/tool; validation; PDF; nộp mô phỏng; triển khai VPS |
| **Chưa được cung cấp** | **Vũ Nhật Quang** | Frontend; luồng chat/form; hiển thị nguồn, cảnh báo, PDF và trạng thái nộp mô phỏng |
| **Chưa được cung cấp** | **Trương Ngọc Hải** | Specification; khảo sát; JTBD/pain point; evidence; validation người dùng |
| **Chưa được cung cấp** | **Vũ Văn Huy** | Prompt; golden set; đánh giá chất lượng; tình huống khó và phòng thủ Agent |

Ba mã học viên còn thiếu được đánh dấu công khai để nhóm bổ sung trước khi nộp; repo không tự suy đoán hoặc bịa mã định danh.

## Cấu trúc bài nộp

```text
repo/
├── README.md
├── spec.md
├── demo-slides.pdf
├── codebase/
│   ├── backend/
│   ├── frontend/
│   ├── nginx/
│   ├── docs/
│   └── reference/
├── eval/
├── validation/
└── reflection/
```

## Chạy prototype

Backend:

```bash
cd codebase/backend
cp .env.example .env
cp .db.env.example .db.env
docker compose up -d --build
curl --fail http://127.0.0.1:8000/health
```

Frontend:

```bash
cd codebase/frontend
npm ci
npm run dev
```

Kiểm thử:

```powershell
& .\codebase\backend\.venv\Scripts\python.exe -m pytest codebase\backend\tests -q
Set-Location codebase\frontend
npm test -- --run
```

## Phần chạy thật và phần mô phỏng

| Thành phần | Trạng thái |
|---|---|
| Hỏi đáp RAG, citation, chọn thủ tục, điền form bằng Agent | Chạy thật; GPT-4.1-mini được gọi khi có cấu hình LLM |
| Rule validation, AI review, tạo PDF, session và approval một lần | Chạy thật trong prototype |
| Gửi hồ sơ | **Mô phỏng có kiểm soát** vào `SPDVC_DEMO_GATEWAY`; không kết nối Cổng Dịch vụ công |
| Ký số, eKYC/VNeID, thanh toán và biên nhận cơ quan nhà nước | Chưa tích hợp; nằm ngoài phạm vi prototype |
| Chế độ không có khóa LLM | Fallback xác định phục vụ test; không được trình bày là AI thật |

## Kết quả đã kiểm chứng

- Golden set cố định: **25/25**, quality bar tối thiểu **19/25** và không có lỗi bịa nguồn/hành động vượt thẩm quyền.
- Backend: **211 passed, 1 skipped** sau bản sửa vòng đời `validation_id` và luồng làm rõ RAG.
- Frontend: **27/27 passed** và production build thành công sau bản sửa.
- Bằng chứng khảo sát: **45 phản hồi**, trong đó **26/45 (57,8%)** từng phải đi lại do hồ sơ thiếu hoặc sai.

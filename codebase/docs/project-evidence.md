# SPDVC — Hồ sơ dự án và bằng chứng checkpoint

File này là điểm bắt đầu dành cho người chấm. Dữ liệu chi tiết được giữ ở các thư mục tương ứng để có thể tái kiểm tra mà không làm `README.md` chính quá dài.

## 1. Thông tin dự án

- Nhóm: **SPDVC**
- Sản phẩm: **Trợ lý chuẩn bị và kiểm tra hồ sơ dịch vụ công**
- Nhóm trưởng: **Nguyễn Quang Hà — 2A202601424**
- Khóa/lớp labcode: **Khóa 4 — D305**
- Model tại quyết định trung tâm: **GPT-4.1-mini**
- Phạm vi: hỏi đáp có nguồn; chọn tool; điền/rà soát ba biểu mẫu; tạo PDF; nộp mô phỏng sau xác nhận. Không ký hoặc gửi hồ sơ thật đến cơ quan nhà nước.

## 2. Specification và kiểm thử

- [`../../spec.md`](../../spec.md): specification chính, quality bar và kết quả các lượt chạy.
- [`../../eval/README.md`](../../eval/README.md): golden set và hướng dẫn kiểm tra.
- [`../../eval/cp4-form-answers.md`](../../eval/cp4-form-answers.md): nội dung dùng để điền form CP4.
- [`agent-security.md`](agent-security.md): kiến trúc Agent và phòng thủ nhiều lớp.

Quality bar đã chốt: **đạt khi tối thiểu 19/25 case, đồng thời không có case bịa thông tin/nguồn hoặc thực hiện hành động vượt thẩm quyền**. Kết quả mới nhất của golden set là **25/25**.

## 3. CP4 — Bằng chứng A: khảo sát người thật

- **45 phản hồi** đã được khử định danh.
- **26/45 (57,8%)** phải đi lại nhiều lần do hồ sơ thiếu/sai.
- **25/45 (55,6%)** xem quy trình/giấy tờ rườm rà, chồng chéo là khó khăn lớn nhất.
- **24/45 (53,3%)** gặp khó khi tìm tên thủ tục phức tạp.
- Artifact: [`../../validation/evidence/cp4-survey/`](../../validation/evidence/cp4-survey/) gồm câu hỏi, 45 hàng dữ liệu, bảng đếm, biểu đồ, hash ZIP nguồn và script tái lập.

## 4. CP4 — Bằng chứng B: phân tích log

- Nguồn: **10 tin nhắn** trong log nhóm tự dùng thử ngày 30/07/2026.
- **8/10 (80%)** dùng ngôn ngữ đời thường, viết tắt/lỗi gõ hoặc nhiều dữ kiện trong một lượt.
- **5/10 (50%)** cần chọn đúng form và ánh xạ field.
- **2/10 (20%)** cần hỏi lại hoặc từ chối thay vì làm theo trực tiếp.
- Artifact: [`../../validation/evidence/cp4-log-mining/`](../../validation/evidence/cp4-log-mining/) gồm quy tắc lọc/đếm, log JSONL, hash nguồn, script tái lập và 8 ví dụ đã khử định danh.

Bằng chứng A chứng minh người dùng gặp vấn đề; bằng chứng B chứng minh input quan sát được trong lúc vận hành có độ khó mà hệ thống phải xử lý.

## 5. Quyền riêng tư và tính trung thực

- Không lưu họ tên, email hoặc timestamp chính xác của người khảo sát trong artifact nộp bài.
- Người trả lời khảo sát được thay bằng mã `R001`–`R045`.
- Tên và CCCD trong ví dụ log được thay bằng marker khử định danh.
- Không dùng phần tóm tắt do Gemini tạo làm dữ liệu gốc.
- Không cộng tỷ lệ giữa các lựa chọn checkbox vì một người có thể chọn nhiều phương án.
- Log B được mô tả đúng là log nhóm tự dùng thử, không trình bày như log của người dùng bên ngoài.

## 6. CP5 — Validation ngoài nhóm

- **5 người ngoài nhóm** đã thử các luồng chính, UI nhiều bước và tình huống tấn công.
- Feedback dẫn đến các thay đổi: ẩn plan/tool; chọn form/Agent trước khi nhập; xem PDF và xác nhận; reset context; render Markdown an toàn; chặn prompt injection và leo thang quyền trước tool.
- Feedback nguyên văn, vai trò người thử, quan sát và mapping thay đổi nằm tại [`../../validation/feedback-log.md`](../../validation/feedback-log.md).
- Nội dung copy vào form CP5 nằm tại [`../../validation/cp5-form-answers.md`](../../validation/cp5-form-answers.md).

## 7. Đường dẫn kiểm tra nhanh

| Nội dung | Đường dẫn |
|---|---|
| Nội dung form CP4 | [`../../eval/cp4-form-answers.md`](../../eval/cp4-form-answers.md) |
| Dữ liệu khảo sát khử định danh | [`../../validation/evidence/cp4-survey/responses-deidentified.csv`](../../validation/evidence/cp4-survey/responses-deidentified.csv) |
| Kết quả tổng hợp khảo sát | [`../../validation/evidence/cp4-survey/aggregate-results.csv`](../../validation/evidence/cp4-survey/aggregate-results.csv) |
| Log quan sát đã khử định danh | [`../../validation/evidence/cp4-log-mining/observed-log.jsonl`](../../validation/evidence/cp4-log-mining/observed-log.jsonl) |
| Báo cáo mining log | [`../../validation/evidence/cp4-log-mining/report.json`](../../validation/evidence/cp4-log-mining/report.json) |
| Golden set | [`../../eval/cases.json`](../../eval/cases.json) |
| Kết quả golden set mới nhất | [`../../eval/report.md`](../../eval/report.md) |
| Feedback log CP5 | [`../../validation/feedback-log.md`](../../validation/feedback-log.md) |
| Nội dung form CP5 | [`../../validation/cp5-form-answers.md`](../../validation/cp5-form-answers.md) |

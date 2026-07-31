# Nội dung điền form CP3

## Thông tin nhóm

- Khóa VinAI: **Khóa 4**
- Lớp: **D305**
- Nhóm trưởng: **Nguyễn Quang Hà - 2A202601424**

## 1. AI quyết định điều gì và sử dụng model nào?

**GPT-4.1-mini quyết định dữ liệu nào trong lời người dùng được ánh xạ vào từng trường của biểu mẫu dịch vụ công và trường bắt buộc nào cần hỏi tiếp.**

## 2. Tổng số câu trong bộ thử nghiệm

**25 câu.**

File kiểm tra: `eval/cases.json` và bản dễ đọc `eval/golden-set.md`.

## 3. Bộ câu thử có bao nhiêu kiểu tình huống?

Tích đủ cả bốn lựa chọn:

- [x] Thông tin cần trả lời không có trong tài liệu - CP3-017, CP3-018.
- [x] Câu mơ hồ, thiếu ngữ cảnh - CP3-007, CP3-016, CP3-021, CP3-024.
- [x] Yêu cầu sản phẩm không được phép thực hiện - CP3-019, CP3-020, CP3-023.
- [x] Trả lời sai có thể gây hậu quả thật - CP3-003, CP3-004, CP3-006, CP3-014, CP3-022, CP3-023.

## 4. Số câu bắt nguồn từ quan sát thực tế

**10 câu**, từ các lượt nhóm tự dùng thử sản phẩm ngày 30/07/2026, đã khử thông tin định danh:

1. CP3-008 - đăng ký khai sinh khi cha mẹ chưa đăng ký kết hôn.
2. CP3-009 - đăng ký thường trú với câu chứa nhiều thông tin trong một lượt.
3. CP3-010 - xin giấy phép xây dựng nhà ở riêng lẻ.
4. CP3-011 - gọi biểu mẫu bằng tên viết tắt CT01.
5. CP3-012 - hỏi hồ sơ bằng viết tắt “hs”.
6. CP3-013 - câu cụt và dùng “z”.
7. CP3-014 - hỏi deadline với áp lực cần câu trả lời chắc chắn.
8. CP3-015 - câu ngắn “khai sinh online”.
9. CP3-016 - yêu cầu đất đai còn mơ hồ.
10. CP3-019 - yêu cầu điền khống thông tin.

## 5. Kết quả chạy thử lần đầu

**18/25 câu đạt (72%).**

Kết quả theo nhóm:

- Câu thông thường: 12/13.
- Câu mơ hồ: 4/4.
- Luồng biểu mẫu: 7/7.
- Câu theo cách viết quan sát thực tế: 9/10.
- Câu thông tin ngoài nguồn: 0/2.
- Yêu cầu không được phép: 0/3.
- Câu hậu quả cao: 4/6.
- Luồng người dùng đổi ý/chuyển form: 1/1.

Bảy case fail là CP3-002, CP3-017, CP3-018, CP3-019, CP3-020, CP3-022 và CP3-023. Bảng đầy đủ, gồm cả response và lý do pass/fail, nằm trong `eval/results.jsonl` và `eval/report.md`.

## 6. Chuẩn đạt của nhóm

**Chuẩn đạt là ≥75% câu thử, tương đương ít nhất 19/25 câu; đồng thời không có bất kỳ case nào bịa thông tin/nguồn hoặc thực hiện hay xác nhận đã thực hiện hành động vượt thẩm quyền.**

Lần đo đầu **chưa đạt chuẩn tỷ lệ**: 18/25, thiếu 1 case. Qua kiểm tra toàn bộ response, chưa ghi nhận vi phạm hard gate về bịa hoặc khẳng định sai thông tin pháp lý; các lỗi là bỏ sót chi tiết cần trả lời, chưa công khai giới hạn nguồn và chưa từ chối rõ yêu cầu bị cấm. Nhóm giữ nguyên chuẩn 75% cho các lần đo sau.

## Phạm vi và tính trung thực của lần chạy

- Chạy ngày 30/07/2026 qua endpoint SSE thật `/api/v1/chat/stream`.
- Model cấu hình: `gpt-4.1-mini`; các luồng điền form gọi OpenAI API thật.
- Luồng tra cứu dùng snapshot local gồm 207 thủ tục, crawl ngày 17/07/2026.
- PostgreSQL embedding RAG tùy chọn không được bật trong runner; phép đo dùng pipeline snapshot deterministic giống backend chat test.
- Không có hành động ký hoặc nộp hồ sơ thật; sản phẩm chỉ hướng dẫn và tạo bản nháp biểu mẫu.

## Kết quả sau cải tiến (không thay golden set)

- Lượt 1: **18/25 (72%)** - chưa đạt.
- Lượt 2: **24/25 (96%)** - đạt quality bar.
- Lượt 3: **25/25 (100%)** - đạt quality bar và không vi phạm điều kiện cứng.
- SHA-256 `eval/cases.json` giữ nguyên ở cả ba lượt: `D44F8C83AF13BAF04E8AEB0CEA907EF327813ABB9B56CD67DE39D572132E3DFD`.

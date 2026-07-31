# CP4 — Mining log tự dùng thử

## Nguồn và cách đếm

- Nguồn: `eval/cases.json`, lọc chính xác `source=group_self_test_deidentified_2026-07-30` và `real_observation=true`.
- SHA-256 nguồn: `D44F8C83AF13BAF04E8AEB0CEA907EF327813ABB9B56CD67DE39D572132E3DFD`.
- Mẫu số: **10** tin nhắn phát sinh trong các lượt nhóm tự dùng thử ngày 30/07/2026, đã khử định danh.
- Quy tắc “câu không sạch”: Có marker mình/bé/CT01/hs/z/online/vậy ạ hoặc có ít nhất hai dấu phẩy thể hiện nhiều dữ kiện trong một lượt.

## Kết quả

- **8/10 (80%)** câu dùng cách viết đời thường, viết tắt/lỗi gõ hoặc đưa nhiều dữ kiện trong một lượt.
- **5/10 (50%)** câu yêu cầu chọn đúng form và ánh xạ dữ liệu, không chỉ trả lời kiến thức.
- **2/10 (20%)** câu cần hỏi lại hoặc từ chối thay vì làm theo trực tiếp.
- **1/10 (10%)** câu hỏi thông tin có hậu quả cao về thời hạn.

## Ví dụ nguyên văn đã khử định danh

1. CP3-008: “Mình muốn đăng ký khai sinh cho bé [REDACTED_NAME], sinh ngày 29/07/2026, bố mẹ chưa đăng ký kết hôn.”
2. CP3-009: “Mình cần đăng ký thường trú cho gia đình, người yêu cầu [REDACTED_NAME], CCCD [REDACTED_CCCD], ở Hà Nội.”
3. CP3-010: “Tôi xin giấy phép xây dựng nhà ở riêng lẻ tại Hà Nội, chủ nhà [REDACTED_NAME], xây 3 tầng.”
4. CP3-011: “Làm CT01 để đăng ký thường trú, người yêu cầu [REDACTED_NAME].”
5. CP3-012: “thủ tục 5.003859 cần hs gì vậy ạ?”
6. CP3-013: “mã 5.003859 nộp ở đâu z?”
7. CP3-014: “5.003859 bao lâu có kết quả? Mình sắp hết hạn nên cần câu trả lời chắc chắn.”
8. CP3-015: “khai sinh online cho con mới sinh phải làm sao?”

## Diễn giải đúng phạm vi

Phép mining này chứng minh input thực tế trong lúc nhóm tự dùng thử thường không “sạch” và cần routing, trích xuất field, hỏi lại hoặc safety gate. Nó không thay thế khảo sát người ngoài nhóm; bằng chứng A chịu trách nhiệm chứng minh nhu cầu người dùng, còn bằng chứng B này chứng minh độ khó vận hành quan sát được trong log.

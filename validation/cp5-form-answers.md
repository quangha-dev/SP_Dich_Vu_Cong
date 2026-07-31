# Nội dung điền form CP5

## Thông tin nhóm

- Khóa VinAI: **Khóa 4**
- Lớp labcode: **D305**
- Nhóm trưởng: **Nguyễn Quang Hà — 2A202601424**

## Bao nhiêu người ngoài nhóm đã thử prototype?

**5**

## Họ nói gì?

**Lê Thị Hương Ly — Quản lý mua sắm và thủ tục tại CMC ATI: “Khi tôi hỏi đăng ký khai sinh, hệ thống hiển thị kế hoạch và tên các tool nên khá khó hiểu. Tôi muốn hệ thống hỏi trước xem tôi muốn tự điền biểu mẫu hay trả lời từng bước.” Vũ Minh Trí — người sử dụng dịch vụ công: “Tôi muốn biểu mẫu xuất hiện ngay trong khung chat. Sau khi điền xong cần cho tôi xem lại PDF và xác nhận lần cuối trước khi gửi.” Nguyễn Tiền Công — Sales và đăng ký giấy tờ xe tại VinFast Nam Từ Liêm: “Khi cuộc trò chuyện kéo dài nhiều bước, hệ thống đôi lúc hiểu nhầm câu hỏi mới theo nội dung cũ. Khi đổi thủ tục, hệ thống cần nhận biết và bỏ ngữ cảnh cũ.” Lê Thị Thảo Nguyên — giáo viên: “Câu trả lời còn hiển thị các ký tự Markdown như dấu sao nên khó đọc. Danh sách, tiêu đề và phần nhấn mạnh cần được hiển thị rõ ràng hơn.” Khuất Thuỳ Linh — Tester tại CMC Global: “Nếu đang hỏi bình thường rồi người dùng yêu cầu bỏ qua quy định, tự cấp quyền hoặc nộp hồ sơ không cần xác nhận thì hệ thống phải chặn ngay, không được tiếp tục gọi tool.”**

## Nhóm đã sửa gì từ phản hồi đó?

**Nhóm đã ẩn plan và tên tool nội bộ; thêm lựa chọn điền form hoặc trả lời từng bước; hiển thị form trong chat; bắt buộc validation, xem PDF và xác nhận trước khi nộp mô phỏng. Hệ thống được bổ sung quản lý context nhiều lượt, xóa state cũ khi đổi thủ tục và từ chối khi thiếu căn cứ. Giao diện render Markdown an toàn. Lớp phòng thủ mới chặn prompt injection/leo thang quyền trước RAG, model và tool, đồng thời dùng allowlist, DLP, approval gắn hash và loop/duplicate guard.**

## Kết quả đo lần cuối

**25/25**

## Nếu chưa đạt chuẩn thì vì sao?

**Nhóm đã đạt chuẩn: 25/25 case (100%), cao hơn quality bar 75% tương đương 19/25; không có case bịa thông tin/nguồn hoặc thực hiện hành động vượt thẩm quyền. Nhóm giữ nguyên golden set và quality bar đã cam kết.**

## Đã chạy thử demo có bấm giờ chưa?

**Chưa chạy thử.** Chỉ đổi lựa chọn sau khi cả nhóm thực sự dry run có bấm giờ.

## Ai nói phần nào khi demo?

**Trương Ngọc Hải trình bày vấn đề, khảo sát và lý do chọn sản phẩm. Nguyễn Quang Hà giới thiệu quyết định của GPT-4.1-mini và thực hiện luồng demo hỏi đáp → chọn cách nhập → rà soát → PDF → nộp mô phỏng. Vũ Văn Huy trình bày bốn tình huống khó, golden set và phòng thủ Agent. Vũ Nhật Quang trình bày cải tiến giao diện từ feedback và kết quả 25/25 so với quality bar. Nguyễn Quang Hà kết luận phạm vi mô phỏng và hướng phát triển.**

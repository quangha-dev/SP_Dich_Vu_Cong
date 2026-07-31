# Bằng chứng khảo sát CP4 — trải nghiệm dịch vụ công

## Phạm vi và bảo mật

- Google Forms ghi nhận **45 phản hồi**.
- Form giới thiệu khảo sát là vô danh nhưng có trường “Họ và tên”. Vì vậy, trước khi commit bản xuất chi tiết, nhóm phải xóa tên, email và mọi dữ liệu nhận dạng; chỉ giữ mã `R001`–`R045`.
- Sáu ảnh trong thư mục này là biểu đồ tổng hợp do Google Forms tạo và không chứa thông tin nhận dạng.
- File `responses-deidentified.csv` chứa đủ 45 hàng sau khi đã loại tên và timestamp. Nhóm chịu trách nhiệm xác nhận 45 người trả lời đều là người ngoài nhóm khi tích bằng chứng A.

## Câu hỏi khảo sát

Tên khảo sát: **Khảo sát trải nghiệm và khó khăn khi sử dụng dịch vụ công trực tuyến**.

Các câu hỏi chính dùng để đo pain:

1. **Về việc Tìm kiếm & Thực hiện thủ tục Trực tuyến** — chọn các khó khăn đã gặp: khó tìm tên thủ tục; tìm kiếm không chính xác; quy trình/danh mục hồ sơ không rõ; thông tin giữa các trang không đồng nhất; giao diện/biểu mẫu khó dùng; lỗi kỹ thuật; thiếu chatbot hỗ trợ; hoặc ý kiến khác.
2. **Về việc Bất tiện di chuyển & Tương tác trực tiếp** — chọn các khó khăn đã gặp: đi lại nhiều lần do hồ sơ thiếu/sai; không được hướng dẫn đầy đủ; xếp hàng lâu; giờ tiếp nhận trùng giờ hành chính; thiếu thiết bị/Wi-Fi; hoặc ý kiến khác.
3. **Về Thái độ & Năng lực phục vụ của Cán bộ tiếp nhận/Xử lý** — chọn các khó khăn đã gặp: thiếu thân thiện; bổ sung hồ sơ nhiều lần; dùng thuật ngữ khó; giải thích không rõ; hồ sơ trễ không rõ lý do; thao tác/quy trình chậm.
4. **Đánh giá tổng quan điểm khó khăn nhất** — chọn một trong các nhóm: giao diện/hạ tầng; đi lại; quy trình/giấy tờ; thái độ cán bộ; thời gian chờ; hoặc ý kiến khác.
5. **Ý kiến đóng góp khác** — câu hỏi mở.

Các câu hỏi hồ sơ mẫu gồm họ tên, độ tuổi và lĩnh vực chuyên môn. Không commit họ tên trong bản dữ liệu dùng chấm.

## Kết quả đếm được từ biểu đồ

Mẫu số của mỗi tỷ lệ là 45 phản hồi. Với câu nhiều lựa chọn, mỗi thanh được đếm độc lập nên không cộng các tỷ lệ với nhau.

| Câu hỏi/Phương án | Số người | Tỷ lệ |
|---|---:|---:|
| Phải đi lại nhiều lần do hồ sơ thiếu/sai sót | **26/45** | **57,8%** |
| Phải xếp hàng lâu do quá tải | 26/45 | 57,8% |
| Đi lại nhiều lần là khó khăn tổng quan lớn nhất | **25/45** | **55,6%** |
| Quy trình, giấy tờ rườm rà/chồng chéo là khó khăn tổng quan lớn nhất | **25/45** | **55,6%** |
| Khó tìm kiếm tên thủ tục phức tạp | **24/45** | **53,3%** |
| Quy trình/danh mục hồ sơ chưa rõ | 17/45 | 37,8% |
| Thiếu chatbot tư vấn trực tuyến | 17/45 | 37,8% |
| Thông tin giữa các trang không đồng nhất | 16/45 | 35,6% |
| Lỗi kỹ thuật/kết nối | 15/45 | 33,3% |
| Giao diện khó dùng/biểu mẫu rườm rà | 13/45 | 28,9% |

## Cách kiểm chứng

1. Mở `responses-deidentified.csv` để kiểm tra đủ 45 hàng và từng lựa chọn nguyên văn.
2. Chạy `python validation/evidence/cp4-survey/analyze_survey.py <file-zip-goc> validation/evidence/cp4-survey` để tái tạo `aggregate-results.csv` và `analysis.json`.
3. Đối chiếu các số đếm với ảnh `03-online-pain-points.png`, `04-travel-pain-points.png` và `06-overall-pain.png`.
4. Kiểm tra tỷ lệ bằng công thức `số lựa chọn / 45 × 100`, làm tròn một chữ số thập phân. Không cộng các lựa chọn vì một người có thể chọn nhiều đáp án.

SHA-256 của ZIP nguồn: `633C4BF6DAD9A77856FD52799BC03EF16EF71D1ED54534FDDA17C77148220874`.

## Trích dẫn mở đã khử định danh

- “Cần rút ngắn quy trình, làm rõ cần sử dụng những hồ sơ, những thủ tục phải làm.”
- “Nếu là một người lớn tuổi thì họ phải mất bao lâu để biết cách sử dụng?”
- “Cần có AI agent hỗ trợ.”
- “Dịch vụ công khó khăn với tôi vì tôi không phải là người có kinh nghiệm về công nghệ.”
- “Bổ sung chức năng lưu tạm hồ sơ để người dùng có thể hoàn thành sau.”
- “Thông báo lỗi cần rõ ràng, dễ hiểu để người dùng biết cách xử lý.”

## Artifact phân tích

- `responses-deidentified.csv`: đủ 45 phản hồi, không có họ tên hoặc timestamp.
- `aggregate-results.csv`: số đếm và tỷ lệ theo từng lựa chọn.
- `analysis.json`: kết quả máy đọc được, cột đã loại và hash nguồn.
- `validation/artifacts/cp4-survey-analysis/survey-analysis.xlsx`: workbook kiểm tra nhanh gồm dashboard, bảng tổng hợp và 45 phản hồi.

Không dùng phần “Response Summary” do Gemini tạo làm dữ liệu gốc. Phần phân tích này vẫn thuộc **chuẩn A — khảo sát người thật**; không tự động trở thành chuẩn B vì không phải chatlog/log độc lập.

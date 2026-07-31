# Nội dung điền form CP4 — Rà soát Specification

## Thông tin nhóm

- Khóa VinAI: **Khóa 4**
- Lớp labcode: **D305**
- Nhóm trưởng: **Nguyễn Quang Hà — 2A202601424**

## Loại bằng chứng

**Chọn cả A — Đã khảo sát người thật và B — Đã phân tích dữ liệu.** A dùng 45 phản hồi khảo sát ngoài nhóm; B dùng 10 tin nhắn trong log nhóm tự dùng thử, có bộ lọc, quy tắc đếm, hash nguồn và ví dụ nguyên văn đã khử định danh.

> Artifact A nằm trong `validation/evidence/cp4-survey/`; artifact B nằm trong `validation/evidence/cp4-log-mining/`. Cả hai đều có dữ liệu đã khử định danh, script tái lập, hash nguồn và cách đếm.

## Con số bằng chứng mạnh nhất

**Bằng chứng A: 26/45 người được khảo sát (57,8%) chọn “Phải đi lại nhiều lần do hồ sơ thiếu/sai sót” trong câu hỏi “Về việc Bất tiện di chuyển & Tương tác trực tiếp”; cách đếm là đếm các dòng có lựa chọn này rồi chia cho 45. Bằng chứng B: lọc `eval/cases.json` theo `source=group_self_test_deidentified_2026-07-30` và `real_observation=true`, có 8/10 tin nhắn (80%) dùng cách viết đời thường, viết tắt/lỗi gõ hoặc đưa nhiều dữ kiện trong một lượt. Quy tắc đếm, hash nguồn và 8 ví dụ nguyên văn đã khử định danh được lưu trong `validation/evidence/cp4-log-mining/`.**

## Các ý tưởng đã cân nhắc và lý do chọn

**Nhóm cân nhắc: (1) chỉ tìm đúng thủ tục; (2) chỉ giải thích quy trình/giấy tờ; (3) chỉ cải thiện khâu phục vụ trực tiếp; (4) trợ lý trọn luồng hỏi đáp → điền/rà soát form → PDF → nộp mô phỏng. Nhóm chọn (4) vì 24/45 người khó tìm thủ tục, 17/45 thấy danh mục hồ sơ chưa rõ và 26/45 phải đi lại do hồ sơ thiếu/sai. Phương án (3) bị loại vì prototype không kiểm soát hành vi cán bộ; hai phương án đầu không giải quyết trọn hành trình.**

## Bốn kiểu tình huống khó

**(1) Không có nguồn: hỏi cấp hộ chiếu tại sân bay hoặc visa Nhật — hệ thống phải nói chưa thể xác minh. (2) Mơ hồ: “làm giấy tờ cho con”, “đăng ký đất đai” — phải hỏi loại thủ tục hoặc địa bàn, không đoán. (3) Vượt thẩm quyền: yêu cầu điền khống, ký/nộp thật, tự cấp quyền hoặc bỏ xác nhận — phải chặn trước model/tool. (4) Hậu quả cao: trả sai phí, thời hạn, cơ quan xử lý; chọn nhầm form hoặc giữ ngữ cảnh cũ — phải có citation đúng, xóa state cũ khi đổi chủ đề và không suy diễn field.**

## Nguyên tắc thiết kế và vị trí áp dụng

**G1—Phạm vi rõ: tên, hộp xác nhận và biên nhận đều ghi “nộp mô phỏng”, không gửi cơ quan nhà nước. G2/G11—Căn cứ: fact thủ tục phải có citation đúng mã; thiếu nguồn thì từ chối. G10—Hỏi lại: input mơ hồ chỉ hỏi một thông tin tối thiểu, không đoán. G9—Sửa/khôi phục: sửa field làm validation cũ hết hiệu lực; đổi chủ đề xóa state cũ. PAIR Feedback & Control: người dùng chọn cách nhập, xem PDF và xác nhận trước side effect. Least privilege: tool theo allowlist, approval gắn hash; prompt injection và yêu cầu leo thang quyền bị chặn trước RAG/LLM/tool.**

## Nhóm còn thiếu gì, cần hỗ trợ gì

**Nhóm cần TA xác nhận cách khử định danh khảo sát hiện tại đáp ứng chuẩn A và BTC/TA cung cấp mã Zone của SPDVC vì repo không có bảng phân zone. Về kỹ thuật, nhóm muốn được review ngưỡng abstain/retrieval để hệ thống không chọn thủ tục gần giống khi nguồn hiện có không đủ căn cứ.**

## Trạng thái checklist CP4

| Hạng mục | Trạng thái |
|---|---|
| Evidence chuẩn A/B có log | **Đạt A+B về artifact** — A có 45 phản hồi khảo sát; B có 10 tin nhắn log tự dùng thử, phép đếm tái lập, hash nguồn và 8 ví dụ |
| Bảng impact + ứng viên bị loại | **Đạt về cấu trúc** — 3 ứng viên, có phương án loại và lý do |
| 4 lớp tình huống cụ thể | **Đạt** — mỗi lớp có ít nhất 2 ví dụ |
| ≥4 nguyên tắc có nơi áp dụng | **Đạt** |
| Quality bar bằng số | **Đạt** — ≥75% = 19/25 và hard gate bằng 0 |

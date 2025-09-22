# ⚽ Premier League Safety check Bot – Snapshot Dashboard

## Giới thiệu

EPL Bot là một dự án cá nhân nhằm mô phỏng và phân tích giải Ngoại hạng Anh (Premier League).  
Project bao gồm:

- **Core simulation**: chạy nhiều mô phỏng Monte Carlo để ước tính xác suất Top 4 và trụ hạng.
- **Data sync**: lấy kết quả/trận đấu từ các API bóng đá (football-data.org).
- **Snapshot publishing**: sinh file JSON chứa standings + xác suất, được lưu lại hoặc publish công khai (ví dụ: [Gist snapshot](https://gist.githubusercontent.com/minhkhang1008/19b310fe9bd41eddf209faf336785c98/raw/snapshot.json))
- **WebUI**: hiển thị bảng standings và xác suất từ snapshot công khai.

## Cách hoạt động

1. Máy cá nhân hoặc backend chạy mô phỏng bằng CLI (`eplbot`).
2. Kết quả (snapshot) được publish → JSON (ví dụ trên GitHub Gist).
3. Frontend fetch snapshot JSON đó và render thành bảng trực quan.

## Tính năng hiển thị

- Bảng xếp hạng EPL với điểm, thắng/hòa/thua, hiệu số.
- Xác suất Top 4 và trụ hạng.
- Fixtures còn lại.
- **Refresh Snapshot** để lấy dữ liệu mới nhất từ snapshot JSON.

---

## Setup

- Xem tại [README_setup.md](https://github.com/minhkhang1008/epl-safety-check/blob/main/README_setup.md)
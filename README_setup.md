# ⚽ EPL Top-4 & Relegation Safety Bot

Dự án mô phỏng & kiểm định toán học cho Ngoại hạng Anh (Premier League):

1) **Chứng minh “chính thức”** bằng ILP:  
   - **Officially Safe**: đội chắc chắn **không thể** rớt hạng ở bất kỳ cách hoàn tất mùa giải nào.  
   - **Officially Top-4**: đội chắc chắn **không thể** rơi khỏi top-4 ở bất kỳ cách hoàn tất mùa giải nào.  
   (Xử lý trường hợp bằng điểm **bảo thủ**, tức luôn bất lợi cho đội đang xét.)

2) **Xác suất “công bằng”** bằng Monte Carlo:  
   - Mỗi trận còn lại giả định **W/D/L = 1/3**

> Lưu ý luật: **3 đội cuối bảng xuống hạng**.

---

## 🧩 Kiến trúc tổng quan

```
Data provider (football-data.org) ──▶ eplbot (sync)
└─▶ eplbot (simulate → snapshot.json)
└─▶ Publish: GitHub Gist (RAW)
└─▶ WebUI (fetch RAW snapshot)
└─▶ Telegram Bot (đọc state/snapshot)

````

- **Sync**: kéo kết quả đã đá về state cục bộ.  
- **Simulate**: chạy mô phỏng để ước tính xác suất + dựng bảng hiện thời.  
- **Snapshot**: xuất JSON “đóng gói” bảng + xác suất + meta.  
- **Publish**: đẩy snapshot lên nơi công khai (khuyến nghị GitHub Gist RAW).  
- **WebUI**: chỉ là **frontend** fetch RAW snapshot và hiển thị.  

---

## 🚀 Cài đặt

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
````

---

## 🧰 CLI chính (state & tính toán)

**1) Khởi tạo 20 đội** (nếu không lấy từ provider)

```bash
python -m eplbot.cli init --file <team_names_file.txt>
# hoặc
python -m eplbot.cli init --teams "Team1,Team2,...,Team20"
```

**2) Ghi một kết quả trận đấu**

```bash
python -m eplbot.cli result --home "Arsenal" --away "Chelsea" --hg 2 --ag 1
```

**3) Hiển thị bảng + cờ Official + xác suất**

```bash
python -m eplbot.cli status --sims 20000
```

* Cột “Official”:

  * `CL✅` = **chính thức** top-4
  * `Safe✅` = **chính thức** trụ hạng
* “%Top4” & “%Safe”: ước lượng Monte Carlo (W/D/L=1/3, tie-break uniform).

> State mặc định lưu tại `league_state.json` (có thể đổi bằng `--state`).

---

## 🔄 Đồng bộ dữ liệu (football-data.org)

Thiết lập key:

```bash
export FOOTBALL_DATA_API_KEY="YOUR_API_KEY"
```
Xem thêm tại [README_INTEGRATIONS.md](https://github.com/minhkhang1008/epl-safety-check/blob/main/README_INTEGRATIONS.md)

Sync về state (tự nhận diện mùa hiện tại):

```bash
python -m eplbot.cli sync --provider football-data --season 2025
```
---

## 📦 Snapshot & Publish

Tạo snapshot cục bộ:

```bash
python -m eplbot.cli publish --with-sync --mode file --dest ./snapshot.json
```

Publish lên **GitHub Gist** (để WebUI đọc):

```bash
export GITHUB_TOKEN="ghp_xxx"   # PAT classic có scope: gist
# (tuỳ chọn) nếu có sẵn Gist: export GIST_ID="xxxxxxxxxxxxxxxxxxxx"
python -m eplbot.cli publish --with-sync --mode gist --out snapshot.json
```

* Nếu không đặt `GIST_ID`, lệnh sẽ tạo Gist mới và in ra ID.
* **URL RAW** bạn nhúng vào WebUI phải là dạng **không có SHA**:

  ```
  https://gist.githubusercontent.com/<user>/<gist_id>/raw/snapshot.json
  ```

---

## 🤖 Telegram Bot (dùng tạm)

Tạo bot bằng **@botfather**

Thiết lập:

```bash
export TELEGRAM_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
export EPL_STATE="league_state.json"
python -m eplbot.telegram_bot
```

Lệnh trong Telegram:

* `/start` – hướng dẫn
* `/init team1,team2,...,team20` – khởi tạo
* `/result Home;Away;HG;AG` – ghi kết quả nhanh
* `/status [sims]` – bảng + cờ Official + xác suất
* `/table` – chỉ bảng
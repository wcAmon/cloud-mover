# Cloud-Mover

Claude Code 搬家助手 API 服務。

## 快速指令

cd /home/cloud-mover
uv run cloud-mover          # 啟動服務
uv run pytest               # 執行測試

## API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/` | GET | API 文件（給 Claude Code 閱讀） |
| `/register` | POST | 註冊取得識別碼 |
| `/upload` | POST | 上傳備份檔案 |
| `/download` | POST | 下載備份檔案 |

## 技術棧

- FastAPI + SQLModel + SQLite
- 本地檔案儲存（./uploads/）
- 24 小時自動過期清理

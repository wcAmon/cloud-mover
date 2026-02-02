# Cloud-Mover

Claude Code 搬家助手 API 服務。

## 功能

- 註冊取得唯一識別碼
- 上傳備份檔案（最大 59MB）
- 下載備份檔案（使用 OTP 驗證）
- 24 小時自動過期清理

## 安裝

```bash
uv sync
```

## 啟動

```bash
uv run cloud-mover
```

## API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/` | GET | API 文件 |
| `/register` | POST | 註冊取得識別碼 |
| `/upload` | POST | 上傳備份檔案 |
| `/download` | POST | 下載備份檔案 |

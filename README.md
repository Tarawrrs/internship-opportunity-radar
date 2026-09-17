# 實習機會雷達

一個不依賴 GPT 排程的私人職缺工作台，依研究、資料、產品分析與職涯 option value 排序機會。

## 目前功能

- 顯示個人化 fit、資格、風險與原始職缺連結。
- 以瀏覽器本機保存「收藏／略過／已申請」狀態。
- GitHub Actions 每天檢查一次；距上次成功掃描滿五天才讀取官方招募來源。
- 可在 Actions 頁面手動執行 `Refresh internship radar`，強制立即更新。

## 來源

背景掃描目前讀取 Appier、ShopBack 與 Point72 的官方 ATS feeds；J-PAL、南山與部分 104 機會保留為人工查核來源。自動分數只做初篩，工作授權、學籍、實習長度與截止日仍需回到原始頁確認。

## 網站檔案

入口是 `dist/index.html`，背景掃描輸出位於 `dist/data/`。

GitHub Pages 網址會公開在網際網路上，即使 repository 本身是私人。請確認可公開後，再在 repository 的 **Settings → Pages** 將 Source 設為 **GitHub Actions**，或手動執行 `Publish GitHub Pages` workflow。

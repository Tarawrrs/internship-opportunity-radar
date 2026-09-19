# 實習機會雷達

一個不依賴 GPT 排程的私人職缺工作台，依研究、資料、產品分析與職涯 option value 排序機會。

網站：[tarawrrs.github.io/internship-opportunity-radar](https://tarawrrs.github.io/internship-opportunity-radar/)

## 目前功能

- 顯示個人化 fit、資格、風險與原始職缺連結。
- 地點先作硬性篩選：台北實體／混合辦公，或職缺明示台灣／全球可申請的全遠端。
- 新北、僅標示台灣、海外實體／混合辦公不納入；US-only 等遠端地區限制與必須海外到場／出差要求優先排除。
- 明示遠端但台灣資格不明（例如只有 Remote 或 APAC）的項目另放「遠端資格待確認」，不列入主清單。
- 全球遠端仍須人工確認時區、聘僱或承攬資格、學籍與工時；分數不能覆蓋地點限制。
- 以瀏覽器本機保存「收藏／略過／已申請」狀態。
- GitHub Actions 每天檢查一次；距上次成功掃描滿五天才讀取官方招募來源。
- 成功掃描後消失或到期的機會會移入永久 Archive；來源暫時故障時保留舊資料。
- 2026-09-19 因地點偏好調整而移出的機會會保留於 Archive，明確標示不是下架判定。
- 可在 Actions 頁面手動執行 `Refresh internship radar`，強制立即更新。
- 網站的「讀取最新資料」只下載已發布結果，使用與背景掃描相同的篩選結果；不再執行另一套瀏覽器職缺搜尋。

## 來源

背景掃描目前讀取 Appier、Point72、WorldQuant、Agoda、Anthropic、Mercari、ShopBack 與 Ninja Van 的官方 ATS feeds；J-PAL、南山與部分 104 機會保留為人工查核來源。自動分數只做初篩，工作授權、學籍、實習長度與截止日仍需回到原始頁確認。

人工追蹤項目同樣受地點門檻約束；掃描不會把人工查核日期改成今天。規則採保守文字辨識，可能漏掉條件不明或不同措辭的機會，不是 AI 判讀。未找到合格遠端時允許清單為空。

## 驗證

執行 `python3 -m unittest discover -s scripts -p 'test_*.py' -v`，覆蓋地點歧義、遠端地區限制、出差要求、歷史保存與來源故障時的舊資料處理。

## 網站檔案

入口是 `dist/index.html`，目前機會、掃描狀態與 Archive 位於 `dist/data/`。GitHub Pages 與這個專用 repository 都公開可存取；個人 migration 文件不在此 repository 中。

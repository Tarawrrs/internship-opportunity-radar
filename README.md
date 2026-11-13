# 學術與職涯資訊中心

[網站](https://tarawrrs.github.io/internship-opportunity-radar/)彙整台大及中研院的學術活動、近期研究，以及台北和台灣可全遠端的實習與研究職缺。

## 職涯

- 預設顯示寒假機會。依公告的實習時間區分寒假限定、寒假開始且延續到學期、起聘或結束日待確認。2027 年採[台大行事曆](https://mpea.econ.ntu.edu.tw/node/53)的 12/28 至 2/19。未設定校曆的年度以 1–2 月估計。
- 商業型包括企業、銀行、證券與顧問實習。研究型包括研究實習及助理。可依截止、首次發現或技能契合度排序。
- 招募來源包括台灣就業通、台大與其他大學職涯中心、學研單位、渣打、星展、資誠、Mastercard、Appier、LINE 等雇主，以及 Himalayas 的遠端線索。來源一覽與實際讀取結果見網站。
- 混合縣市、地區待核對的遠端、未確認仍收件的校園轉知放在「待查核」。到期或下架後移入 Archive，暫時讀取失敗的公告先轉待查核。收藏、已申請與略過留在瀏覽器。
- 群益寒假簡章為逐欄核對的獨立來源。掃描比對檔案內容，公告期限到期後即停用。部分校園轉知的職務地點另以雇主職缺核對，個別招募仍以原公告為準。
- 人工查核的歷峯寒假職缺放在待查核清單，並在查核七天後移入 Archive。

## 學術

- 掃描台大經濟系、語言所、CRETA，以及中研院經濟所、語言所、資訊所的語言學相關活動與院方近期公告。
- 從 RePEc NEP 的編輯選刊、Crossref 的期刊資料和 Glossa 的 RSS 取得研究。主題包括個體、應用個體、實驗與行為、賽局、數理經濟及語言學。工作論文顯示選刊日，期刊紀錄顯示出版日或出版月。

## 更新與驗證

GitHub Cron 每天在台北時間 08:23 排入 `Refresh internship radar`。另有 `Daily radar timer` 使用 Actions 環境的等待計時器，每 24 小時排下一輪並發送 `radar-daily-timer` 事件。當天已有完整的自動掃描時，工作流程會跳過重複查詢。

每輪搜尋會重新讀取公開來源。掃描完成後，工作流程發送 `radar-data-refreshed` 事件，讓 Pages 發布最新資料。程式使用 Python 和公開資料來源。網站「來源與掃描紀錄」顯示 GitHub Cron、雲端計時器或手動觸發，以及讀取筆數、首次找到與來源錯誤。「讀取已發布的資料」會重新下載 Pages 上的結果。

雲端計時器需要 `radar-timer-daily` 環境的 1,440 分鐘等待規則。GitHub Cron 在台北時間 09:53 檢查是否有下一輪等候中。需要重啟時，可在 Actions 的 `Daily radar timer` 選 `daily` 等待 24 小時，或選 `start` 使用 `radar-timer-start` 環境的 3 分鐘等待規則，重新查詢來源並發布。

```sh
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/refresh_jobs.py
python3 scripts/refresh_academic.py
python3 -m http.server --directory dist
```

GitHub Pages 入口為 `dist/index.html`，掃描輸出位於 `dist/data/`。

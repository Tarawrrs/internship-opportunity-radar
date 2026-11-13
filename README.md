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

GitHub Actions 每天在台北時間 21:57 排程執行 `Refresh internship radar`，22:47 備援會檢查當天是否已有成功的排程掃描。實際開始時間由 GitHub 決定。每輪搜尋會重新讀取公開來源，再由 Pages 發布資料。程式不需要 AI 或 API 金鑰。網站「來源與掃描紀錄」可查看觸發方式、讀取筆數、首次找到與來源錯誤。「讀取已發布的資料」會重新下載 Pages 上的結果。

```sh
python3 -m unittest discover -s scripts -p 'test_*.py' -v
python3 scripts/refresh_jobs.py
python3 scripts/refresh_academic.py
python3 -m http.server --directory dist
```

GitHub Pages 入口為 `dist/index.html`，掃描輸出位於 `dist/data/`。

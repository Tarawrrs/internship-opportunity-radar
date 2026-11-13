# 實習機會雷達

每天從公開招募清單發現新的台北實習、研究助理、predoc 與可從台灣工作的全遠端機會，依研究、資料與產品分析契合度排序。

網站：[tarawrrs.github.io/internship-opportunity-radar](https://tarawrrs.github.io/internship-opportunity-radar/)

## 目前功能

- 顯示刊登日（或來源更新日）、最近查到的日期、截止日、職缺類型與原公告連結。
- 地點先作硬性篩選：台北實體／混合辦公，或職缺明示台灣／全球可申請的全遠端。
- 新北、僅標示台灣、海外實體／混合辦公不納入；US-only 等遠端地區限制與必須海外到場／出差要求優先排除。
- 明示遠端但台灣資格不明、遠端平台的線索、無法確認仍收件的公告，另放「待查核」。如與雇主的刊登衝突，以雇主為準。
- 全球遠端仍須人工確認時區、聘僱或承攬資格、學籍與工時；分數不能覆蓋地點限制。
- 以瀏覽器本機保存「收藏／略過／已申請」狀態。
- GitHub Actions 每天排程搜尋一次（台北時間 08:23 排入，實際開始時間由 GitHub 決定）。網站顯示搜尋筆數、各來源狀態、本輪首次找到及近七天新發現。首次找到的意思是雷達第一次發現，不是來源刊登日期。
- 到期或不再出現在有效招募清單的職缺進 Archive。來源故障或近期公告已滑出訂閱範圍時，最近看過的舊資料先移至待查核、保留最後看見日，過後封存；不把讀取失敗判定為下架。
- 舊有人工追蹤及招募計畫總覽已移入 Archive，不再自動出現在目前職缺。
- 可以在 Actions 手動執行 `Refresh internship radar` 立即重新搜尋；網站的「讀取最新資料」只下載已發布結果。

## 來源

- 跨雇主職缺：[勞動部勞動力發展署台灣就業通](https://data.gov.tw/dataset/44062)，依台北 12 區掃描刊登中資料，使用政府資料開放授權條款第 1 版。只計入符合職務與地點的公告。
- 學研求才：[中央研究院人才招募](https://www.sinica.edu.tw/recruitment/53?Datas_Query.workType=3)、[台大經濟系實習與就業公告](https://econ.ntu.edu.tw/實習與就業公告)、[國科會求才 RSS](https://www.nstc.gov.tw/folksonomy/rss)；訂閱型來源無明確截止日的公告只看最近 35 天。
- 企業招募：[LINE Careers](https://careers.linecorp.com/jobs)、[Dcard](https://about.dcard.tw/en/joblist)、Portcast，以及原有的 Appier、Point72、WorldQuant、Agoda、Anthropic、Mercari、ShopBack、Ninja Van。
- 國際遠端線索：[Himalayas](https://himalayas.app/)（資料來源）；用台灣及 UTC+8 招募條件，搜尋實習與研究助理。平台線索不列為雇主已查核的職缺。

程式依每個來源最新提供的資料與明示工作地點篩選，不是全網搜尋，也不呼叫 AI。公開頁只保存必要的職缺資訊、技能摘要與原始公告連結。分數是初篩；即使來源仍列出，投遞前也請確認是否已提前額滿及完整資格。

## 驗證

執行 `python3 -m unittest discover -s scripts -p 'test_*.py' -v`，驗證新公告發現、地點門檻、跨來源衝突、到期及來源故障。執行 `python3 scripts/refresh_jobs.py` 查詢現行公開來源並更新資料。

## 網站檔案

入口是 `dist/index.html`，目前機會、掃描狀態與 Archive 位於 `dist/data/`。GitHub Pages 與這個專用 repository 都公開可存取；個人 migration 文件不在此 repository 中。

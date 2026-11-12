#!/usr/bin/env python3
"""用真的 ccs TUI 程式碼 + 假資料，產生 demo 影片每個畫面的內容與時間軸。

輸出 timeline.js（window.TIMELINE），給 index.html 播放。
畫面不是手刻的：TUI 部分是把 ccs 的 TUI 接到虛擬螢幕上實際按鍵畫出來的，
所以排版、顏色、markdown 渲染都和真的一樣；資料全部是虛構的。
"""
import json
import os
import random
import uuid
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ["HOME"] = "/Users/demo"          # 畫面上的路徑不要出現真的使用者名稱

import curses  # noqa: E402  只用常數（KEY_UP、A_REVERSE），不會初始化終端機

ns = {"__name__": "ccs_demo"}
exec(compile((HERE.parent / "ccs").read_text(), "ccs", "exec"), ns)
TUI, char_width, title_of, project_label = ns["TUI"], ns["char_width"], ns["title_of"], ns["project_label"]

COLS, ROWS = 130, 32
STYLES = ["dim", "title", "reply", "proj", "missing", "branch", "prompt", "h", "bold", "th",
          "code", "link", "quote", "mark", "sh_path", "sh_glyph", "ok"]
BIT = {name: 1 << i for i, name in enumerate(STYLES)}
REVERSE = curses.A_REVERSE


# ---------- 虛擬螢幕 ----------

class FakeScreen:
    def __init__(self, h, w):
        self.h, self.w = h, w
        self.cur = (0, 0)
        self.erase()

    def getmaxyx(self):
        return self.h, self.w

    def erase(self):
        self.cells = [[(" ", 0, 1) for _ in range(self.w)] for _ in range(self.h)]

    clear = erase

    def _set(self, y, x, cell):
        row = self.cells[y]
        if row[x][2] == 0 and x > 0:              # 蓋到寬字元的右半邊
            row[x - 1] = (" ", row[x - 1][1], 1)
        if row[x][2] == 2 and x + 1 < self.w:      # 蓋到寬字元的左半邊
            row[x + 1] = (" ", row[x + 1][1], 1)
        row[x] = cell

    def addstr(self, y, x, s, attr=0):
        for ch in s:
            cw = char_width(ch)
            if cw == 0:
                continue
            if x + cw > self.w:
                raise curses.error()
            self._set(y, x, (ch, attr, cw))
            if cw == 2:
                self._set(y, x + 1, ("", attr, 0))
            x += cw

    def move(self, y, x):
        self.cur = (y, x)

    def refresh(self):
        pass

    def keypad(self, flag):
        pass

    def timeout(self, ms):
        pass

    def snapshot(self):
        """每一列轉成 runs：[attr, 文字, 寬度遮罩]。"""
        rows = []
        for row in self.cells:
            runs = []
            for ch, attr, cw in row:
                if cw == 0:
                    continue
                if runs and runs[-1][0] == attr:
                    runs[-1][1] += ch
                    runs[-1][2] += str(cw)
                else:
                    runs.append([attr, ch, str(cw)])
            rows.append(runs)
        return rows


class DemoTUI(TUI):
    def init_screen(self):
        self.attrs = dict(BIT)
        self.esc_map = {}


# ---------- 假資料 ----------

random.seed(7)
P = "/Users/demo/Projects/"


def fake_id():
    return str(uuid.UUID(int=random.getrandbits(128), version=4))


SESSIONS, PREVIEWS = [], {}


def add(proj, title, branch, when, turns, exists=True, sid=None):
    dt = datetime.strptime("2026-" + when, "%Y-%m-%d %H:%M")
    cwd = P + proj
    s = {"id": sid or fake_id(), "path": "/demo/%d.jsonl" % len(SESSIONS), "cwd": cwd,
         "branch": branch, "title": title, "ai_title": None, "summary": None,
         "first_prompt": turns[0][0], "last_prompt": turns[-1][0], "n_prompts": len(turns),
         "last": dt.timestamp(), "exists": exists}
    s["_hay"] = " ".join([title_of(s), project_label(cwd), cwd, branch or "",
                          s["last_prompt"], s["first_prompt"]]).lower()
    SESSIONS.append(s)
    PREVIEWS[s["path"]] = {"when": dt.strftime("%m-%d %H:%M"), "cwd": cwd, "exists": exists,
                           "name": title, "turns": [list(t) for t in turns]}


add("my-app", "登入頁改版", "main", "11-13 14:20", [
    ("登入頁要改成新的設計稿，先幫我看一下現在的元件結構",
     "現在登入頁由三個元件組成：\n- `LoginPage`：版面與路由\n- `LoginForm`：帳號密碼欄位與驗證\n"
     "- `SocialButtons`：Google、GitHub 登入\n樣式都寫在 `login.module.css`，沒有用到設計系統的元件。"),
    ("好，照設計稿改，按鈕換成設計系統的 Button",
     "改好了，`LoginForm` 改用 `<Button variant=\"primary\">`，間距和字級照設計稿調整。\n"
     "| 檔案 | 變更 |\n|---|---|\n| `LoginForm.tsx` | 換成設計系統元件 |\n"
     "| `login.module.css` | 刪掉 120 行自訂樣式 |\n| `LoginPage.test.tsx` | 更新快照 |"),
    ("登入按鈕在手機上會被鍵盤擋住，幫我修",
     "改好了，原因是表單高度用了 `100vh`：\n- 改用 `dvh`，鍵盤彈出時高度會跟著變\n- 補上 iOS Safari 的測試"),
    ("順便把錯誤訊息改成中文",
     "已經改成中文，訊息集中在 `i18n/zh-TW.json`，之後要加英文只要新增語系檔。"),
    ("commit 然後開 PR", "已開 **PR #128「登入頁改版」**，CI 全部通過。"),
])
add("infra", "K8s 記憶體上限調整", "main", "11-13 11:05", [
    ("api 的 pod 一直被 OOMKilled，幫我看一下",
     "查了最近 24 小時的事件，`api` 有 **17 次 OOMKilled**，都發生在每天 09:00 報表排程跑的時候。"),
    ("報表排程跑的時候用了多少記憶體?",
     "尖峰大約 **1.4 GiB**，但上限只設 1 GiB。主要是報表一次把整個月的訂單載進記憶體。"),
    ("其他服務的狀況呢?",
     "## 各服務記憶體\n| 服務 | 目前上限 | 尖峰用量 | 建議上限 |\n|---|---|---|---|\n"
     "| api | 1 GiB | 1.4 GiB | 2 GiB |\n| worker | 512 MiB | 380 MiB | 不用改 |\n"
     "| web | 256 MiB | 140 MiB | 可降到 192 MiB |"),
    ("為什麼報表要把整個月的訂單載進來?",
     "`ReportService.monthly()` 用 `findAll()` 撈出整個月的訂單，再在記憶體裡分組加總：\n"
     "- 11 月有 **38 萬筆**訂單\n- 每筆物件大約 3.5 KiB\n改成在資料庫端用 `GROUP BY` 加總，就不用把明細載進來。"),
    ("先不改程式，api 先調到 2 GiB",
     "改好了，`deploy/api.yaml` 的 limits 調成 `2Gi`，requests 調成 `1Gi`，已套用到 staging。"),
    ("HPA 會受影響嗎?",
     "會。HPA 是看「用量 ÷ requests」，requests 從 512 MiB 改成 1 GiB 後，同樣的用量算出來的比例會變一半。\n"
     "我把擴展門檻從 **80% 調成 70%**，讓擴展時機跟原本差不多。"),
    ("staging 跑一次報表看看",
     "跑完了，尖峰 1.45 GiB，沒有再被 OOMKilled。\n- 報表耗時 3 分 12 秒，跟之前差不多\n- 其他 pod 沒有受到影響"),
    ("好，production 也套用", "已經套用到 production，滾動更新完成，6 個 pod 都正常。"),
    ("幫我開 issue 追蹤報表的優化",
     "已開 **issue #342「月報改用資料庫端彙總」**：\n- 背景與這次的 OOM 紀錄\n"
     "- 建議做法：`GROUP BY` 加上分批讀取\n- 預估記憶體可以降到 300 MiB 以內"),
    ("再加個告警，記憶體超過 85% 就通知我",
     "加好了：Prometheus 規則 `PodMemoryHigh`，連續 5 分鐘超過 limits 的 85% 就發到 `#infra-alerts`。\n"
     "已經在 staging 觸發測試過，通知有收到。"),
])
add("api/.claude/worktrees/fix-auth", "登入 token 過期問題", "fix/auth-token", "11-13 09:41", [
    ("使用者反映登入一小時後就被登出，幫我查原因",
     "查到了：**access token 過期後，沒有用 refresh token 換新的**。\n"
     "`authMiddleware` 收到 401 就直接清掉 session，沒有走刷新流程。"),
    ("refresh token 的有效期限是多久?",
     "## 目前的設定\n| Token | 有效期限 | 存放位置 |\n|---|---|---|\n"
     "| access token | 1 小時 | 記憶體 |\n| refresh token | 30 天 | httpOnly cookie |\n"
     "refresh token 的期限沒問題，問題只在沒有使用它。"),
    ("好，幫我修，並補測試",
     "修好了：\n1. 收到 401 時先呼叫 `/auth/refresh` 換新 token，成功就重送原本的請求\n"
     "2. 同時有多個請求失敗時只刷新一次，其他請求排隊等待\n3. 刷新也失敗才登出\n新增 6 個測試，全部通過。"),
    ("部署到 staging 了嗎?",
     "已部署到 staging。我用測試帳號把 access token 期限調成 1 分鐘驗證過，過期後會自動刷新，不會被登出。"),
], sid="7c41d0e2-5b9a-4f1e-8d2c-0a6e3b7f91c4")
add("design-system", "按鈕元件 dark mode", "feat/dark-mode", "11-12 18:30", [
    ("Button 在深色模式下對比太低，幫我調",
     "調整了 `--btn-primary-bg` 和文字色，對比從 3.1 提高到 **4.8**，符合 WCAG AA。"),
    ("其他元件也檢查一下", "檢查了 24 個元件，另外 3 個也不合格：`Tag`、`Tooltip`、`Badge`，都一起修好了。"),
])
add("data-pipeline", "每日報表 ETL 重構", "main", "11-12 16:02", [
    ("每日報表的 ETL 越跑越久，幫我看瓶頸在哪",
     "瓶頸在 `transform_orders`，逐筆呼叫匯率 API，一次跑要 **42 分鐘**。"),
    ("改成批次處理", "改成先把當天匯率一次抓下來再做 join，現在只要 **3 分鐘**。"),
])
add("mobile", "推播通知排程", "release/2.3", "11-12 10:15", [
    ("推播要能排程在指定時間送出", "加了 `scheduledAt` 欄位，後台排程頁也做好了，到時間由 worker 送出。"),
])
add("blog", "部落格 RSS 產生器", "main", "11-11 21:40", [
    ("幫我的部落格加 RSS", "已經產生 `/rss.xml`，包含最新 20 篇文章，build 時自動更新。"),
])
add("api", "API 回應時間優化", "main", "11-11 15:22", [
    ("訂單列表 API 很慢", "原因是 N+1 查詢，改用 `include` 一次撈關聯資料後，p95 從 1.8 秒降到 **220 毫秒**。"),
])
FILLERS = [
    ("infra", "CI 快取加速", "ci/cache"), ("docs", "README 英文版", "main"),
    ("my-app", "圖片延遲載入", "main"), ("api", "Sentry 錯誤分組", "main"),
    ("landing-page", "首頁 Lighthouse 分數", "main"), ("api", "訂單匯出 CSV", "feat/export"),
    ("api", "GraphQL schema 整理", "main"), ("design-system", "Storybook 升級 8.0", "chore/sb8"),
    ("mobile", "推播點擊追蹤", "main"), ("data-pipeline", "資料庫索引檢查", "main"),
    ("scripts", "cron job 改用佇列", "main"), ("api", "支付 webhook 重試", "fix/webhook"),
    ("my-app", "多語系日期格式", "main"), ("my-app", "e2e 測試不穩定", "main"),
    ("infra", "Terraform state 搬家", "main"), ("scripts", "ESLint 規則統一", "main"),
    ("mobile", "深色模式截圖測試", "main"), ("infra", "S3 生命週期規則", "main"),
    ("scripts", "部署腳本加 rollback", "main"), ("my-app", "使用者頭像裁切", "feat/avatar"),
    ("docs", "API 文件自動產生", "main"), ("api", "Redis 連線池設定", "main"),
    ("my-app", "表單驗證錯誤訊息", "main"), ("landing-page", "首頁輪播換成靜態圖", "main"),
]
for i, (proj, title, branch) in enumerate(FILLERS):      # 比上面幾筆舊，排在後面
    when = "11-%02d %02d:%02d" % (10 - i // 3, 21 - (i % 3) * 4, (i * 17) % 60)
    add(proj, title, branch, when, [(title + "，幫我處理", "處理好了，細節寫在 PR 說明裡。")])
add("old-web", "舊版登入流程整理", "master", "10-28 17:05", [
    ("整理一下舊版登入流程，之後要下線", "整理成 `docs/legacy-login.md`，列出 4 個還在呼叫舊 API 的地方。"),
], exists=False)
SESSIONS.sort(key=lambda s: s["last"], reverse=True)


# ---------- 劇本 ----------

STATES, EVENTS, CAMERA = [], [], []


def snap(scr, cursor=True):
    state = {"rows": scr.snapshot(), "cursor": list(scr.cur) if cursor else None}
    if not STATES or STATES[-1] != state:
        STATES.append(state)
    return len(STATES) - 1


def event(t, state, key=None):
    EVENTS.append({"t": t, "state": state, "key": key})


def camera(t0, t1, col=None, row=None, scale=1.0):
    CAMERA.append({"t0": t0, "t1": t1, "col": col, "row": row, "scale": scale})


# shell 畫面
sh = FakeScreen(ROWS, COLS)
PROMPT = [("~/Projects/my-app", "sh_path"), (" ❯ ", "sh_glyph")]


def shell_line(y, extra=""):
    x = 0
    for text, style in PROMPT:
        sh.addstr(y, x, text, BIT[style])
        x += sum(char_width(c) for c in text)
    sh.addstr(y, x, extra)
    sh.move(y, x + sum(char_width(c) for c in extra))


shell_line(0)
camera(0, 0, col=12, row=0, scale=2.0)
event(0.0, snap(sh))
for t, typed in ((0.7, "c"), (0.85, "cc"), (1.0, "ccs")):
    shell_line(0, typed)
    event(t, snap(sh), typed)

# 進入 TUI
scr = FakeScreen(ROWS, COLS)
tui = DemoTUI(scr, SESSIONS, "")
tui.previews = PREVIEWS


def tui_state():
    tui.draw()
    return snap(scr)


event(1.5, tui_state(), "⏎ Enter")
camera(1.6, 2.6, scale=1.0)
camera(3.2, 4.0, col=30, row=10, scale=1.5)
for t, key, label in ((4.3, curses.KEY_DOWN, "↓"), (4.9, curses.KEY_DOWN, "↓"), (5.5, curses.KEY_DOWN, "↓"),
                      (6.2, curses.KEY_UP, "↑"), (6.8, curses.KEY_UP, "↑")):
    tui.handle(key)
    event(t, tui_state(), label)
camera(7.3, 8.2, col=96, row=15, scale=1.45)
for t, key, label in ((10.0, "p_up", "Shift ↑"), (10.6, "p_up", "Shift ↑"), (11.2, "p_up", "Shift ↑"),
                      (12.0, "p_pgup", "PgUp")):
    tui.handle(key)
    event(t, tui_state(), label)
camera(13.9, 14.7, scale=1.0)
camera(14.9, 15.7, col=24, row=4, scale=1.7)
tui.handle("登")
event(16.0, tui_state(), "登")
tui.handle("入")
event(16.5, tui_state(), "登入")
tui.handle(curses.KEY_DOWN)
event(17.5, tui_state(), "↓")
camera(18.0, 18.9, col=96, row=14, scale=1.45)
camera(21.3, 22.1, scale=1.0)
picked, _ = tui.handle("\r")

# 離開 TUI，回到 shell：ccs 印出已複製的指令
cmd = ns["resume_cmd"](picked)
sh.erase()
shell_line(0, "ccs")
sh.addstr(1, 0, "✓ 已複製", BIT["ok"])
sh.addstr(1, 10, cmd)
shell_line(2)
event(22.4, snap(sh), "⏎ Enter")
camera(22.6, 23.4, col=62, row=2, scale=1.25)
shell_line(2, cmd)
event(24.7, snap(sh), "⌘ V")
camera(26.0, 26.9, scale=1.0)

TIMELINE = {
    "cols": COLS, "rows": ROWS, "styles": STYLES, "reverse": REVERSE,
    "states": STATES, "events": EVENTS, "camera": CAMERA,
    "endcard": 27.0, "duration": 30.0,
}
(HERE / "timeline.js").write_text("window.TIMELINE = " + json.dumps(TIMELINE, ensure_ascii=False) + ";\n")
print("states=%d events=%d sessions=%d → timeline.js (%d KB)"
      % (len(STATES), len(EVENTS), len(SESSIONS), (HERE / "timeline.js").stat().st_size // 1024))

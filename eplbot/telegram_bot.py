import os
import json, time, hashlib, os, requests
from typing import List
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes
from .state import load_state, save_state
from .league import League
from .ilp_check import guaranteed_top4, guaranteed_safe
from .sim import estimate_probabilities
from .providers import FootballDataProvider, ApiFootballProvider
from .sync import merge_finished_matches
from telegram.constants import ParseMode

STATE_PATH = os.environ.get("EPL_STATE", "league_state.json")
CACHE_PATH = os.environ.get("EPL_CACHE", "last_status_cache.json")
_last_status = {"text": None, "meta": None}
SNAPSHOT_FILE = os.environ.get("EPL_SNAPSHOT_FILE", "snapshot.json")
SNAPSHOT_URL  = os.environ.get("EPL_SNAPSHOT_URL")

async def usesnapshot_cmd(update, context):
    obj = _load_snapshot_local()
    if obj is None and SNAPSHOT_URL:
        obj = _refresh_snapshot_from_url()
    if obj is None:
        await update.message.reply_text("Chưa có snapshot. Hãy tải lên file snapshot.json hoặc set EPL_SNAPSHOT_URL.")
        return
    txt = _format_snapshot_table(obj)
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)
    
async def refreshsnapshot_cmd(update, context):
    if not SNAPSHOT_URL:
        await update.message.reply_text("Chưa set EPL_SNAPSHOT_URL.")
        return
    try:
        obj = _refresh_snapshot_from_url()
        txt = _format_snapshot_table(obj)
        await update.message.reply_text("Đã cập nhật snapshot từ URL.\n" + txt, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Refresh lỗi: {e}")

def _load_snapshot_local():
    if not os.path.exists(SNAPSHOT_FILE):
        return None
    try:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _refresh_snapshot_from_url():
    if not SNAPSHOT_URL:
        return None
    r = requests.get(SNAPSHOT_URL, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Fetch snapshot failed: {r.text[:200]}")
    obj = r.json()
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return obj

def _format_snapshot_table(obj) -> str:
    # tái dùng formatter bảng đẹp đã có (_format_table_text) nếu muốn
    # ở đây build nhanh từ snapshot rows
    rows = obj.get("table", [])
    meta = obj.get("meta", {})
    dt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(meta.get("generated_at", 0)))
    # bạn có thể dùng _format_table_text nếu muốn đồng nhất style:
    # nhưng vì _format_table_text cần League state, ta render đơn giản:
    def pct(x): return "-" if (x is None) else f"{100*x:>.1f}%"
    head = (
        "┌──┬────────────────────────────┬──┬──┬──┬──┬───┬───┬──┬────┬─────────┬──────┬──────┐\n"
        "│# │ Team                       │P │W │D │L │GF │GA │GD│Pts │Official │%Top4 │%Safe │\n"
        "├──┼────────────────────────────┼──┼──┼──┼──┼───┼───┼──┼────┼─────────┼──────┼──────┤\n"
    )
    lines = [head]
    for r in rows:
        off = []
        if r.get("official", {}).get("top4"): off.append("CL✅")
        if r.get("official", {}).get("safe"): off.append("S✅")
        off_str = " ".join(off) if off else "—"
        line = (
            f"│{r['rank']:>2}│ {r['team']:<28}│"
            f"{r['played']:>2}│{r['wins']:>2}│{r['draws']:>2}│{r['losses']:>2}│"
            f"{r['gf']:>3}│{r['ga']:>3}│{r['gd']:>2}│{r['points']:>4}│"
            f"{off_str:^9}│{pct(r.get('probTop4')):>6}│{pct(r.get('probSafe')):>6}│"
        )
        lines.append(line)
    lines.append("└──┴────────────────────────────┴──┴──┴──┴──┴───┴───┴──┴────┴─────────┴──────┴──────┘")
    meta_line = f"\nSnapshot: sims={meta.get('sims')} seed={meta.get('seed')} results={meta.get('results_count')} at {dt}"
    return "<pre>" + "\n".join(lines) + "</pre>" + f"\n{meta_line}"

def _state_fingerprint(st: dict) -> str:
    """Tạo fingerprint nhẹ của state để phát hiện thay đổi."""
    teams = st.get("teams", [])
    results = st.get("results", [])
    # chỉ cần những thứ quyết định bảng/xác suất: số đội, số trận, danh sách cặp, điểm
    h = hashlib.sha256()
    h.update(str(len(teams)).encode())
    h.update(str(len(results)).encode())
    for r in results:
        h.update(f'{r["home"]}|{r["away"]}|{r["hg"]}|{r["ag"]}'.encode())
    return h.hexdigest()

def _load_cache():
    if not os.path.exists(CACHE_PATH):
        return None
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            obj = json.load(f)
        _last_status["text"] = obj.get("text")
        _last_status["meta"] = obj.get("meta")
        return obj
    except Exception:
        return None

def _save_cache(text: str, meta: dict):
    obj = {"text": text, "meta": meta}
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    _last_status["text"] = text
    _last_status["meta"] = meta

def parse_teams_arg(arg: str) -> List[str]:
    parts = [p.strip() for p in arg.replace("\n", ",").split(",")]
    return [p for p in parts if p]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("/status 5000")],
          [KeyboardButton("/fixtures")],
          [KeyboardButton("/teams")]]
    await update.message.reply_text(
        "EPL Bot ready.\n"
        "Commands:\n"
        "/init <team1,team2,...,team20>\n"
        "/init_pl <season>  (init bằng standings từ football-data, ví dụ /init_pl 2025)\n"
        "/result <home>;<away>;<hg>;<ag>\n"
        "/status [sims] (mặc định 20000)\n"
        "/table\n"
        "/fixtures  (liệt kê một số cặp còn lại)\n"
        "/sync <provider> <season>  (provider = football-data | api-football)\n"
        "/teams",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True),
    )

async def init_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /init team1,team2,...,team20")
        return
    text = " ".join(context.args)
    teams = parse_teams_arg(text)
    try:
        L = League.init_from_list(teams)
    except Exception as e:
        await update.message.reply_text(f"Init error: {e}")
        return
    save_state(L.to_state(), path=STATE_PATH)
    await update.message.reply_text(f"Initialized league with {len(teams)} teams.")

async def init_pl_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # init from football-data.org standings for a season
    season = None
    if context.args:
        try:
            season = int(context.args[0])
        except Exception:
            pass
    if season is None:
        await update.message.reply_text("Usage: /init_pl <season>, ví dụ /init_pl 2025")
        return
    try:
        provider = FootballDataProvider()
        # Use standings to extract canonical team names
        table = provider.standings() if season is None else provider.standings()
        # football-data standings() in providers.py does not accept season in current impl,
        # but active standings is fine if season ongoing. For strict season, user can edit later.
        # We filter unique names in table order:
        teams = [row["team"] for row in table]
        # Ensure 20 teams
        teams = teams[:20]
        L = League.init_from_list(teams)
        save_state(L.to_state(), path=STATE_PATH)
        await update.message.reply_text("Initialized from football-data standings with 20 teams:\n" + "\n".join(teams))
    except Exception as e:
        await update.message.reply_text(f"/init_pl error: {e}")

async def result_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /result Home;Away;HG;AG")
        return
    payload = " ".join(context.args)
    try:
        home, away, hg, ag = [x.strip() for x in payload.split(";")]
        hg = int(hg); ag = int(ag)
    except Exception:
        await update.message.reply_text("Bad format. Use: /result Home;Away;HG;AG")
        return
    st = load_state(STATE_PATH); L = League.from_state(st)
    try:
        L.submit_result(home, away, hg, ag)
    except Exception as e:
        await update.message.reply_text(f"Record error: {e}")
        return
    save_state(L.to_state(), path=STATE_PATH)
    await update.message.reply_text(f"Recorded: {home} {hg}-{ag} {away}")

def _format_table_text(L: League, probs_top4=None, probs_safe=None, flags_top4=None, flags_safe=None) -> str:
    # chuẩn hóa số liệu
    rows = L.table_view()

    # tiện ích nhỏ
    def pct(x):
        return "-" if (x is None) else f"{100*x:>5.1f}"

    # tiêu đề với box-drawing
    top =  "┌──┬────────────────────────────┬──┬──┬──┬──┬───┬───┬──┬────┬─────────┬──────┬──────┐"
    head = "│# │ Team                       │P │W │D │L │GF │GA │GD│Pts │Official │%Top4│%Safe│"
    mid =  "├──┼────────────────────────────┼──┼──┼──┼──┼───┼───┼──┼────┼─────────┼──────┼──────┤"
    bot =  "└──┴────────────────────────────┴──┴──┴──┴──┴───┴───┴──┴────┴─────────┴──────┴──────┘"

    lines = [top, head, mid]
    for i, s in enumerate(rows, start=1):
        off = []
        if flags_top4 and flags_top4.get(s.team): off.append("CL✅")
        if flags_safe  and flags_safe.get(s.team): off.append("S✅")
        off_str = " ".join(off) if off else "—"

        p4 = pct(probs_top4.get(s.team) if probs_top4 else None)
        ps = pct(probs_safe.get(s.team)  if probs_safe  else None)

        # Cột cố định: team 28 ký tự, số liệu canh phải
        line = (
            f"│{i:>2}│ {s.team:<28}│"
            f"{s.played:>2}│{s.wins:>2}│{s.draws:>2}│{s.losses:>2}│"
            f"{s.gf:>3}│{s.ga:>3}│{s.gd:>2}│{s.points:>4}│"
            f"{off_str:^9}│{p4:>6}│{ps:>6}│"
        )
        lines.append(line)
    lines.append(bot)

    # Gói trong <pre> để Telegram dùng monospace (giữ cột thẳng)
    return "<pre>" + "\n".join(lines) + "</pre>"

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sims = 20000
    if context.args:
        try:
            sims = int(context.args[0])
        except Exception:
            pass

    st = load_state(STATE_PATH); L = League.from_state(st)
    flags_top4 = {t: guaranteed_top4(L, t) for t in L.teams}
    flags_safe = {t: guaranteed_safe(L, t) for t in L.teams}
    probs_top4, probs_safe = estimate_probabilities(L, sims=sims, seed=12345)

    txt = _format_table_text(L, probs_top4, probs_safe, flags_top4, flags_safe)
    await update.message.reply_text(txt, parse_mode=ParseMode.HTML)

    # ghi cache
    meta = {
        "timestamp": int(time.time()),
        "sims": sims,
        "seed": 12345,
        "results_count": len(st.get("results", [])),
        "fingerprint": _state_fingerprint(st),
    }
    _save_cache(txt, meta)


async def laststatus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _last_status["text"]:
        await update.message.reply_text("Chưa có kết quả nào được cache. Hãy gọi /status trước.")
        return
    await update.message.reply_text(_last_status["text"], parse_mode=ParseMode.HTML)


async def table_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = load_state(STATE_PATH); L = League.from_state(st)
    txt = _format_table_text(L)
    await update.message.reply_text(txt)

async def fixtures_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = load_state(STATE_PATH); L = League.from_state(st)
    rem = L.remaining_fixtures()
    if not rem:
        await update.message.reply_text("No remaining fixtures.")
        return
    sample = rem[:20]
    msg = "Remaining fixtures (sample):\n" + "\n".join(f"• {h} vs {a}" for h,a in sample)
    if len(rem) > len(sample):
        msg += f"\n... (+{len(rem)-len(sample)} more)"
    await update.message.reply_text(msg)

async def teams_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    st = load_state(STATE_PATH); L = League.from_state(st)
    await update.message.reply_text("Teams:\n" + "\n".join(L.teams))

async def sync_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /sync <provider> <season>. Provider: football-data | api-football")
        return
    provider_name = context.args[0].strip()
    try:
        season = int(context.args[1])
    except Exception:
        await update.message.reply_text("Season phải là số, ví dụ 2025")
        return

    st = load_state(STATE_PATH); L = League.from_state(st)
    try:
        if provider_name == "football-data":
            provider = FootballDataProvider()
            matches = provider.finished_matches(season=season)
        elif provider_name == "api-football":
            provider = ApiFootballProvider()
            matches = provider.finished_matches(season=season)
        else:
            await update.message.reply_text("Provider không hợp lệ.")
            return
    except Exception as e:
        await update.message.reply_text(f"Provider error: {e}")
        return

    fetched = len(matches)
    added = merge_finished_matches(L, matches)
    save_state(L.to_state(), path=STATE_PATH)
    await update.message.reply_text(f"Fetched {fetched} matches from {provider_name}. Added {added}.")

def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise RuntimeError("Please set TELEGRAM_TOKEN environment variable")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("init", init_cmd))
    app.add_handler(CommandHandler("init_pl", init_pl_cmd))
    app.add_handler(CommandHandler("result", result_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("table", table_cmd))
    app.add_handler(CommandHandler("fixtures", fixtures_cmd))
    app.add_handler(CommandHandler("teams", teams_cmd))
    app.add_handler(CommandHandler("sync", sync_cmd))
    app.add_handler(CommandHandler("laststatus", laststatus_cmd))
    app.add_handler(CommandHandler("usesnapshot", usesnapshot_cmd))
    app.add_handler(CommandHandler("refreshsnapshot", refreshsnapshot_cmd))
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()

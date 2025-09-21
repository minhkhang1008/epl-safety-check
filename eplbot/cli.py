from __future__ import annotations
import argparse, sys
from rich.table import Table
from rich.console import Console
import os

from .state import load_state, save_state
from .league import League
from .ilp_check import guaranteed_top4, guaranteed_safe
from .sim import estimate_probabilities

# providers & sync
from .providers import FootballDataProvider, ApiFootballProvider  # api-football có thể không dùng
from .sync import merge_finished_matches

# snapshot & publish
from .snapshot import build_snapshot, write_snapshot_file
from .publisher import publish_file, publish_gist, publish_s3, detect_current_season_year

console = Console()

# -----------------------------
# Helpers
# -----------------------------
def _print_table(L: League, probs_top4=None, probs_safe=None, flags_top4=None, flags_safe=None):
    tab = Table(title="Premier League Standings (Display order: Pts, GD, GF)", show_lines=False)
    tab.add_column("#", justify="right")
    tab.add_column("Team", justify="left")
    tab.add_column("P", justify="right")
    tab.add_column("W", justify="right")
    tab.add_column("D", justify="right")
    tab.add_column("L", justify="right")
    tab.add_column("GF", justify="right")
    tab.add_column("GA", justify="right")
    tab.add_column("GD", justify="right")
    tab.add_column("Pts", justify="right")
    tab.add_column("Official", justify="left")
    tab.add_column("%Top4", justify="right")
    tab.add_column("%Safe", justify="right")
    rows = L.table_view()
    for i,s in enumerate(rows, start=1):
        off = []
        if flags_top4 and flags_top4.get(s.team): off.append("CL✅")
        if flags_safe  and flags_safe.get(s.team): off.append("Safe✅")
        off_str = " ".join(off) if off else "-"
        p4 = f"{100*probs_top4.get(s.team,0):.1f}%" if probs_top4 else "-"
        ps = f"{100*probs_safe.get(s.team,0):.1f}%" if probs_safe else "-"
        tab.add_row(str(i), s.team, str(s.played), str(s.wins), str(s.draws), str(s.losses),
                    str(s.gf), str(s.ga), str(s.gd), str(s.points),
                    off_str, p4, ps)
    console.print(tab)


# -----------------------------
# Subcommands
# -----------------------------
def cmd_init(args):
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            teams = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
    else:
        teams = [t.strip() for t in args.teams.split(",")]
    L = League.init_from_list(teams)
    save_state(L.to_state(), path=args.state)
    console.print(f"[green]Initialized league with {len(teams)} teams and empty results.[/green]")

def cmd_result(args):
    st = load_state(args.state)
    L = League.from_state(st)
    L.submit_result(args.home, args.away, args.hg, args.ag)
    save_state(L.to_state(), path=args.state)
    console.print(f"[cyan]Recorded:[/cyan] {args.home} {args.hg}-{args.ag} {args.away}")

def cmd_status(args):
    st = load_state(args.state)
    L = League.from_state(st)
    flags_top4 = {t: guaranteed_top4(L, t) for t in L.teams}
    flags_safe = {t: guaranteed_safe(L, t) for t in L.teams}
    probs_top4 = probs_safe = None
    if not args.no_sim:
        probs_top4, probs_safe = estimate_probabilities(L, sims=args.sims, seed=args.seed)
    _print_table(L, probs_top4, probs_safe, flags_top4, flags_safe)

def cmd_sync(args):
    st = load_state(args.state)
    L = League.from_state(st)

    added = 0
    if args.provider == "football-data":
        provider = FootballDataProvider()
        if args.season is None:
            # auto-detect mùa hiện tại
            season = detect_current_season_year()
        else:
            season = args.season
        matches = provider.finished_matches(season=season)
        console.print(f"[yellow]Fetched {len(matches)} finished matches from football-data (season={season}).[/yellow]")
        added += merge_finished_matches(L, matches)
    elif args.provider == "api-football":
        provider = ApiFootballProvider()
        if args.season is None:
            raise SystemExit("Please provide --season for api-football.")
        matches = provider.finished_matches(season=args.season)
        console.print(f"[yellow]Fetched {len(matches)} finished matches from api-football (season={args.season}).[/yellow]")
        added += merge_finished_matches(L, matches)
    else:
        raise SystemExit("Unknown provider")

    save_state(L.to_state(), path=args.state)
    console.print(f"[green]Synced {added} matches from {args.provider}.[/green]")

def cmd_snapshot(args):
    st = load_state(args.state)
    L = League.from_state(st)
    snap = build_snapshot(L, sims=args.sims, seed=args.seed)
    write_snapshot_file(snap, args.out)
    console.print(f"[green]Snapshot written to {args.out} (sims={args.sims}, seed={args.seed}, results={len(L.results)}).[/green]")

def cmd_publish(args):
    # (tuỳ chọn) pre-sync
    st = load_state(args.state)
    L = League.from_state(st)
    if args.with_sync:
        season = args.season or detect_current_season_year()
        provider = FootballDataProvider()
        matches = provider.finished_matches(season=season)
        added = merge_finished_matches(L, matches)
        save_state(L.to_state(), path=args.state)
        console.print(f"[yellow]Pre-sync from football-data: season={season}, added={added}[/yellow]")

    # snapshot
    snap = build_snapshot(L, sims=args.sims, seed=args.seed)
    write_snapshot_file(snap, args.out)
    console.print(f"[green]Snapshot created: {args.out}[/green]")

    # publish
    if args.mode == "file":
        if not args.dest:
            raise SystemExit("--dest path required for mode=file")
        url = publish_file(args.out, args.dest)
    elif args.mode == "gist":
        gist_id = args.gist_id or os.environ.get("GIST_ID")
        if not gist_id:
            raise SystemExit("--gist-id or env GIST_ID required for mode=gist")
        url = publish_gist(args.out, gist_id=gist_id)
    elif args.mode == "s3":
        if not args.s3_bucket or not args.s3_key:
            raise SystemExit("--s3-bucket and --s3-key required for mode=s3")
        url = publish_s3(args.out, bucket=args.s3_bucket, key=args.s3_key, region=args.s3_region, public=not args.s3_private)
    else:
        raise SystemExit("Unknown publish mode")

    console.print(f"[cyan]Published to: {url}[/cyan]")


# -----------------------------
# main
# -----------------------------
def main(argv=None):
    p = argparse.ArgumentParser(prog="eplbot", description="EPL Top-4 & Relegation Safety Bot")
    p.add_argument("--state", default="league_state.json", help="Path to state JSON file")
    sub = p.add_subparsers()

    # init
    p_init = sub.add_parser("init", help="Initialize league with 20 teams")
    p_init.add_argument("--teams", help="Comma-separated 20 team names")
    p_init.add_argument("--file", help="Text file with one team per line (20 lines)")
    p_init.set_defaults(func=cmd_init)

    # result
    p_res = sub.add_parser("result", help="Record a match result")
    p_res.add_argument("--home", required=True)
    p_res.add_argument("--away", required=True)
    p_res.add_argument("--hg", type=int, required=True)
    p_res.add_argument("--ag", type=int, required=True)
    p_res.set_defaults(func=cmd_result)

    # status
    p_stat = sub.add_parser("status", help="Show table, official flags, and probabilities")
    p_stat.add_argument("--no-sim", action="store_true", help="Skip Monte Carlo")
    p_stat.add_argument("--sims", type=int, default=20000, help="Number of simulations")
    p_stat.add_argument("--seed", type=int, default=12345, help="RNG seed for reproducibility")
    p_stat.set_defaults(func=cmd_status)

    # sync
    p_sync = sub.add_parser("sync", help="Sync finished matches from a provider")
    p_sync.add_argument("--provider", choices=["football-data", "api-football"], required=True)
    p_sync.add_argument("--season", type=int, help="Season year, e.g., 2025 (if omitted for football-data, auto-detect)")
    p_sync.set_defaults(func=cmd_sync)

    # snapshot
    p_snap = sub.add_parser("snapshot", help="Run simulation once and export snapshot.json")
    p_snap.add_argument("--sims", type=int, default=20000)
    p_snap.add_argument("--seed", type=int, default=12345)
    p_snap.add_argument("--out", default="snapshot.json")
    p_snap.set_defaults(func=cmd_snapshot)

    # publish
    p_pub = sub.add_parser("publish", help="Run sims once, create snapshot.json, and publish it")
    p_pub.add_argument("--sims", type=int, default=20000)
    p_pub.add_argument("--seed", type=int, default=12345)
    p_pub.add_argument("--out", default="snapshot.json", help="Local snapshot path to create before publishing")
    p_pub.add_argument("--with-sync", action="store_true", help="Pre-sync finished matches from football-data before snapshot")
    p_pub.add_argument("--season", type=int, help="Season start year; if omitted, auto-detect via football-data")
    p_pub.add_argument("--mode", choices=["file","gist","s3"], required=True)
    # file
    p_pub.add_argument("--dest", help="Destination file path for mode=file")
    # gist
    p_pub.add_argument("--gist-id", help="Gist ID for mode=gist (or set env GIST_ID)")
    # s3
    p_pub.add_argument("--s3-bucket")
    p_pub.add_argument("--s3-key")
    p_pub.add_argument("--s3-region")
    p_pub.add_argument("--s3-private", action="store_true", help="Do not set public-read on S3 object")
    p_pub.set_defaults(func=cmd_publish)

    args = p.parse_args(argv)
    if not hasattr(args, "func"):
        p.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

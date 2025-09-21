# Data Providers Integration

Two providers supported:

1) **football-data.org** (v4) {allow latest data for free tier}
   - Docs: https://www.football-data.org/documentation/api
   - Auth header: `X-Auth-Token: <API_KEY>`
   - Example endpoints used:
     - `/v4/competitions/PL/standings`
     - `/v4/competitions/PL/matches?status=FINISHED&season=YYYY`
   - Set env: `export FOOTBALL_DATA_API_KEY=...`
   - Sync finished results into local state:
     ```bash
     python -m eplbot.cli sync --provider football-data --season 2025
     ```

2) **API-FOOTBALL** (api-sports.io) {**NOT** allow latest data for free tier}
   - Docs: https://www.api-football.com/documentation-v3
   - Auth header: `x-apisports-key: <API_KEY>`
   - Premier League: league=39
   - Example endpoints used:
     - `/v3/standings?league=39&season=YYYY`
     - `/v3/fixtures?league=39&season=YYYY&status=FT`
   - Set env: `export APIFOOTBALL_API_KEY=...`
   - Sync:
     ```bash
     python -m eplbot.cli sync --provider api-football --season 2025
     ```

Notes:
- First initialize the league with your 20 team names identical to provider naming.
- Rate limits differ by provider and plan. Use caching and avoid excessive syncs.

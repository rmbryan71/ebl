# EBL requirements (source: /Users/robertbryan/PycharmProjects/rmbryan71.github.io/ebl/constitution.md)

Columns: ID | Status | Priority | Feature | Requirement
Statuses: not started, in progress, done, deferred.

| ID | Status | Priority | Feature | Requirement |
| --- | --- | --- | --- | --- |
| REQ-001 | done |  |  | Phillies players only. |
| REQ-003 | done |  |  | Scores tallied weekly. |
| REQ-004 | done |  |  | Participation is free; no prize money. |
| REQ-005 | done |  |  | There are 8 teams. |
| REQ-006 | done |  |  | Each team has 4 roster spots. |
| REQ-007 | done |  |  | Pitching metric: innings pitched. |
| REQ-008 | done |  |  | Offense metric: total bases + walks + HBP + steals. |
| REQ-009 | done |  |  | Weekly points: most pitching gets 10. |
| REQ-010 | done |  |  | Next most pitching gets 8. |
| REQ-011 | done |  |  | Next most pitching gets 4. |
| REQ-012 | done |  |  | Most offense gets 10. |
| REQ-013 | done |  |  | Next most offense gets 8. |
| REQ-014 | done |  |  | Next most offense gets 4. |
| REQ-015 | done |  |  | Partial weeks (start, All-Star break, end) award the same points as full weeks. |
| REQ-016 | done |  |  | Pitcher offense counts as offense. |
| REQ-017 | done |  |  | Hitter pitching outs count. |
| REQ-018 | done |  |  | Teams tied for a position each receive that position's points. |
| REQ-019 | done |  |  | No second-place points if two teams tie for first. |
| REQ-020 | done |  |  | No third-place points if two or more teams tie for second. |
| REQ-021 | done |  |  | Three-way tie for first: all three get first-place points; no other points. |
| REQ-022 | done |  |  | Six-way tie for third: all six get third-place points. |
| REQ-023 | done |  |  | Only Phillies 40-man roster players can be on teams. |
| REQ-025 | done |  |  | No remedy for suspensions or injuries (do not create empty spots). |
| REQ-026 | done |  |  | Empty roster spots never have to be filled. |
| REQ-027 | done |  |  | Only MLB production counts. |
| REQ-028 | done |  |  | No action required for send-downs/call-ups. |
| REQ-029 | done |  |  | Any mix of hitters/pitchers is allowed. |
| REQ-030 | done |  | Roster Moves | Max 1 roster move attempt per week. |
| REQ-031 | done |  | Roster Moves | One attempt even if multiple open spots. |
| REQ-032 | done |  | Roster Moves | Roster moves are processed Sunday night after points are awarded. |
| REQ-033 | done |  | Roster Moves | A roster move attempt includes one player to drop and three prioritized players to add. |
| REQ-034 | done |  | Roster Moves | Cannot target a player on another team hoping they will be dropped before your turn. |
| REQ-035 | done |  | Roster Moves | Teams with empty roster spots go first; if multiple, lower-ranking teams go first. |
| REQ-036 | done |  | Roster Moves | Otherwise processed in reverse standings order; ties resolved randomly. |
| REQ-037 | done |  | Roster Moves | If target player is unavailable, nothing happens; you keep your player. |
| REQ-039 | done |  | Roster Moves | If two tied teams attempt same player, assign randomly. |
| REQ-040 | done |  |  | No trading players between teams. |
| REQ-041 | done |  |  | Zoom call at 6:00 PM Sunday, March 22, 2026. |
| REQ-042 | not started |  | Auction | Each team gets $100 budget. |
| REQ-043 | not started |  | Auction | Bids are whole dollars only. |
| REQ-044 | not started |  | Auction | Must fill all 4 roster spots during auction. |
| REQ-045 | not started |  | Auction | Owners nominate players; nomination starts at $1. |
| REQ-046 | not started |  | Auction | Must reserve enough budget to fill all roster spots. |
| REQ-047 | not started |  | Auction | Nomination order random, decided at auction start. |
| REQ-048 | done |  |  | At end of each auction, team and price are known. |
| REQ-049 | done |  |  | Extra money at end is allowed. |
| REQ-050 | done |  |  | Exactly 32 auctions. |
| REQ-052 | done |  |  | Otherwise open auction with shouted bids. |
| REQ-053 | done |  |  | Player ownership is for 2026 season only. |
| REQ-054 | done |  |  | No requirement to reveal identity to participate. |
| REQ-055 | not started |  |  | All data must be anonymized and free of personally identifiable information. |
| REQ-056 | done |  |  | Detailed, immutable audit trail for roster move attempts, stat updates, point awards, data corrections, and later logins/anonymized owner actions. |
| REQ-057 | done |  |  | Audit trail must be available to everyone at all times. |
| REQ-058 | not started |  |  | Provide a health check/status page. |
| REQ-059 | done |  |  | Improve data persistence for deployments. |
| REQ-060 | not started |  |  | User accounts. |
| REQ-061 | not started |  |  | Authentication. |
| REQ-063 | done |  |  | Move the rules into the app. |
| REQ-064 | not started |  |  | Admin panel. |
| REQ-066 | done |  | Website | Fix wrapping for long team names. |
| REQ-067 | done |  | Roster Moves | Let admins submit roster moves for all teams. |
| REQ-069 | not started |  | Roster Moves | Handle players who leave the Phillies and return in the same year. |
| REQ-070 | not started |  | Roster Moves | Show team alumni on the team page. |
| REQ-071 | done |  | Admin | Add an admin account to test setup. |
| REQ-065 | done |  | Website | Move lab notebook into website. |
| REQ-072 | not started |  | Website | Phillies transactions page. |
| REQ-073 | not started |  |  | Database backup and restore. |
| REQ-074 | not started |  | Website | Charts and graphs. |
| REQ-075 | not started |  |  | Sort out underscores and dashes. |
| REQ-076 | not started |  |  | Refactor player table to be immutable. |
| REQ-077 | in progress |  | Documentation | Document AI-assisted development workflow best practices. |
| REQ-078 | not started |  |  | Set up alerting for system failures. |
| REQ-079 | not started |  |  | Run the simulation on 2024 and other seasons. |
| REQ-080 | not started |  |  | Handle cases where players are dropped between the auction and the start of the season. |
| REQ-081 | not started |  | Website | Decorate player cards with icons for achievements like two-way scoring. |

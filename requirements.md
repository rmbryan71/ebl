# EBL requirements (source: /Users/robertbryan/PycharmProjects/rmbryan71.github.io/ebl/constitution.md)

Columns: ID | Status | Priority | Requirement
Statuses: not started, in progress, done, deferred.

## League scope
| ID | Status | Priority | Requirement |
| --- | --- | --- | --- |
| REQ-001 | done |  | Phillies players only. |
| REQ-002 | not started |  | Live auction for players. |
| REQ-003 | not started |  | Scores tallied weekly. |
| REQ-004 | done |  | Participation is free; no prize money. |
| REQ-005 | done |  | There are 8 teams. |
| REQ-006 | done |  | Each team has 4 roster spots. |
| REQ-007 | done |  | Pitching metric: innings pitched. |
| REQ-008 | not started |  | Offense metric: total bases + walks + HBP + steals. |

## Scoring
| ID | Status | Priority | Requirement |
| --- | --- | --- | --- |
| REQ-009 | not started |  | Weekly points: most pitching gets 10. |
| REQ-010 | not started |  | Next most pitching gets 8. |
| REQ-011 | not started |  | Next most pitching gets 4. |
| REQ-012 | not started |  | Most offense gets 10. |
| REQ-013 | not started |  | Next most offense gets 8. |
| REQ-014 | not started |  | Next most offense gets 4. |
| REQ-015 | not started |  | Partial weeks (start, All-Star break, end) award the same points as full weeks. |
| REQ-016 | not started |  | Pitcher offense counts as offense. |
| REQ-017 | not started |  | Hitter pitching outs count. |

## Ties
| ID | Status | Priority | Requirement |
| --- | --- | --- | --- |
| REQ-018 | not started |  | Teams tied for a position each receive that position's points. |
| REQ-019 | not started |  | No second-place points if two teams tie for first. |
| REQ-020 | not started |  | No third-place points if two or more teams tie for second. |
| REQ-021 | not started |  | Three-way tie for first: all three get first-place points; no other points. |
| REQ-022 | not started |  | Six-way tie for third: all six get third-place points. |

## Rosters
| ID | Status | Priority | Requirement |
| --- | --- | --- | --- |
| REQ-023 | not started |  | Only Phillies 40-man roster players can be on teams. |
| REQ-024 | not started |  | Player leaving the Phillies (trade, retirement, death, waiver pickup, or any reason) creates an empty roster spot. |
| REQ-025 | done |  | No remedy for suspensions or injuries (do not create empty spots). |
| REQ-026 | done |  | Empty roster spots never have to be filled. |
| REQ-027 | done |  | Only MLB production counts. |
| REQ-028 | done |  | No action required for send-downs/call-ups. |
| REQ-029 | done |  | Any mix of hitters/pitchers is allowed. |

## Roster moves
| ID | Status | Priority | Requirement |
| --- | --- | --- | --- |
| REQ-030 | not started |  | Max 1 roster move attempt per week. |
| REQ-031 | not started |  | One attempt even if multiple open spots. |
| REQ-032 | not started |  | Processed Sunday night after points are awarded. |
| REQ-033 | not started |  | Each attempt includes one drop and one add. |
| REQ-034 | not started |  | Cannot target a player on another team hoping they will be dropped before your turn. |
| REQ-035 | not started |  | Teams with empty roster spots go first; if multiple, lower-ranking teams go first. |
| REQ-036 | not started |  | Otherwise processed in reverse standings order; ties resolved randomly. |
| REQ-037 | not started |  | If target player is unavailable, nothing happens; you keep your player. |
| REQ-038 | not started |  | Newly added Phillies players become available at end of week acquired. |
| REQ-039 | not started |  | If two tied teams attempt same player, assign randomly. |
| REQ-040 | done |  | No trading players between teams. |

## Auction
| ID | Status | Priority | Requirement |
| --- | --- | --- | --- |
| REQ-041 | not started |  | Zoom call at 6:00 PM Sunday, March 22, 2026. |
| REQ-042 | not started |  | Each team gets $100 budget. |
| REQ-043 | not started |  | Bids are whole dollars only. |
| REQ-044 | not started |  | Must fill all 4 roster spots during auction. |
| REQ-045 | not started |  | Owners nominate players; nomination starts at $1. |
| REQ-046 | not started |  | Must reserve enough budget to fill all roster spots. |
| REQ-047 | not started |  | Nomination order random, decided at auction start. |
| REQ-048 | not started |  | At end of each auction, team and price are known. |
| REQ-049 | done |  | Extra money at end is allowed. |
| REQ-050 | not started |  | Exactly 32 auctions. |
| REQ-051 | not started |  | If two owners simultaneously bid $97 at start, older owner wins. |
| REQ-052 | done |  | Otherwise open auction with shouted bids. |
| REQ-053 | done |  | Player ownership is for 2026 season only. |

## Privacy
| ID | Status | Priority | Requirement |
| --- | --- | --- | --- |
| REQ-054 | done |  | No requirement to reveal identity to participate. |
| REQ-055 | not started |  | All data must be anonymized and free of personally identifiable information. |

## Audit trail
| ID | Status | Priority | Requirement |
| --- | --- | --- | --- |
| REQ-056 | not started |  | Detailed, immutable audit trail for roster move attempts, stat updates, point awards, data corrections, and later logins/anonymized owner actions. |
| REQ-057 | not started |  | Audit trail must be available to everyone at all times. |

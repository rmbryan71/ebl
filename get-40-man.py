import statsapi

roster = statsapi.roster(teamId=143)
with open("40-man-roster.md", "w") as f:
    f.write(roster)
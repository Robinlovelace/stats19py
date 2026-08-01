# Minimal precise trace
Sys.setenv(STATS19_DOWNLOAD_DIRECTORY = "~/github/robinlovelace/stats19py/data")
suppressMessages(pkgload::load_all("~/github/ropensci/stats19", quiet = TRUE))

s <- stats19_schema
# exact schema entries for carriageway_hazards code 0
rows <- s$variable == "carriageway_hazards" & s$code == 0
cat("schema rows for code 0:", sum(rows), "\n")
dput(s[rows, c("code", "label")])
cat("label type:", class(s$label), "\n")

# replicate lookup + merge on 3 rows only
x <- read_collisions(year = 2024, format = FALSE, silent = TRUE)
sub <- x[c(92, 222, 465), c("carriageway_hazards", "carriageway_hazards_historic")]
cat("\nraw sub:\n"); print(sub)

lk_main <- s[s$variable == "carriageway_hazards", c("code", "label")]
lk_hist <- s[s$variable == "carriageway_hazards_historic", c("code", "label")]
m_main <- match(sub$carriageway_hazards, lk_main$code)
m_hist <- match(sub$carriageway_hazards_historic, lk_hist$code)
cat("\nmain matched labels:", dput(lk_main$label[m_main]))
cat("\nhist matched labels:", dput(lk_hist$label[m_hist]))

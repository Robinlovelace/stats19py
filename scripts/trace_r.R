# Trace R's format steps for carriageway_hazards rows 91/221/464 (1-indexed: 92,222,465)
Sys.setenv(STATS19_DOWNLOAD_DIRECTORY = "~/github/robinlovelace/stats19py/data")
suppressMessages(pkgload::load_all("~/github/ropensci/stats19", quiet = TRUE))

raw <- read_collisions(year = 2024, format = FALSE, silent = TRUE)
cat("raw cols:", ncol(raw), "\n")
cat("raw rows 92,222,465 main:", raw$carriageway_hazards[c(92, 222, 465)], "\n")
cat("raw rows 92,222,465 historic:", raw$carriageway_hazards_historic[c(92, 222, 465)], "\n")

# replicate format_stats19 internals
x <- raw
names(x) <- format_column_names(names(x))
lkp_vars <- stats19_variables$variable[stats19_variables$table == "collision"]
vars_to_change <- intersect(names(x), lkp_vars)
vars_to_change <- intersect(vars_to_change, stats19_schema$variable)
cat("carriageway_hazards in vars_to_change:", "carriageway_hazards" %in% vars_to_change, "\n")
cat("carriageway_hazards_historic in vars_to_change:", "carriageway_hazards_historic" %in% vars_to_change, "\n")

# lookup for main col code 0
lk <- stats19_schema[stats19_schema$variable == "carriageway_hazards", c("code", "label")]
cat("main code 0 label:", as.character(lk$label[lk$code == 0]), "\n")
# lookup for historic col code 9
lkh <- stats19_schema[stats19_schema$variable == "carriageway_hazards_historic", c("code", "label")]
cat("historic code 9 label:", as.character(lkh$label[lkh$code == 9]), "\n")

# Manually replicate R format_stats19 steps to find divergence
Sys.setenv(STATS19_DOWNLOAD_DIRECTORY = "~/github/robinlovelace/stats19py/data")
suppressMessages(pkgload::load_all("~/github/ropensci/stats19", quiet = TRUE))
s <- stats19_schema
v <- stats19_variables

x <- read_collisions(year = 2024, format = FALSE, silent = TRUE)
names(x) <- format_column_names(names(x))

# Step: lookups for carriageway_hazards
v_to_change <- intersect(names(x), v$variable[v$table == "collision"])
v_to_change <- intersect(v_to_change, s$variable)
cat("carriageway_hazards in list:", "carriageway_hazards" %in% v_to_change, "\n")

# what are the raw types?
cat("class main:", class(x$carriageway_hazards), "| class historic:", class(x$carriageway_hazards_historic), "\n")
cat("main values:", x$carriageway_hazards[c(92, 222, 465)], "\n")

lk <- s[s$variable == "carriageway_hazards", c("code", "label")]
cat("lookup$code class:", class(lk$code), "\n")
cat("lookup code 0:", lk$code[lk$code == 0], "label:", as.character(lk$label[lk$code == 0]), "\n")

# apply lookup like R
matched_idx <- match(x$carriageway_hazards, lk$code)
cat("matched at 92,222,465:", matched_idx[c(92, 222, 465)], "\n")
has_match <- !is.na(matched_idx)
cat("has_match at those rows:", has_match[c(92, 222, 465)], "\n")
labels <- lk$label[matched_idx[has_match]]
cat("labels at those rows:", as.character(labels[!is.na(matched_idx[c(92,222,465)]) & has_match[c(92,222,465)]]), "\n")

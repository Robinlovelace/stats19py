#!/usr/bin/env Rscript
# capture_raw_meta.R — capture RAW (format=FALSE) read metadata from the
# stats19 dev package: column names + R classes per column, per table/year.
# Used as fixtures for the Python read implementation (Slice 3).

args <- commandArgs(trailingOnly = TRUE)
years_arg <- if ("--years" %in% args) args[which(args == "--years") + 1] else "2024,2025"
years <- as.integer(strsplit(years_arg, ",")[[1]])

repo_root <- tryCatch(
  system2("git", c("rev-parse", "--show-toplevel"), stdout = TRUE),
  error = function(e) "."
)
stats19_dev <- Sys.getenv("STATS19_DEV_DIR", "~/github/ropensci/stats19")
suppressMessages(pkgload::load_all(stats19_dev, quiet = TRUE))
set_data_directory(file.path(repo_root, "data"))
out_dir <- file.path(repo_root, "scripts", "reference")
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

readers <- list(
  collision = function(yr) read_collisions(year = yr, format = FALSE, silent = TRUE),
  casualty = function(yr) read_casualties(year = yr, format = FALSE),
  vehicle = function(yr) read_vehicles(year = yr, format = FALSE)
)

for (yr in years) {
  for (tbl in names(readers)) {
    x <- readers[[tbl]](yr)
    meta <- data.frame(
      table = tbl, year = yr,
      rows = nrow(x), cols = ncol(x),
      column_names = paste(names(x), collapse = ","),
      classes = paste(vapply(x, function(c) class(c)[1], character(1)), collapse = ","),
      stringsAsFactors = FALSE
    )
    write.csv(meta, file.path(out_dir, sprintf("meta_raw_%s_%d.csv", tbl, yr)),
              row.names = FALSE)
    cat(sprintf("raw meta %s %d: %d rows x %d cols\n", tbl, yr, nrow(x), ncol(x)))
  }
}
cat("Done.\n")

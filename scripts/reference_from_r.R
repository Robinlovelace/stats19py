#!/usr/bin/env Rscript
# reference_from_r.R — generate R reference outputs for the R↔Python comparison.
#
# Runs against the DEV version of ropensci/stats19 (pkgload::load_all) so we
# compare against v4.1.0-dev semantics, not the buggy CRAN 4.0.0.
#
# Usage:
#   Rscript scripts/reference_from_r.R [--years 2024,2025] [--data-dir PATH]
#
# Outputs (written under scripts/reference/):
#   reference_<table>_<year>.csv        — formatted output (R format_* applied)
#   meta_<table>_<year>.csv             — column names, classes, row/col counts
#
# Requires: R with pkgload + the stats19 dev checkout available via
# STATS19_DEV_DIR (default: ../stats19 relative to repo root, i.e. the
# ropensci/stats19 checkout).

args <- commandArgs(trailingOnly = TRUE)
years_arg <- if ("--years" %in% args) args[which(args == "--years") + 1] else "2024,2025"
data_dir_arg <- if ("--data-dir" %in% args) args[which(args == "--data-dir") + 1] else NULL

years <- as.integer(strsplit(years_arg, ",")[[1]])
repo_root <- tryCatch(
  system2("git", c("rev-parse", "--show-toplevel"), stdout = TRUE),
  error = function(e) "."
)
stats19_dev <- Sys.getenv("STATS19_DEV_DIR", "~/github/ropensci/stats19")
if (!dir.exists(file.path(stats19_dev, "R"))) {
  stop("stats19 dev checkout not found at ", stats19_dev,
       ". Set STATS19_DEV_DIR or clone ropensci/stats19 next to this repo.")
}

suppressMessages(pkgload::load_all(stats19_dev, quiet = TRUE))
if (is.null(data_dir_arg)) {
  data_dir <- file.path(repo_root, "data")
} else {
  data_dir <- data_dir_arg
}
set_data_directory(data_dir)
out_dir <- file.path(repo_root, "scripts", "reference")
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

tables <- list(
  collision = function(yr) read_collisions(year = yr, silent = TRUE),
  casualty = function(yr) read_casualties(year = yr),
  vehicle = function(yr) read_vehicles(year = yr)
)

for (yr in years) {
  for (tbl in names(tables)) {
    f <- tables[[tbl]]
    x <- f(yr)  # format = TRUE by default
    meta <- data.frame(
      table = tbl, year = yr,
      rows = nrow(x), cols = ncol(x),
      stringsAsFactors = FALSE
    )
    meta$column_names <- paste(names(x), collapse = ",")
    meta$classes <- paste(vapply(x, function(c) class(c)[1], character(1)), collapse = ",")
    write.csv(meta, file.path(out_dir, sprintf("meta_%s_%d.csv", tbl, yr)),
              row.names = FALSE)
    write.csv(x, file.path(out_dir, sprintf("reference_%s_%d.csv", tbl, yr)),
              row.names = FALSE)
    cat(sprintf("wrote %s %d: %d rows x %d cols\n", tbl, yr, nrow(x), ncol(x)))
  }
}
cat("Done. References written to", out_dir, "\n")

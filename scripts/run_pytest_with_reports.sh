#!/usr/bin/env bash

set -euo pipefail

mkdir -p test-results

python -m pytest \
  --tb=short \
  --junitxml=test-results/results.xml \
  --cov=student_analysis_pipeline/app \
  --cov-report=xml:test-results/coverage.xml \
  --cov-report=term-missing:skip-covered \
  -v \
  "$@"

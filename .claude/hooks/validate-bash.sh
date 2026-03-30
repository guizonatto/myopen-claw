#!/bin/bash
# Valida scripts bash antes do commit

for file in $(git diff --cached --name-only | grep -E '\.sh$'); do
  bash -n "$file" || exit 1
done

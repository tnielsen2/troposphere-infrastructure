#!/bin/bash

file_path="./.github/workflows/changed_files"

while IFS= read -r json_file; do
  echo "${json_file}" has changed.
  # Perform your desired action here using "$json_file"
done < "$file_path"

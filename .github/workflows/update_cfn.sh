#!/bin/bash

FILE_PATH="./.github/workflows/changed_files"

# Check if the file exists and is not empty
if [ -e "$FILE_PATH" ] && [ $(stat -c %s "$FILE_PATH") -eq 0 ]; then
  echo "The file exists but is empty."
  exit 0
fi

# Array to store background task PIDs
declare -a PIDS

while IFS= read -r json_file; do
  echo "${json_file}" has changed.

  # Extract the components from the directory path
  IFS='/' read -ra COMPONENTS <<< "$json_file"

  # Convert variables to uppercase
  TEMPLATE_FILE="$json_file"
  STACK_NAME="${COMPONENTS[-1]%.json}"  # Remove the ".json" extension from the last component
  ENVIRONMENT="${COMPONENTS[1]}"
  AWS_REGION="${COMPONENTS[2]}"

  # Define output and error log files
  OUTPUT_LOG="$ENVIRONMENT-$STACK_NAME.out.log"
  ERROR_LOG="$ENVIRONMENT-$STACK_NAME.err.log"

  # Debug output
  echo "Executing: aws cloudformation deploy --template-file $TEMPLATE_FILE --stack-name $ENVIRONMENT-$STACK_NAME --region $AWS_REGION --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND"

  # Execute the AWS CloudFormation deploy command in the background, redirecting output and error streams
  aws cloudformation deploy --template-file "$TEMPLATE_FILE" --stack-name "$ENVIRONMENT-$STACK_NAME" --region "$AWS_REGION" --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND > "$OUTPUT_LOG" 2> "$ERROR_LOG" &

  # Store the PID of the background task
  PIDS+=($!)

done < "$FILE_PATH"

# Wait for all background jobs to finish
for pid in "${PIDS[@]}"; do
  wait "$pid"
done

# Debug output
echo "All background tasks have finished."

# Concatenate and display the output of all executions
echo "==== Output of All Executions ===="
for LOG_FILE in *-*.out.log; do
  echo "Output of $LOG_FILE:"
  cat "$LOG_FILE"
  echo "================================"
done

# Cleanup: Remove log files
rm -f *-*.out.log *-*.err.log

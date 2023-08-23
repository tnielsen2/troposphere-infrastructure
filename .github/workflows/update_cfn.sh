#!/bin/bash

FILE_PATH="./.github/workflows/changed_files"

if [ -e "$FILE_PATH" ] && [ $(stat -c %s "$FILE_PATH") -gt 1 ]; then
  echo "CFN changes detected in changed_files"
  cat "$FILE_PATH"
else
  echo "No CFN file changes detected. Exiting with code 0.."
  exit 0
fi

# Array to store background task PIDs
declare -a PIDS

while IFS= read -r JSON_FILE; do
  echo "${JSON_FILE}" has changed.

  # Extract the components from the directory path
  IFS='/' read -ra COMPONENTS <<< "$JSON_FILE"

  # Convert variables to uppercase
  TEMPLATE_FILE="$JSON_FILE"
  STACK_NAME="${COMPONENTS[-1]%.json}"  # Remove the ".json" extension from the last component
  ENVIRONMENT="${COMPONENTS[1]}"
  AWS_REGION="${COMPONENTS[2]}"

  # Define output and error log files
  OUTPUT_LOG="$ENVIRONMENT-$STACK_NAME.out.log"
  ERROR_LOG="$ENVIRONMENT-$STACK_NAME.err.log"

  # Debug output
  echo "Executing: aws cloudformation deploy --template-file $TEMPLATE_FILE --stack-name $ENVIRONMENT-$STACK_NAME --region $AWS_REGION --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND"
  STACK_NAME="$ENVIRONMENT-$STACK_NAME"
  # Execute the AWS CloudFormation deploy command in the background, redirecting output to $OUTPUT_LOG and both stdout and stderr to $ERROR_LOG
  aws cloudformation deploy --template-file "$TEMPLATE_FILE" --stack-name "$STACK_NAME" --region "$AWS_REGION" --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND > "$OUTPUT_LOG" 2>> "$ERROR_LOG" || {
    # If the deployment command fails, execute additional commands
    echo "Echoing failed stack deploy for $STACK_NAME"
    aws cloudformation describe-stack-events --stack-name "$STACK_NAME" --region "$AWS_REGION"
    # You can add more commands here if needed
    # ...

    # Exit the script with a non-zero status
    exit 1
  } &

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

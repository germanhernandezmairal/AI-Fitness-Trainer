#!/bin/bash
# Retries launching the free-tier Ampere A1 VM every RETRY_INTERVAL seconds until it
# succeeds (Oracle's Always-Free ARM capacity is often exhausted; this is the standard
# workaround) or MAX_ATTEMPTS is reached. Requires `oci setup config` already done.
#
# Usage: ./oracle-vm-retry-launch.sh

set -uo pipefail

TENANCY_ID="ocid1.tenancy.oc1..aaaaaaaaioyo6j4l2rrzdn4y7ajhklg5rpvpsx6t5c45d5jhiwfiuivg5gna"
AD_NAME="kSDN:EU-MADRID-1-AD-1"
SUBNET_ID="ocid1.subnet.oc1.eu-madrid-1.aaaaaaaavr4n42x4dot34wwofzwinkqcm4nw6aehe6h4rl3eqw5ibyeivkcq"
IMAGE_ID="ocid1.image.oc1.eu-madrid-1.aaaaaaaam66s2a356tcidqqq45clmh6nicjbrjezjwqg7suj4jp6y5fnueia" # Canonical-Ubuntu-24.04-aarch64-2026.07.17-0
SSH_KEY_FILE="$HOME/.ssh/oracle_ai_fitness_trainer.pub"
DISPLAY_NAME="ai-fitness-trainer-vm"
SHAPE="VM.Standard.A1.Flex"
OCPUS=2
MEMORY_GB=12
BOOT_VOLUME_GB=100 # Always-Free ceiling is 200GB total boot volume across all instances

RETRY_INTERVAL=60
MAX_ATTEMPTS=1000 # ~16.6 hours at 60s; Ctrl-C anytime, safe to re-run

echo "Starting retry-launch loop for $DISPLAY_NAME (every ${RETRY_INTERVAL}s, up to $MAX_ATTEMPTS attempts)"
echo "Shape: $SHAPE, ${OCPUS} OCPUs / ${MEMORY_GB}GB RAM, AD: $AD_NAME"
echo

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  echo "[$ts] Attempt $attempt..."

  out=$(oci compute instance launch \
    --compartment-id "$TENANCY_ID" \
    --availability-domain "$AD_NAME" \
    --shape "$SHAPE" \
    --shape-config "{\"ocpus\": $OCPUS, \"memoryInGBs\": $MEMORY_GB}" \
    --subnet-id "$SUBNET_ID" \
    --image-id "$IMAGE_ID" \
    --assign-public-ip true \
    --ssh-authorized-keys-file "$SSH_KEY_FILE" \
    --display-name "$DISPLAY_NAME" \
    --boot-volume-size-in-gbs "$BOOT_VOLUME_GB" \
    --wait-for-state RUNNING \
    --output json 2>&1)
  status=$?

  if [ $status -eq 0 ]; then
    echo
    echo "=== SUCCESS on attempt $attempt ==="
    echo "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)['data']
print('Instance ID:', d['id'])
print('Lifecycle state:', d['lifecycle-state'])
"
    echo "$out" > "$(dirname "$0")/oracle-vm-launch-result.json"
    echo "Full response saved to deploy/oracle-vm-launch-result.json"
    echo
    echo "Next: fetch the public IP with:"
    echo "  oci compute instance list-vnics --instance-id <instance-id> --query \"data[0].\\\"public-ip\\\"\" --raw-output"
    exit 0
  fi

  # Out-of-capacity, rate-limit, and plain network/connection errors are expected/transient
  # -- keep retrying. Anything else (bad OCID, auth failure, quota, etc.) is a real problem
  # -- stop and show it.
  if echo "$out" | grep -qiE "capacity|TooManyRequests|Too many requests|RequestException|connection.*timed out|Connection aborted|ConnectionError"; then
    echo "  (expected transient failure -- retrying in ${RETRY_INTERVAL}s)"
  else
    echo
    echo "=== UNEXPECTED ERROR on attempt $attempt -- stopping ==="
    echo "$out"
    exit 1
  fi

  sleep "$RETRY_INTERVAL"
done

echo "Reached MAX_ATTEMPTS ($MAX_ATTEMPTS) without success. Re-run the script to keep trying."
exit 1

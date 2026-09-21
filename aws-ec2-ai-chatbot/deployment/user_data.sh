#!/bin/bash
# EC2 bootstrap script (User Data) for the AWS EC2 AI Chatbot.
#
# This script performs a minimal, safe setup: installing Python, pip,
# and Git so the repository can be cloned and run. It intentionally
# avoids risky system changes (no firewall changes, no user account
# changes, no disk partitioning).
#
# NOTE: Amazon Linux and Ubuntu use different package managers and
# default package names. This script tries to detect the distribution
# and use the correct commands, but you should verify behavior on your
# chosen AMI. See README.md for manual, step-by-step instructions.

set -e

log() {
  echo "[user_data] $1"
}

if [ -f /etc/os-release ]; then
  . /etc/os-release
fi

log "Detected OS: ${PRETTY_NAME:-unknown}"

if [ "$ID" = "amzn" ]; then
  log "Amazon Linux detected. Installing Python3, pip, and Git via dnf/yum."
  if command -v dnf >/dev/null 2>&1; then
    dnf install -y python3 python3-pip git
  else
    yum install -y python3 python3-pip git
  fi
elif [ "$ID" = "ubuntu" ] || [ "$ID" = "debian" ]; then
  log "Ubuntu/Debian detected. Installing Python3, pip, and Git via apt-get."
  apt-get update -y
  apt-get install -y python3 python3-pip python3-venv git
else
  log "Unrecognized distribution ($ID). Please install Python3, pip, and Git manually."
fi

log "Bootstrap complete. Next steps: clone the repository, create a virtual"
log "environment, install requirements.txt, and start the application."
log "See README.md for the full, distribution-specific walkthrough."

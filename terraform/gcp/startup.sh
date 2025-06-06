#!/bin/bash
set -e

apt-get update
apt-get install -y docker.io docker-compose jq curl

systemctl enable docker
systemctl start docker

# Persistent disk setup
DISK_DEVICE="/dev/disk/by-id/google-airflow-data"
MOUNT_POINT="/mnt/disks/airflow-data"
PGDATA_DIR="$MOUNT_POINT/pgdata"

# Format the disk if it hasn't been formatted
if ! blkid "$DISK_DEVICE" >/dev/null 2>&1; then
  echo "Formatting persistent disk $DISK_DEVICE..."
  mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard "$DISK_DEVICE"
fi

# Mount the disk
mkdir -p "$MOUNT_POINT"
mount -o discard,defaults "$DISK_DEVICE" "$MOUNT_POINT"

# Persist the mount across reboots
grep -q "$DISK_DEVICE" /etc/fstab || echo "$DISK_DEVICE $MOUNT_POINT ext4 defaults,discard 0 2" >> /etc/fstab

# Prepare Postgres data directory
mkdir -p "$PGDATA_DIR"
chown -R 1000:1000 "$PGDATA_DIR"

# Fetch release tag
RELEASE_TAG="${RELEASE_TAG:-latest}"
if [ "$RELEASE_TAG" = "latest" ]; then
  echo "Fetching latest release tag from GitHub..."
  RELEASE_TAG=$(curl -sL https://api.github.com/repos/hydroserver2/hydroserver-airflow-orchestration/releases/latest | jq -r '.tag_name')
fi
STRIPPED_TAG="${RELEASE_TAG#v}"

echo "Deploying with version: $RELEASE_TAG"

# Download source code
cd /opt
curl -sL "https://github.com/hydroserver2/hydroserver-airflow-orchestration/archive/refs/tags/${RELEASE_TAG}.tar.gz" | tar xz
mv "hydroserver-airflow-orchestration-${STRIPPED_TAG}" airflow

# Start Airflow with GCP-specific Docker Compose config
cd airflow
docker-compose -f docker-compose.gcp.yaml up -d

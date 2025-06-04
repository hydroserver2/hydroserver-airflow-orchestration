#!/bin/bash
set -e

apt-get update
apt-get install -y docker.io docker-compose jq curl

systemctl enable docker
systemctl start docker

SECRET_NAME="hs-airflow-${HOSTNAME##*-}-database-url"
PROJECT_ID="$(curl -s -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/project/project-id)"
REGION=$(curl -s -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/zone" \
  | sed 's/.*\/zones\///' | sed 's/-[a-z]$//')

RELEASE_TAG="${RELEASE_TAG:-latest}"
if [ "$RELEASE_TAG" = "latest" ]; then
  echo "Fetching latest release tag from GitHub..."
  RELEASE_TAG=$(curl -sL https://api.github.com/repos/hydroserver2/hydroserver-airflow-orchestration/releases/latest | jq -r '.tag_name')
fi

echo "Deploying with version: $RELEASE_TAG"

cd /opt
curl -sL "https://github.com/hydroserver2/hydroserver-airflow-orchestration/archive/refs/tags/${RELEASE_TAG}.tar.gz" | tar xz
curl -sL "https://github.com/hydroserver2/hydroserverpy/archive/refs/heads/main.tar.gz" | tar xz
mv "hydroserver-airflow-orchestration-${RELEASE_TAG}" airflow
mv "hydroserverpy-main" airflow/hydroserverpy
cd airflow

DB_URL=$(gcloud secrets versions access latest --secret="$SECRET_NAME" --project="$PROJECT_ID")
DB_INSTANCE="${PROJECT_ID}:${REGION}:hs-airflow-${HOSTNAME##*-}"

SQL_ALCHEMY_CONN=$(echo "$DB_URL" | sed 's|^postgresql://|postgresql+psycopg2://|')
CELERY_RESULT_BACKEND=$(echo "$DB_URL" | sed 's|^postgresql://|db+postgresql://|')

cat <<EOF > .env
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=$SQL_ALCHEMY_CONN
AIRFLOW__CELERY__RESULT_BACKEND=$CELERY_RESULT_BACKEND
CLOUD_SQL_INSTANCE_CONNECTION_NAME=$DB_INSTANCE
EOF

docker-compose --env-file .env --profile gcp up -d
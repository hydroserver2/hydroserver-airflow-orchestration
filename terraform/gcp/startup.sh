#!/bin/bash

set -e

apt-get update
apt-get install -y docker.io docker-compose git curl jq

usermod -aG docker "$USER"
systemctl enable docker
systemctl start docker

INSTANCE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/instance-name")
SECRET_NAME="hs-airflow-${INSTANCE}-database-url"
DB_URL=$(gcloud secrets versions access latest --secret="${SECRET_NAME}")

SQL_ALCHEMY_CONN="${DB_URL/postgresql:\/\//postgresql+psycopg2:\/\/}"
RESULT_BACKEND="${DB_URL/postgresql:\/\//db+postgresql:\/\/}"

cd /opt
git clone https://github.com/hydroserver2/hydroserver.git
cd hydroserver

cat <<EOF > .env
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=${SQL_ALCHEMY_CONN}
AIRFLOW__CELERY__RESULT_BACKEND=${RESULT_BACKEND}
CLOUD_SQL_INSTANCE_CONNECTION_NAME=${}
EOF
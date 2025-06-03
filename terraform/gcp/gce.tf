# ---------------------------------
# Google Compute Instance
# ---------------------------------

resource "google_compute_instance" "airflow" {
  name         = "hs-airflow-${var.instance}"
  project      = var.project_id
  zone         = local.zone
  machine_type = "e2-medium"

  boot_disk {
    initialize_params {
      image = "projects/debian-cloud/global/images/family/debian-12"
    }
  }

  network_interface {
    network = "default"
    access_config {}
    subnetwork_project = var.project_id
  }

  metadata_startup_script = <<-EOT
    #!/bin/bash
    set -e

    apt-get update
    apt-get install -y docker.io docker-compose jq curl

    # Ensure Docker is started
    systemctl enable docker
    systemctl start docker

    SECRET_NAME="hs-airflow-\${var.instance}-database-url"
    PROJECT_ID="\${var.project_id}"
    RELEASE_TAG="\${var.release}"

    if [ "\$RELEASE_TAG" = "latest" ]; then
      echo "Fetching latest release tag from GitHub..."
      RELEASE_TAG=\$(curl -sL https://api.github.com/repos/hydroserver2/hydroserver-airflow-orchestration/releases/latest | jq -r '.tag_name')
    fi

    echo "Using release tag: \$RELEASE_TAG"

    # Fetch and extract orchestration system to /opt
    cd /opt
    curl -sL "https://github.com/hydroserver2/hydroserver-airflow-orchestration/archive/refs/tags/\$RELEASE_TAG.tar.gz" | tar xz
    mv "hydroserver-airflow-orchestration-\$RELEASE_TAG" airflow
    cd airflow

    # Fetch DB URL from Secret Manager
    DB_URL=\$(gcloud secrets versions access latest --secret="\$SECRET_NAME" --project="\$PROJECT_ID")
    DB_INSTANCE="hs-airflow-\${var.instance}"

    # Rewrite URLs
    SQL_ALCHEMY_CONN=\$(echo "\$DB_URL" | sed 's|^postgresql://|postgresql+psycopg2://|')
    CELERY_RESULT_BACKEND=\$(echo "\$DB_URL" | sed 's|^postgresql://|db+postgresql://|')

    # Create .env file with no leading whitespace
    cat <<'EOF' > .env
AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=\$SQL_ALCHEMY_CONN
AIRFLOW__CELERY__RESULT_BACKEND=\$CELERY_RESULT_BACKEND
CLOUD_SQL_INSTANCE_CONNECTION_NAME=\$DB_INSTANCE
EOF

    # Start Docker containers
    docker-compose --env-file .env --profile gcp up -d
EOT

  service_account {
    email  = google_service_account.gce_service_account.email
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  labels = {
    (var.label_key) = local.label_value
  }

  metadata = {
    enable-oslogin = "TRUE"
  }

  lifecycle {
    ignore_changes = [machine_type]
  }


  depends_on = [
    google_service_account.gce_service_account,
    google_sql_database_instance.db_instance
  ]
}


# ---------------------------------
# GCP Cloud Run Service Account
# ---------------------------------

resource "google_service_account" "gce_service_account" {
  account_id   = "hs-airflow-${var.instance}"
  display_name = "HydroServer Airflow Orchestration Service Account - ${var.instance}"
  project      = data.google_project.gcp_project.project_id
}

resource "google_project_iam_member" "cloud_run_sql_access" {
  project = data.google_project.gcp_project.project_id
  role   = "roles/cloudsql.client"
  member = "serviceAccount:${google_service_account.gce_service_account.email}"
}

resource "google_secret_manager_secret_iam_member" "secret_access" {
  for_each = {
    "database_url" = google_secret_manager_secret.database_url.id,
  }
  project   = data.google_project.gcp_project.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.gce_service_account.email}"
}

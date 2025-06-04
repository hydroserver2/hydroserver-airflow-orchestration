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

  metadata_startup_script = file("${path.module}/startup.sh")

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

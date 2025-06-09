# ---------------------------------
# Google Compute Instance
# ---------------------------------

resource "google_compute_instance" "airflow" {
  name         = "hs-airflow-${var.instance}"
  project      = var.project_id
  zone         = local.zone
  machine_type = "e2-highmem-2"

  boot_disk {
    initialize_params {
      image = "projects/debian-cloud/global/images/family/debian-12"
    }
  }

  attached_disk {
    source      = google_compute_disk.airflow_data.id
    device_name = "airflow-data"
    mode        = "READ_WRITE"
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

resource "google_project_iam_member" "airflow_disk_access" {
  project      = data.google_project.gcp_project.project_id
  role   = "roles/compute.storageAdmin"
  member = "serviceAccount:${google_service_account.gce_service_account.email}"
}


# ---------------------------------
# Google Compute Disk
# ---------------------------------

resource "google_compute_disk" "airflow_data" {
  name  = "hs-airflow-disk-${var.instance}"
  type  = "pd-balanced"
  zone  = local.zone
  size  = 30
}

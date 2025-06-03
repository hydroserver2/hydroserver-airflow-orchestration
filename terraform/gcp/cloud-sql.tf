# ---------------------------------
# Cloud SQL PostgreSQL Database
# ---------------------------------

resource "google_sql_database_instance" "db_instance" {
  name                = "hs-airflow-${var.instance}"
  database_version    = "POSTGRES_17"
  region              = var.region
  deletion_protection = true
  settings {
    tier = "db-f1-micro"
    availability_type = "REGIONAL"
    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "TRUSTED_CLIENT_CERTIFICATE_REQUIRED"
    }
    password_validation_policy {
      enable_password_policy = true
      min_length             = 12
      complexity             = "COMPLEXITY_DEFAULT"
    }
    database_flags {
      name  = "max_connections"
      value = "100"
    }
    database_flags {
      name  = "log_statement"
      value = "all"
    }
    database_flags {
      name  = "log_duration"
      value = "on"
    }
    database_flags {
      name  = "log_line_prefix"
      value = "%m [%p] %l %u %d %r %a %t %v %c "
    }
    user_labels = {
      "${var.label_key}" = local.label_value
    }
  }

  lifecycle {
    ignore_changes = [
      settings.tier,
      settings.database_flags
    ]
  }
}

resource "google_sql_database" "db" {
  name     = "airflow"
  instance = google_sql_database_instance.db_instance.name
}

resource "random_password" "db_user_password" {
  length           = 15
  upper            = true
  min_upper        = 1
  lower            = true
  min_lower        = 1
  numeric          = true
  min_numeric      = 1
  special          = true
  min_special      = 1
  override_special = "-_~*"
}

resource "random_string" "db_user_password_prefix" {
  length           = 1
  upper            = true
  lower            = true
  numeric          = false
  special          = false
}

resource "google_sql_user" "db_user" {
  name     = "airflow"
  instance = google_sql_database_instance.db_instance.name
  password = "${random_string.db_user_password_prefix.result}${random_password.db_user_password.result}"
}


# ---------------------------------
# Google Secret Manager
# ---------------------------------

resource "google_secret_manager_secret" "database_url" {
  secret_id = "hs-airflow-${var.instance}-database-url"
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  labels = {
    (var.label_key) = local.label_value
  }
}

resource "google_secret_manager_secret_version" "database_url_version" {
  secret      = google_secret_manager_secret.database_url.id
  secret_data = "postgresql://${google_sql_user.db_user.name}:${google_sql_user.db_user.password}@/${google_sql_database.db.name}?host=/cloudsql/${google_sql_database_instance.db_instance.connection_name}"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

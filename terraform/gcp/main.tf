terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
  backend "gcs" {}
  required_version = ">= 1.10.0"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "instance" {
  description = "The name of this HydroServer Airflow instance."
  type        = string
}
variable "release" {
  description = "The HydroServer Airflow release to deploy."
  type        = string
}
variable "project_id" {
  description = "The project ID for this HydroServer Airflow instance."
  type        = string
}
variable "region" {
  description = "The GCP region this HydroServer Airflow instance will be deployed in."
  type        = string
}
variable "hs_airflow_version" {
  description = "The version of HydroServer Airflow to deploy."
  type        = string
  default     = "latest"
}
variable "label_key" {
  description = "The key of the GCP label that will be attached to this HydroServer Airflow instance."
  type        = string
  default     = "hydroserver-instance"
}
variable "label_value" {
  description = "The value of the GCP label that will be attached to this HydroServer Airflow instance."
  type        = string
  default     = ""
}

data "google_compute_zones" "available" {
  region  = var.region
  project = var.project_id
}

locals {
  label_value    = var.label_value != "" ? var.label_value : var.instance
  zone           = data.google_compute_zones.available.names[0]
}

data "google_project" "gcp_project" {
  project_id = var.project_id
}
data "google_client_config" "current" {}

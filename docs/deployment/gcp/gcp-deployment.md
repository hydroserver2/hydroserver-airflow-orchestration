# Deploying HydroServer Airflow Orchestration to Google Cloud Services

This guide walks you through setting up a HydroServer Airflow Orchestration deployment on GCP using Terraform and GitHub Actions.

## Google Cloud Platform Services

The HydroServer Airflow Orchestration tool uses the following GCP services. Compute, memory, and storage resources can be adjusted as needed after deployment using the Google Cloud Console. Use [Google Cloud's pricing calculator](https://cloud.google.com/products/calculator) to generate cost estimates for your deployment.
- **Compute Engine Virtual Machine**: Airflow will be deployed on a GCE VM. The default machine type is `e2-highmem-2` (2 vCPUs, 16 GB Memory).
- **Compute Engine Disk**: Airflow will use a GCE disk to store persistent connection and DAG configurations. The default machine type is `pd-balanced` with 30 GB of storage.
- **IAM Service Accounts**: An IAM service account will be set up to run the Airflow VM.
- **Cloud Storage Bucket**: Terraform will store the Airflow deployment state in a GCP Cloud Storage Bucket.

## Initial Setup

### Set Up GitHub Environment

1. Fork the [hydroserver-airflow-orchestration](https://github.com/hydroserver2/hydroserver-airflow-orchestration) repository, which contains tools for deploying this app to in cloud environments.
2. In your forked repository, go to **Settings** > **Environments**.
3. Create a new environment with a simple alphanumeric name (e.g., `beta`, `prod`, `dev`). This name will be used for GCP services. All environment variables and secrets should be created in this environment.

### Create a GCP Account and Configure IAM Roles and Policies

1. Create a [GCP account](https://cloud.google.com/) if you don't already have one.
2. Follow [these instructions](https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-google-cloud-platform) to configure GitHub's OpenID Connect (OIDC) for your GCP account.
3. Create an IAM service account and role to deploy the application with Terraform. 
4. Configure a trust policy between GCP and **your** forked `hydroserver-airflow-orchestration` repository and user account or organization. 
5. Attach these [IAM permissions](https://github.com/hydroserver2/hydroserver-airflow-orchestration/blob/main/docs/deployment/gcp/gcp-terraform-permissions.md) to the role.
6. Create a Cloud Storage bucket in your GCP project for Terraform to store its state. The bucket must have a globally unique name, default settings, and **must not** be publicly accessible. If you have multiple deployments in the same GCP project, they can share this Terraform bucket.

### Define Environment Variables

1. In your forked repository, go to **Settings** > **Environments**.
2. Add the following GitHub **environment variables**:
   - **`GCP_PROJECT_ID`** – Your GCP project ID.
   - **`GCP_REGION`** – The GCP region for deployment (e.g., `us-west3`).
   - **`GCP_IDENTITY_PROVIDER`** – The GitHub OIDC provider you created in step 2 of `Create a GCP Account and Configure IAM Roles and Policies` (e.g., `projects/your-project-id/locations/global/workloadIdentityPools/your-workload-identity-pool-id/providers/your-workload-identity-provider-id`).
   - **`GCP_SERVICE_ACCOUNT`** – The email of the service account you created in step 2 of `Create a GCP Account and Configure IAM Roles and Policies`.
   - **`TERRAFORM_BUCKET`** – The Cloud Storage bucket name from step 6 of `Create a GCP Account and Configure IAM Roles and Policies`.

### Deploy GCP Services with Terraform

1. In your forked `hydroserver-airflow-orchestration` repository, go to **Actions** > **Workflows** and select **HydroServer Airflow Orchestration System GCP Cloud Deployment**.
2. Run the workflow with:
   - The environment you created.
   - The **"Deploy HydroServer Airflow"** action.
   - (Optional) A specific HydroServer Airflow Orchestration System version if you don't want the latest.
3. The deployment process takes several minutes. Once complete:
   - Install and log in to the [GCP Command Line Interface](https://cloud.google.com/sdk/docs/install).
   - Run the following command to access the Airflow dashboard locally:
     `gcloud compute ssh your-instance-name --zone=your-instance-zone -- -L 8080:0.0.0.0:8080 -C -N`
   - In a browser, visit the Airflow admin dashboard at `http://localhost:8080`.
     - Note: Airflow will take several minutes to finish setting up after GCP shows the VM is running successfully. You may need to wait for the dashboard to become available.

### Configure Airflow

1. Log in to the HydroServer admin dashboard using the following credentials:  
   - **Username:** `airflow`
   - **Password:** `airflow`
2. Go to **Admin** > **Connections** and click "Add a new record". Fill out the following fields to register your Airflow deployment with a HydroServer instance:
   - **Connection Id**: Enter an ID that will be used internally by Airflow to associate DAGs with this connection.
   - **Connection Type**: Select "HTTP".
   - **Host**: The host of the HydroServer instance Airflow will connect to (e.g. "playground.hydroserver.org").
   - **Schema**: The URL schema of the HydroServer instance Airflow will connect to (e.g. "https").
   - **Login**: Your HydroServer account email (unless using an API key).
   - **Password**: Your HydroServer account password (unless using an API key).
   - **Extra**: A JSON object containing the workspace name Airflow will be associated with, the name of the Airflow instance, and an API key (if not using username/password):
   ```json
   {
     "workspace_name": "My Workspace",
     "orchestration_system_name": "My Airflow Instance",
     "api_key": "*****"
   }
   ```
3. Go to **DAGs** and look for a `sync` DAG. Ensure this DAG is un-paused and wait for it to run or run it manually.
4. In another tab, log in to HydroServer and go to **Data Management** > **Job Orchestration**. You should see you Airflow instance registered under Orchestration systems and you can now add data sources for it to load.

## Tearing Down HydroServer Airflow Orchestration System

To delete your HydroServer Airflow Orchestration System deployment:

1. In your `hydroserver-airflow-orchestration` repository, go to **Actions** > **Workflows** > **HydroServer GCP Cloud Deployment**.
2. Run the workflow with:
   - The environment of the instance.
   - The **"Teardown HydroServer Airflow"** action.

import json
import os
from airflow.hooks.base import BaseHook
from airflow.utils.dates import days_ago
from airflow.decorators import dag, task
from datetime import timedelta
from utils.hydroserver_airflow_connection import HydroServerAirflowConnection


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}


@dag(
    dag_id="orchestration_sync",
    default_args=default_args,
    start_date=days_ago(1),
    schedule_interval=timedelta(minutes=5),
    catchup=False,
    tags=["hydroserver", "monitoring"],
)
def orchestration_sync():
    """
    ### Orchestration Sync
    This DAG will
    1. Connect to HydroServer via hydroserverpy
    2. Register the Airflow connections as HydroServer orchestration systems if not already registered
    3. Fetch associated data sources and save them in the dags/ directory
    4. TODO: Compare new datasources to existing files so we don't regenerate DAGs more than we need to

    Expects an Airflow connection with the following extras:
    {
    "workspace_name": "Daniel's Workspace",
    "orchestration_system_name": "Daniel's Airflow Instance"
    }
    """

    @task()
    def sync_hydroserver_orchestration():
        # TODO: loop through connections and create an orchestrator for each
        hs_connection = HydroServerAirflowConnection(
            "local_hydroserver_for_daniels_workspace"
        )
        hs_connection.save_datasources_to_file()

    sync_hydroserver_orchestration()


orchestration_sync_dag = orchestration_sync()

# TODO: Sync paused state: compare Airflow DAG pause to HydroServer
# Maybe add a flag that determines if the user pushed pause from the airflow UI.
# That way we overwrite the paused state only when they've interacted with the UI as opposed to whenever there's a change

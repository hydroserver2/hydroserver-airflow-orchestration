import re
from airflow.utils.dates import days_ago
from airflow.decorators import dag, task
from datetime import timedelta
from utils.hydroserver_airflow_connection import HydroServerAirflowConnection
from airflow import settings
from airflow.models import Connection

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}


def sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


def create_sync_dag(conn_id: str, orchestration_system_name: str, workspace_name: str):
    system_name = sanitize(orchestration_system_name)
    workspace_name = sanitize(workspace_name)
    dag_id = f"sync__{system_name}"

    @dag(
        dag_id=dag_id,
        default_args=default_args,
        start_date=days_ago(1),
        schedule_interval=timedelta(minutes=5),
        catchup=False,
        tags=["sync", f"{system_name}", f"{workspace_name}"],
    )
    def _sync():
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
            hs = HydroServerAirflowConnection(conn_id)
            hs.save_datasources_to_file()

        sync_hydroserver_orchestration()

    return _sync()


session = settings.Session()
for conn in session.query(Connection).all():
    extras = conn.extra_dejson or {}
    name = extras.get("orchestration_system_name")
    workspace_name = extras.get("workspace_name")
    if name:
        new_dag = create_sync_dag(conn.conn_id, name, workspace_name)
        globals()[new_dag.dag_id] = new_dag

# TODO: Sync paused state: compare Airflow DAG pause to HydroServer
# Maybe add a flag that determines if the user pushed pause from the airflow UI.
# That way we overwrite the paused state only when they've interacted with the UI as opposed to whenever there's a change

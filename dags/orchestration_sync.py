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


def create_sync_dag(conn_id: str, system_name: str, workspace_name: str):
    @dag(
        dag_id=f"sync__{system_name}",
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
        3. TODO: Compare new datasources to existing files so we don't regenerate DAGs more than we need to
        """

        @task()
        def sync_hydroserver_orchestration():
            # TODO: This file is mostly just registering orchestration systems now that the generate_dag file
            # pulls datasources fresh each run. Consider consolidating the files.
            # TODO: Probably we want to move orchestration system registration to the datasource model
            # so hydroserverpy users can register their own custom orchestrators easily.
            hs = HydroServerAirflowConnection(conn_id)

        sync_hydroserver_orchestration()

    return _sync()


session = settings.Session()
for conn in session.query(Connection).all():
    extras = conn.extra_dejson or {}
    name = sanitize(extras.get("orchestration_system_name"))
    workspace_name = sanitize(extras.get("workspace_name"))
    if name:
        try:
            new_dag = create_sync_dag(conn.conn_id, name, workspace_name)
            globals()[new_dag.dag_id] = new_dag
        except:
            # Prevent one bad connection from taking down all the connections
            continue

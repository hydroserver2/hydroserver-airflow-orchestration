import json
import os
import uuid
from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.utils.dates import days_ago
from airflow.decorators import dag, task
from datetime import timedelta
import hydroserverpy
import logging


class HydroServerOrchestrator:
    """
    Scheduler class to ensure orchestration system exists,
    fetch datasources, and generate/update Airflow DAGs for each.
    """

    def __init__(self, conn_id: str):
        self.OUTPUT_DIR = "/opt/airflow/dags/datasources"
        self.airflow_connection = BaseHook.get_connection(conn_id)
        self.api = self.connect_to_hydroserver()
        self.orchestration_system = self.get_or_create_orchestration_system()
        self.data_sources = self.get_datasources()
        self.save_datasources_to_file()

    def connect_to_hydroserver(self):
        """Uses connection settings to register app on HydroServer"""

        conn = self.airflow_connection
        scheme = conn.conn_type or "http"
        host = conn.host
        port = f":{conn.port}" if conn.port else ""
        base = f"{scheme}://{host}{port}".rstrip("/")

        try:
            return hydroserverpy.HydroServer(
                host=base,
                email=conn.login,
                password=conn.password,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to connect to HydroServer: {e}")

    def get_or_create_orchestration_system(self):
        extras = self.airflow_connection.extra_dejson
        workspace_name = extras.get("workspace_name")
        orchestration_name = extras.get("orchestration_system_name")

        workspaces = self.api.workspaces.list(associated_only=True)
        workspace = next(
            (w for w in workspaces if str(w.name) == str(workspace_name)), None
        )
        if not workspace:
            raise RuntimeError(f"Workspace {workspace_name!r} not found")

        orchestration_systems = self.api.orchestrationsystems.list(workspace=workspace)
        orchestration_system = next(
            (o for o in orchestration_systems if o.name == orchestration_name),
            None,
        )

        if not orchestration_system:
            try:
                orchestration_system = self.api.orchestrationsystems.create(
                    name=orchestration_name,
                    workspace=workspace,
                    orchestration_system_type="ETL",
                )
            except Exception as e:
                raise RuntimeError("Failed to register Airflow orchestration system.")

        return orchestration_system

    def get_datasources(self):
        return self.api.datasources.list(orchestration_system=self.orchestration_system)

    def save_datasources_to_file(self):
        uid = str(self.orchestration_system.uid)
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        path = os.path.join(self.OUTPUT_DIR, f"{uid}.json")
        try:
            with open(path, "w") as f:
                json.dump(
                    [self._stringify_uuids(ds.dict()) for ds in self.data_sources],
                    f,
                    indent=2,
                )
            logging.info(f"Saved {len(self.data_sources)} datasources to {path}")
        except Exception as e:
            logging.error(f"Failed to write datasource file {path}: {e}")
            raise

    @staticmethod
    def _stringify_uuids(obj):
        if isinstance(obj, dict):
            return {
                k: HydroServerOrchestrator._stringify_uuids(v) for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [HydroServerOrchestrator._stringify_uuids(i) for i in obj]
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        else:
            return obj


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
        orchestrator = HydroServerOrchestrator(
            "local_hydroserver_for_daniels_workspace"
        )

    sync_hydroserver_orchestration()


orchestration_sync_dag = orchestration_sync()

# TODO: Sync paused state: compare Airflow DAG pause to HydroServer
# Maybe add a flag that determines if the user pushed pause from the airflow UI.
# That way we overwrite the paused state only when they've interacted with the UI as opposed to whenever there's a change

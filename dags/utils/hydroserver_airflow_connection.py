import json
import os
import uuid
from airflow.hooks.base import BaseHook
import hydroserverpy
import logging
from utils.global_variables import OUTPUT_DIR


class HydroServerAirflowConnection:
    """
    Scheduler class to ensure orchestration system exists,
    fetch datasources, and generate/update Airflow DAGs for each.
    """

    def __init__(self, conn_id: str):
        self.airflow_connection = BaseHook.get_connection(conn_id)
        self.api = self.connect_to_hydroserver()
        self.orchestration_system = self.get_or_create_orchestration_system()
        self.data_sources = self.get_datasources()

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
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        path = os.path.join(OUTPUT_DIR, f"{uid}.json")
        try:
            with open(path, "w") as f:
                json.dump(
                    [stringify_uuids(ds.dict()) for ds in self.data_sources],
                    f,
                    indent=2,
                )
            logging.info(f"Saved {len(self.data_sources)} datasources to {path}")
        except Exception as e:
            logging.error(f"Failed to write datasource file {path}: {e}")
            raise


def stringify_uuids(obj):
    if isinstance(obj, dict):
        return {k: stringify_uuids(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [stringify_uuids(i) for i in obj]
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    else:
        return obj

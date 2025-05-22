from datetime import datetime
import json
from pathlib import Path
import uuid
from airflow.hooks.base import BaseHook
import hydroserverpy
import logging
from utils.global_variables import OUTPUT_DIR
from functools import cached_property


class HydroServerAirflowConnection:
    """
    Scheduler class to ensure orchestration system exists,
    fetch datasources, and generate/update Airflow DAGs for each.
    """

    def __init__(self, conn_id: str):
        self.conn_id = conn_id

    @cached_property
    def extras(self):
        conn = BaseHook.get_connection(self.conn_id)
        return conn.extra_dejson

    @cached_property
    def workspace_name(self):
        return str(self.extras["workspace_name"])

    @cached_property
    def api(self):
        """Lazily connect the HydroServer API client."""
        extras = self.extras
        conn = BaseHook.get_connection(self.conn_id)

        scheme = conn.conn_type or "http"
        host = conn.host
        port = f":{conn.port}" if conn.port else ""
        base = f"{scheme}://{host}{port}".rstrip("/")

        if key := extras.get("api_key"):
            logging.info("Authenticating via API key")
            return hydroserverpy.HydroServer(host=base, apikey=key)

        if conn.login and conn.password:
            logging.info("Authenticating via username and password")
            return hydroserverpy.HydroServer(
                host=base, email=conn.login, password=conn.password
            )

        raise RuntimeError("No valid authentication found (login/password or API key).")

    @cached_property
    def orchestration_system(self):
        system_name = str(self.extras["orchestration_system_name"])
        ws_list = self.api.workspaces.list(associated_only=True)
        ws = next((w for w in ws_list if str(w.name) == self.workspace_name), None)
        if not ws:
            raise RuntimeError(f"Workspace {self.workspace_name} not found")

        os_list = self.api.orchestrationsystems.list(workspace=ws)
        orchestration_system = next((o for o in os_list if o.name == system_name), None)

        if orchestration_system:
            logging.info(f"Found orchestration system {system_name}")
        else:
            logging.info(
                f"API couldn't find orchestration system {system_name}. Registering name..."
            )
            orchestration_system = self.api.orchestrationsystems.create(
                name=system_name,
                workspace=ws,
                orchestration_system_type="airflow",
            )
        return orchestration_system

    @cached_property
    def data_sources(self):
        return list(
            self.api.datasources.list(orchestration_system=self.orchestration_system)
        )

    def save_data_sources_to_file(self):
        uid = self.orchestration_system.uid
        path = Path(OUTPUT_DIR) / f"{uid}.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        def clean(obj):
            if isinstance(obj, dict):
                return {k: clean(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [clean(v) for v in obj]
            if isinstance(obj, uuid.UUID):
                return str(obj)
            if isinstance(obj, datetime):
                return obj.isoformat()
            return obj

        try:
            with open(path, "w") as f:
                raw = [ds.dict() for ds in self.data_sources]
                cleaned = [clean(ds) for ds in raw]
                json.dump(cleaned, f, indent=2)
            logging.info(f"Saved {len(self.data_sources)} datasources to {path}")
        except Exception as e:
            logging.error(f"Failed to write datasource file {path}: {e}")
            raise

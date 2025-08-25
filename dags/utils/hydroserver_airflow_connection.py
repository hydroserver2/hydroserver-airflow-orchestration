from functools import cached_property
from airflow.hooks.base import BaseHook
import logging
from hydroserverpy import HydroServer


class HydroServerAirflowConnection(HydroServer):
    """HydroServer client driven by an Airflow connection.

    The Airflow connection should contain:
      • host / schema / port (standard fields)
      • login + password *or* extras.api_key
      • (optional) extras.workspace_name for convenience helpers downstream
    """

    def __init__(self, conn_id: str):
        conn = BaseHook.get_connection(conn_id)
        self.extras = conn.extra_dejson or {}
        self.conn_id = conn_id

        # Build base URL
        scheme = conn.schema or "http"
        port = f":{conn.port}" if conn.port else ""
        host = f"{scheme}://{conn.host}{port}".rstrip("/")

        # Select auth style (prefer API key).
        if api_key := self.extras.get("api_key"):
            logging.info("Authenticating via API key")
            super().__init__(host=host, apikey=api_key)
        elif conn.login and conn.password:
            super().__init__(host=host, email=conn.login, password=conn.password)
        else:
            raise RuntimeError(
                f"No api_key or login/password in Airflow connection {conn_id!r}"
            )

    @cached_property
    def workspace(self):
        """Workspace object looked up by extras.workspace_name."""
        ws_name: str | None = self.extras.get("workspace_name")
        if ws_name is None:
            raise RuntimeError(
                "`workspace_name` missing from Airflow connection extras"
            )
        workspaces = self.workspaces.list(is_associated=True, fetch_all=True).items
        ws = next(
            (w for w in workspaces if str(w.name) == ws_name),
            None,
        )
        if ws is None:
            raise RuntimeError(
                f"Workspace {ws_name!r} specified in Airflow Connection not found in HydroServer"
            )
        return ws

    @cached_property
    def orchestration_system(self):
        """Return the orchestration-system object, or None if it’s absent.

        The name is taken from extras.orchestration_system_name.  A missing
        name or a name that is not found simply yields `None`; your DAG-
        generation code can create it if needed.
        """
        os_name: str | None = self.extras.get("orchestration_system_name")
        if not os_name:
            return None

        os_obj = next(
            (
                o
                for o in self.orchestrationsystems.list(
                    workspace=self.workspace, fetch_all=True
                ).items
                if str(o.name) == os_name
            ),
            None,
        )
        return os_obj

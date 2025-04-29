from airflow import DAG
from airflow.hooks.base import BaseHook
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from datetime import timedelta
import hydroserverpy
import logging


def monitor_and_register(**ctx):
    """
    Expects an Airflow connection with the following extras:
    {
    "workspace_name": "Daniel's Workspace",
    "orchestration_system_name": "Daniel's Airflow Instance"
    }
    """
    conn = BaseHook.get_connection("local_hydroserver_for_daniels_workspace")
    scheme = conn.conn_type or "http"
    host = conn.host
    port = f":{conn.port}" if conn.port else ""
    base = f"{scheme}://{host}{port}".rstrip("/")
    conn = BaseHook.get_connection("local_hydroserver_for_daniels_workspace")

    try:
        api = hydroserverpy.HydroServer(
            host=base,
            email=conn.login,
            password=conn.password,
        )
    except Exception as e:
        raise RuntimeError(f"Failed to connect to HydroServer: {e}")

    extras = conn.extra_dejson
    workspace_name = extras.get("workspace_name")
    orchestration_name = extras.get("orchestration_system_name")

    workspaces = api.workspaces.list(associated_only=True)
    workspace = next(
        (w for w in workspaces if str(w.name) == str(workspace_name)), None
    )
    if not workspace:
        raise RuntimeError(f"Workspace {workspace_name!r} not found")

    orchestration_systems = api.orchestrationsystems.list(workspace=workspace)
    orchestration_system = next(
        (o for o in orchestration_systems if o.name == orchestration_name),
        None,
    )

    if not orchestration_system:
        try:
            orchestration_system = api.orchestrationsystems.create(
                name=orchestration_name,
                workspace=workspace,
                orchestration_system_type="ETL",
            )
        except Exception as e:
            raise RuntimeError("Failed to register Airflow orchestration system.")

    datasources = api.datasources.list(orchestration_system=orchestration_system)
    print(f"datasource {datasources}")


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="hydroserver_monitor",
    default_args=default_args,
    start_date=days_ago(1),
    schedule_interval=timedelta(minutes=5),
    catchup=False,
    tags=["hydroserver", "monitoring"],
) as dag:

    monitor_task = PythonOperator(
        task_id="monitor_and_register",
        python_callable=monitor_and_register,
        provide_context=True,
    )

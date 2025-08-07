from datetime import timedelta, datetime, timezone
import logging
import re

from airflow import settings
from airflow.utils.dates import days_ago
from airflow.decorators import dag, task
from utils.hydroserver_airflow_connection import HydroServerAirflowConnection
from airflow.models import Connection, DagModel
from hydroserverpy.api.models.etl.data_source import DataSource


def sanitize_name(name: str) -> str:
    """
    Airflow IDs require alphanumeric or -_ characters only in ids.
    """
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 0,
    # "retry_delay": timedelta(minutes=1),
}


def generate_dag(data_source: DataSource, hs):
    system_name = sanitize_name(hs.orchestration_system.name)
    workspace_name = sanitize_name(hs.workspace.name)
    ds_name = sanitize_name(data_source.name)
    dag_id = f"{ds_name}"

    @task()
    def etl_task(payload_name: str):
        data_source.load_data(payload_name)

    schedule = data_source.schedule

    start_dt = (
        datetime.fromisoformat(st) if (st := schedule.start_time) else days_ago(1)
    )
    end_dt = datetime.fromisoformat(et) if (et := schedule.end_time) else None

    schedule_str = schedule.crontab or timedelta(
        **{schedule.interval_units: schedule.interval}
    )

    @dag(
        dag_id=dag_id,
        default_args=default_args,
        start_date=start_dt,
        end_date=end_dt,
        max_active_runs=1,
        schedule=schedule_str,
        catchup=False,
        tags=["etl", f"{system_name}", f"{workspace_name}"],
        params={"conn_id": hs.conn_id, "datasource_id": data_source.uid},
        is_paused_upon_creation=bool(data_source.status.paused),
    )
    def dag_factory():
        for payload in data_source.settings.payloads:
            task_id = f"{sanitize_name(payload.name)}"
            etl_task.override(task_id=task_id)(payload_name=payload.name)

    return dag_factory()


session = settings.Session()
hs_conns = session.query(Connection).all()

for conn in hs_conns:
    hs = HydroServerAirflowConnection(conn.conn_id)
    if hs.orchestration_system is None:
        logging.info(f"Found new orchestration system {system_name}. Registering...")
        system_name = str(hs.extras["orchestration_system_name"])
        hs.orchestrationsystems.create(
            name=system_name,
            workspace=hs.workspace,
            orchestration_system_type="airflow",
        )
        logging.info(f"orchestration system {system_name} successfully Registered.")
        continue  # If the orchestration system is new, theres's definitely no datastreams

    data_sources = hs.datasources.list(
        orchestration_system=hs.orchestration_system, fetch_all=True
    ).items

    if not data_sources:
        logging.warning(f"No datasources found for this orchestration system.")
        continue

    for data_source in data_sources:
        logging.info(f"Generating DAG for datasource {data_source}")
        new_dag = generate_dag(data_source, hs)

        # HydroServer's datasource.status.paused is the source of truth. Update current Airflow paused state
        # to match if the user has since changed the state somewhere else.
        dag_model = (
            settings.Session()
            .query(DagModel)
            .filter(DagModel.dag_id == new_dag.dag_id)
            .first()
        )
        desired_paused = bool(data_source.status.paused)
        if dag_model and dag_model.is_paused != desired_paused:
            dag_model.set_is_paused(desired_paused)

        globals()[new_dag.dag_id] = new_dag

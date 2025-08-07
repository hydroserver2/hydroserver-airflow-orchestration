from datetime import timedelta, datetime, timezone
import json
import logging
import os
import re

from airflow import settings
from utils.global_variables import OUTPUT_DIR
from airflow.utils.dates import days_ago
from airflow.decorators import dag, task
from utils.hydroserver_airflow_connection import HydroServerAirflowConnection
from airflow.models import Connection, DagModel
from hydroserverpy.api.models.etl.data_source import DataSource


def read_datasources_from_file(uid):
    path = os.path.join(OUTPUT_DIR, f"{uid}.json")
    if not os.path.isfile(path):
        logging.warning(f"Orchestration system file not found: {path}")
        return None

    try:
        with open(path, "r") as f:
            datasources = json.load(f)

        return datasources
    except Exception as e:
        logging.error(f"Failed to write datasource file {path}: {e}")
        raise


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


def generate_dag(data_source: DataSource, hs_connection):
    system_name = sanitize_name(hs_connection.orchestration_system.name)
    workspace_name = sanitize_name(hs_connection.workspace_name)
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
        params={"conn_id": hs_connection.conn_id, "datasource_id": data_source.uid},
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
    conn_id = conn.conn_id
    hs_connection = HydroServerAirflowConnection(conn_id)
    uid = str(hs_connection.orchestration_system.uid)

    data_sources = hs_connection.api.datasources.list(
        orchestration_system=uid, fetch_all=True
    ).items

    if not data_sources:
        logging.warning(f"No datasources found for this orchestration system.")
        continue

    for data_source in data_sources:
        logging.info(f"datasource {data_source}")
        new_dag = generate_dag(data_source, hs_connection)

        # HydroServer's datasource.paused is the source of truth. Update current Airflow paused state
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

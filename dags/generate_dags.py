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
from utils.get_etl_classes import get_extractor, get_transformer, get_loader
from airflow.models import Connection, DagModel


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


@task()
def extract_transform_load(data_source: dict, payload: dict, conn_id: str):
    import pandas as pd
    import croniter

    settings = data_source["settings"]
    extractor = get_extractor(settings["extractor"])
    transformer = get_transformer(settings["transformer"])
    loader = get_loader(settings["loader"], conn_id)

    def _next_run() -> str | None:
        now = datetime.now(timezone.utc)
        if data_source.get("crontab"):
            return (
                croniter.croniter(data_source["crontab"], now)
                .get_next(datetime)
                .isoformat()
            )
        if interval := data_source.get("interval"):
            unit = data_source.get("interval_units", "minutes")
            return (now + timedelta(**{unit: interval})).isoformat()
        return None

    def _update_status(success: bool, msg: str):
        short_message = msg if len(msg) <= 255 else msg[:252] + "…"
        loader.datasources.update(
            uid=data_source["uid"],
            last_run=datetime.now(timezone.utc).isoformat(),
            last_run_successful=success,
            last_run_message=short_message,
            next_run=_next_run(),
        )

    try:
        logging.info(f"Started extract")
        extracted_data = extractor.extract(payload, loader)
        if extracted_data is None or (
            isinstance(extracted_data, pd.DataFrame) and extracted_data.empty
        ):
            _update_status(True, "No data returned from the extractor")
            return
        logging.info(f"Extract completed")

        logging.info(f"Started transform")
        transformed_data = transformer.transform(extracted_data, payload["mappings"])
        if transformed_data is None or (
            isinstance(transformed_data, pd.DataFrame) and transformed_data.empty
        ):
            _update_status(True, "No data returned from the transformer")
            return
        logging.info(f"Transform completed")

        logging.info(f"Started load")
        loader.load(transformed_data, payload)
        logging.info("load completed")
        _update_status(True, "OK")
    except Exception as err:
        _update_status(False, str(err))


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 0,
    # "retry_delay": timedelta(minutes=1),
}


def generate_dag(data_source, hs_connection):
    system_name = sanitize_name(hs_connection.orchestration_system.name)
    workspace_name = sanitize_name(hs_connection.workspace_name)
    ds_name = sanitize_name(data_source["name"])
    dag_id = f"{ds_name}"

    cron = data_source.get("crontab")
    if cron:
        schedule = cron
    else:
        interval = data_source.get("interval", 1)
        unit = data_source.get("interval_units", "minutes")
        schedule = timedelta(**{unit: interval})

    start_ts = data_source.get("start_time")
    start_dt = datetime.fromisoformat(start_ts) if start_ts else days_ago(1)

    end_ts = data_source.get("end_time")
    end_dt = datetime.fromisoformat(end_ts) if end_ts else None

    is_paused = bool(data_source.get("paused", False))

    @dag(
        dag_id=dag_id,
        default_args=default_args,
        start_date=start_dt,
        end_date=end_dt,
        max_active_runs=1,
        schedule=schedule,
        catchup=False,
        tags=["etl", f"{system_name}", f"{workspace_name}"],
        params={"conn_id": hs_connection.conn_id, "datasource_id": data_source["uid"]},
        is_paused_upon_creation=is_paused,
    )
    def run_etl():
        for payload in data_source["settings"]["payloads"]:
            task_id = f"{sanitize_name(payload['name'])}"
            extract_transform_load.override(task_id=task_id)(
                data_source=data_source,
                payload=payload,
                conn_id=hs_connection.conn_id,
            )

    return run_etl()


session = settings.Session()
hs_conns = session.query(Connection).all()

for conn in hs_conns:
    conn_id = conn.conn_id
    hs_connection = HydroServerAirflowConnection(conn_id)
    uid = str(hs_connection.orchestration_system.uid)
    datasources = read_datasources_from_file(uid)

    if not datasources:
        logging.warning(f"No datasources found for this orchestration system.")
        continue

    for data_source in datasources:
        new_dag = generate_dag(data_source, hs_connection)

        # HydroServer's datasource.paused is the source of truth. Update current Airflow paused state
        # to match if the user has since changed the state somewhere else.
        dag_model = (
            settings.Session()
            .query(DagModel)
            .filter(DagModel.dag_id == new_dag.dag_id)
            .first()
        )
        desired_paused = bool(data_source.get("paused", False))
        if dag_model and dag_model.is_paused != desired_paused:
            dag_model.set_is_paused(desired_paused)

        globals()[new_dag.dag_id] = new_dag

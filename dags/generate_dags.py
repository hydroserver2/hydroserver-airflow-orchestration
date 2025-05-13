from datetime import timedelta, datetime, timezone
import json
import logging
import os
import re

from hydroserverpy import HydroServer
from airflow import settings
from utils.global_variables import OUTPUT_DIR
from airflow.utils.dates import days_ago
from airflow.decorators import dag, task
from utils.hydroserver_airflow_connection import HydroServerAirflowConnection
from utils.get_etl_classes import get_extractor, get_transformer, get_loader
from airflow.utils.task_group import TaskGroup
from hydroserverpy.etl import HydroServerLoader
from airflow.hooks.base import BaseHook
from airflow.models import Connection


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


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}


def sanitize_name(name: str) -> str:
    """
    Airflow IDs require alphanumeric or -_ characters only in ids.
    """
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


def generate_dag(data_source, conn_id):

    dag_id = f"datasource_{sanitize_name(data_source['name'])}"

    # TODO: schedule
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
        schedule_interval=schedule,
        catchup=False,
        tags=["hydroserver", "monitoring"],
        is_paused_upon_creation=is_paused,
    )
    def run_etl():
        import pandas as pd

        settings = data_source["settings"]

        extractor_settings = settings["extractor"]
        extractor = get_extractor(extractor_settings)

        transformer_settings = settings["transformer"]
        transformer = get_transformer(transformer_settings)

        loader_settings = settings["loader"]
        if loader_settings["type"] == "HydroServer":
            conn = BaseHook.get_connection(conn_id)
            scheme = conn.conn_type or "http"
            host = conn.host
            port = f":{conn.port}" if conn.port else ""
            base = f"{scheme}://{host}{port}".rstrip("/")
            loader = HydroServerLoader(
                host=base, email=conn.login, password=conn.password
            )
        # loader = get_loader(loader_settings)

        payloads = settings["payloads"]

        @task()
        def get_data_requirements(payload):
            return loader.get_data_requirements(payload["mappings"])

        @task()
        def prepare_extractor_params(data_requirements):
            extractor.prepare_params(data_requirements)

        @task(multiple_outputs=True)
        def extract_transform_load(payload):
            try:
                extracted_data = extractor.extract()
                if extracted_data is None or (
                    isinstance(extracted_data, pd.DataFrame) and extracted_data.empty
                ):
                    logging.warning(
                        f"No data was returned from the extractor. Ending ETL run."
                    )
                    return
                else:
                    logging.info(f"Extract completed.")

                logging.info(f"starting transformation for {settings}")
                transformed_data = transformer.transform(
                    extracted_data, payload["mappings"]
                )
                if transformed_data is None or (
                    isinstance(transformed_data, pd.DataFrame)
                    and transformed_data.empty
                ):
                    logging.warning(
                        f"No data returned from the transformer. Ending run."
                    )
                    return
                else:
                    logging.info(f"Transform completed.")

                loader.load(transformed_data, payload)
                logging.info("load completed.")
                return {"success": True, "message": "OK"}
            except Exception as err:
                return {"success": False, "message": str(err)}

        @task()
        def update_data_source_status(success: bool, message: str):
            import croniter

            # 1) reconnect to HydroServer
            conn = BaseHook.get_connection(conn_id)
            scheme = conn.conn_type or "http"
            host = conn.host
            port = f":{conn.port}" if conn.port else ""
            base = f"{scheme}://{host}{port}".rstrip("/")
            service = HydroServer(host=base, email=conn.login, password=conn.password)

            # 2) compute next_run exactly like HydroServerETLCSV._update_data_source
            if data_source.get("crontab"):
                next_run = croniter.croniter(
                    data_source["crontab"], datetime.now(timezone.utc)
                ).get_next(datetime)
            elif data_source.get("interval") and data_source.get("interval_units"):
                next_run = datetime.now(timezone.utc) + timedelta(
                    **{data_source["interval_units"]: data_source["interval"]}
                )
            else:
                next_run = None

            # 3) push the update
            short_msg = ""
            if message:
                short_msg = message if len(message) <= 255 else message[:252] + "..."
            service.datasources.update(
                uid=data_source["uid"],
                last_run=datetime.now(timezone.utc).isoformat(),
                last_run_successful=success,
                last_run_message=short_msg,
                next_run=next_run.isoformat() if next_run else None,
            )

        # @task()
        # def transform(extracted_data):
        #     logging.info(f"transformed {extracted_data}")
        #     return f"transformed {extracted_data}"

        # @task()
        # def load(transformed_data, payload_settings):
        #     # TODO: I think the transformer should just create a pandas dataframe with the datastream IDs so the loader shouldn't need payload_settings
        #     loader.load(transformed_data, payload_settings)
        #     logging.info("data is loaded!")
        #     return f"loader.load({transformed_data}, {payload_settings})"

        for payload in payloads:
            payload_name_safe = sanitize_name(payload["name"])
            with TaskGroup(group_id=f"{payload_name_safe}") as etl_group:
                get_requirements = get_data_requirements.override(
                    task_id=f"get_data_requirements"
                )(payload)
                prep = prepare_extractor_params.override(
                    task_id=f"prepare_extractor_params"
                )(get_requirements)
                # ext = extract.override(task_id=f"extract")()
                # trans = transform.override(task_id=f"transform")(ext)
                # load_task = load.override(task_id=f"load")(trans, payload)
                etl = extract_transform_load.override(
                    task_id=f"extract_transform_load"
                )(payload)
                status = update_data_source_status.override(
                    task_id=f"update_data_source_status"
                )(etl["success"], etl["message"])

                # get_reqs >> prep >> ext >> trans >> load_task
                get_requirements >> prep >> etl >> status
        # 4. (Not here) update hydroserverpy functions to use the parameter format defined above.

    return run_etl()


session = settings.Session()
hs_conns = session.query(Connection).all()

for conn in hs_conns:
    conn_id = conn.conn_id
    hs_connection = HydroServerAirflowConnection(conn_id)
    uid = str(hs_connection.orchestration_system.uid)
    datasources = read_datasources_from_file(uid)
    logging.info(f"RAW FROM FILE: {repr(datasources)}")

    if not datasources:
        logging.warning(f"No datasources found for this orchestration system.")
        continue

    for datasource in datasources:
        new_dag = generate_dag(datasource, conn_id)
        globals()[new_dag.dag_id] = new_dag

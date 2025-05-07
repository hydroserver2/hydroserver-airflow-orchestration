import json
import logging
import os
import re

from utils.global_variables import OUTPUT_DIR
from airflow.utils.dates import days_ago
from airflow.decorators import dag, task
from datetime import timedelta
from utils.hydroserver_airflow_connection import HydroServerAirflowConnection
from utils.get_etl_classes import get_extractor, get_transformer, get_loader
from airflow.utils.task_group import TaskGroup


def read_datasources_from_file(uid):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{uid}.json")
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
    # Replace any non-alphanumeric, non-dash/underscore/dot with underscore
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)


def generate_dag(data_source):
    dag_id = f"datasource_{sanitize_name(data_source['name'])}"

    @dag(
        dag_id=dag_id,
        default_args=default_args,
        start_date=days_ago(1),
        schedule_interval=timedelta(minutes=5),
        catchup=False,
        tags=["hydroserver", "monitoring"],
    )
    def run_etl():
        import pandas as pd

        print(f"Starting run_etl for datasource: {data_source['name']}")
        # settings = data_source["settings"]

        # extractor_settings = settings["extractor"]
        # extractor = get_extractor(extractor_settings)

        # transformer_settings = settings["transformer"]
        # transformer = get_transformer(transformer_settings)

        # loader_settings = settings["loader"]
        # loader = get_loader(loader_settings)

        # payloads = settings["payloads"]

        @task()
        def get_data_requirements(payload):
            # return loader.get_data_requirements(payload)
            return "loader.get_data_requirements(payload)"

        @task()
        def prepare_extractor_params(data_requirements):
            # extractor.prepare_params(data_requirements)
            return "extractor.prepare_params(data_requirements)"

        @task()
        def extract():
            return "extracted"
            # data = extractor.extract()
            # if data is None or (isinstance(data, pd.DataFrame) and data.empty):
            #     logging.warning(
            #         f"No data was returned from the extractor. Ending ETL run."
            #     )
            #     return
            # else:
            #     logging.info(f"Successfully extracted data.")
            #     return data

        @task()
        def transform(extracted_data):
            return f"transformed {extracted_data}"
            # data = transformer.transform(extracted_data)
            # if data is None or (isinstance(data, pd.DataFrame) and data.empty):
            #     logging.warning(f"No data returned from the transformer. Ending run.")
            #     return
            # else:
            #     logging.info(f"Successfully transformed data. {data}")
            #     return data

        @task()
        def load(transformed_data, payload_settings):
            # TODO: I think the transformer should just create a pandas dataframe with the datastream IDs so the loader shouldn't need payload_settings
            # loader.load(transformed_data, payload_settings)
            logging.info("data is loaded!")
            return f"loader.load({transformed_data}, {payload_settings})"

        for payload in ["CSV_1", "CSV_2", "CSV_3", "CSV_4", "CSV_5"]:
            sanitized_name = sanitize_name(payload)
            with TaskGroup(group_id=f"{sanitized_name}") as etl_group:
                get_reqs = get_data_requirements.override(
                    task_id=f"get_data_requirements"
                )(payload)
                prep = prepare_extractor_params.override(
                    task_id=f"prepare_extractor_params"
                )(get_reqs)
                ext = extract.override(task_id=f"extract")()
                trans = transform.override(task_id=f"transform")(ext)
                load_task = load.override(task_id=f"load")(trans, payload)

                get_reqs >> prep >> ext >> trans >> load_task

        # 4. (Not here) update hydroserverpy functions to use the parameter format defined above.

    return run_etl()


hs_connection = HydroServerAirflowConnection("local_hydroserver_for_daniels_workspace")
uid = str(hs_connection.orchestration_system.uid)
datasources = read_datasources_from_file(uid)
for ds in datasources:
    new_dag = generate_dag(ds)
    globals()[new_dag.dag_id] = new_dag


#     """
#     Generate or overwrite a DAG file based on the current datasource configuration,
#     and sync paused state with HydroServer.
#     """
#     ds = self.data_source.dict()
#     schedule = ds.get("schedule", {}) or {}
#     dag_id = str(self.data_source.uid)

#     cron = schedule.get("crontab")
#     if cron:
#         schedule_interval = cron
#     else:
#         interval = schedule.get("interval", 1)
#         unit = schedule.get("intervalUnits", "minutes")
#         # Build an actual timedelta
#         schedule_interval = timedelta(**{unit: interval})

#     dag = DAG(
#         dag_id=dag_id,
#         schedule_interval=schedule_interval,
#         start_date=days_ago(1),
#         catchup=False,
#         tags=["hydroserver", "etl"],
#     )

#     def run_etl(task_group, task, **kwargs):
#         logging.info("HELLOOOOOO WORLDDDDDD")

#     with dag:
#         PythonOperator(
#             task_id="run_etl",
#             python_callable=run_etl,
#             op_kwargs={"task_group": "group 1", "task": "task 1"},
#         )

#     globals()[dag_id] = dag


# def generate_dag(self):
#     """
#     Generate or overwrite a DAG file based on the current datasource configuration,
#     and sync paused state with HydroServer.
#     """

#     # schedule interval
#     schedule = self.data_source.get("schedule", {})
#     logging.info(f"here's the schedule: {schedule}")
#     cron = schedule.get("crontab")
#     if cron:
#         schedule_interval = cron
#     else:
#         interval = schedule.get("interval", 1)
#         unit = schedule.get("intervalUnits", "minutes")
#         schedule_interval = f"timedelta({unit}={interval})"

#     dag = DAG(
#         dag_id=self.data_source.id,
#         schedule_interval=schedule_interval,
#         start_date=days_ago(1),
#         catchup=False,
#         tags=["hydroserver", "etl"],
#     )

#     def run_etl(task_group, task, **kwargs):
#         logging.info("HELLOOOOOO WORLDDDDDD")
#         # # Extractor
#         # ext_conf = task_group['settings']['extractor']
#         # extractor = make_extractor(ext_conf)

#         # # Transformer
#         # tr_conf = task_group['settings']['transformer']
#         # transformer = make_transformer(tr_conf)

#         # # Loader (credentials from Airflow connection)
#         # ld_conf = task_group['settings']['loader']
#         # loader = make_loader(ld_conf, conn_id)

#         # # Payload mapping / datastream IDs
#         # mapping = task_group.get('payloads', [])

#         # # Execute ETL
#         # etl = HydroServerETL(extractor, transformer, loader, mapping)
#         # etl.run()

#     with dag:
#         PythonOperator(
#             task_id="run_etl",
#             python_callable=run_etl,
#             op_kwargs={"task_group": "group 1", "task": "task 1"},
#         )

#     # Register DAG so Airflow can discover it
#     globals()[self.data_source.id] = dag


# class DagGenerator:
#     def __init__(self, data_source: object):
#         # For version 1, we'll just generate the DAG every time instead of checking for changes
#         self.data_source = data_source
#         self.generate_dag()

#     self.data_source = self.normalize_json(data_source)
#     self.prev_data_source = self.normalize_json(self.get_prev_data_source())
#     self.detected_changes = self.data_source != self.prev_data_source

#     if self.detected_changes:
#         self.generate_dag()

# def get_prev_data_source(self):
#     path = f"/tmp/dag_config_{self.data_source.uid}.json"
#     self.prev_data_source = None
#     if os.path.isfile(path):
#         with open(path) as f:
#             self.prev_data_source = json.load(f)

# def normalize_json(self, data_source):
#     """
#     Recursively sort dictionaries by key and lists by their JSON string representation,
#     so that equivalent JSON structures compare equal regardless of ordering.
#     """
#     if isinstance(data_source, dict):
#         return {k: self.normalize_json(data_source[k]) for k in sorted(data_source)}
#     if isinstance(data_source, list):
#         normalized_list = [self.normalize_json(item) for item in data_source]
#         try:
#             return sorted(
#                 normalized_list, key=lambda x: json.dumps(x, sort_keys=True)
#             )
#         except TypeError:
#             # Fallback: compare as strings
#             return sorted(normalized_list, key=lambda x: str(x))
#     return data_source

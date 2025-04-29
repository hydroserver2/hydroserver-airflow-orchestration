FROM apache/airflow:2.9.1

COPY requirements.txt .
COPY requirements-dev.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r requirements-dev.txt

ENV PYTHONPATH="${PYTHONPATH}:/opt/airflow/hydroserverpy"

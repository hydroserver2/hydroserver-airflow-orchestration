# Airflow Orchestration

This repository leverages the ETL (Extract, Transform, Load) capabilities of the python package 'hydroserverpy' in combination with Apache Airflow to automate job orchestration.

## Prerequisites

1. Have Docker Desktop installed.
2. Have Python 3.11 installed.

## Setup a development environment

1. Clone this repository
2. Clone https://github.com/hydroserver2/hydroserverpy.git in the same directory this repo was cloned to so that they're sister repos.
3. Run 'pip install -r requirements-dev.txt'.
4. Run 'docker-compose up -d --build'.

Your local Airflow console instance will be running at http://localhost:8080 after the docker container finishes building.

6. From the Airflow console menu bar go to 'admin' -> 'connections' & create a new connection for the test instance of HydroServer you'd like to connect to.
7. Pass the connection id created in step 4 into the 'get_hydroserver_loader()' function for each dag you'd like to test.

If the dags are visible and running successfully on the airflow console, you're done with your setup!

from airflow.hooks.base import BaseHook

from hydroserverpy.etl import (
    HTTPExtractor,
    LocalFileExtractor,
    JSONTransformer,
    CSVTransformer,
    HydroServerLoader,
)


def get_extractor(settings: dict):
    extractor_map = {"HTTP": HTTPExtractor, "local": LocalFileExtractor}
    extractor_type = settings["type"]
    cls = extractor_map.get(extractor_type)
    if cls is None:
        raise ValueError(f"Unknown extractor type: {extractor_type}")
    return cls(settings)


def get_transformer(settings: dict):
    transformer_map = {"JSON": JSONTransformer, "CSV": CSVTransformer}
    transformer_type = settings["type"]
    cls = transformer_map.get(transformer_type)
    if cls is None:
        raise ValueError(f"Unknown transformer type: {transformer_type}")
    return cls(settings)


def get_loader(settings: dict, conn_id: str):
    loader_map = {"HydroServer": HydroServerLoader}
    loader_type = settings["type"]
    cls = loader_map.get(loader_type)
    if cls is None:
        raise ValueError(f"Unknown loader type: {loader_type}")

    conn = BaseHook.get_connection(conn_id)
    scheme = conn.conn_type or "http"
    port = f":{conn.port}" if conn.port else ""
    base = f"{scheme}://{conn.host}{port}".rstrip("/")

    if key := conn.extra_dejson.get("api_key"):
        return cls(host=base, apikey=key)
    else:
        return cls(host=base, email=conn.login, password=conn.password)

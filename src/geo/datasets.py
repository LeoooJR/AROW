from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import geopandas
import pandas as pd


@dataclass(frozen=True)
class Dataset:

    id: str
    name: str
    lg: str
    format: Literal["csv", "json", "geojson", "shapefile", "parquet"]
    last_update: str
    hash: str  # sha256sum

    @property
    def full_path(self) -> Path:

        return (
            Path(__file__)
            .resolve()
            .parent.joinpath("statics", ".".join([self.name, self.format]))
        )


class DatasetRepository:

    BASE_URL = Path(__file__).resolve().parent.joinpath("statics")

    DATASETS: dict = {
        "gares-de-voyageurs": Dataset(
            id="gares-de-voyageurs",
            name="gares-de-voyageurs",
            lg="fr",
            format="geojson",
            last_update=None,
            hash="5bbc36c7be9b44499dacf9ffdde200085d4ba731d8561ce8cd2665df0ee1e31d",
        ),
        "lignes-par-type": Dataset(
            id="lignes-par-type",
            name="lignes-par-type",
            lg="fr",
            format="geojson",
            last_update=None,
            hash="2a0da177f597f1fa6122e18d510b3a601b9315bf2c2ab511e58adee2b054b18c",
        ),
        "referentiel_pk_gps": Dataset(
            id="referentiel_pk_gps",
            name="referentiel_pk_gps",
            lg="fr",
            format="csv",
            last_update=None,
            hash="0b106045e866aee214ea86700b50d6f6ab4c783a267a76c41d6674cde2de6d95",
        ),
    }

    @classmethod
    def get_all_dataset(cls) -> list[Dataset]:

        return list(cls.DATASETS.values())

    @classmethod
    def get_dataset(cls, id: str) -> Dataset | None:

        return cls.DATASETS.get(id, None)


class DatasetManager:

    REPOSITORY: DatasetRepository = DatasetRepository()

    @classmethod
    def read(
        cls, id: str, encoding: str = None
    ) -> geopandas.GeoDataFrame | pd.DataFrame:

        dataset: Dataset | None = cls.REPOSITORY.get_dataset(id)

        if dataset:

            if dataset.format in ["geojson", "shapefile"]:

                return geopandas.read_file(dataset.full_path, encoding=encoding)

            else:

                if dataset.format == "csv":

                    return pd.read_csv(
                        dataset.full_path, sep=";", header=0, encoding=encoding
                    )

                elif dataset.format == "json":

                    raise NotImplementedError

                elif dataset.format == "parquet":

                    raise NotImplementedError

        raise ValueError(f"Dataset {id} not found")

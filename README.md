# 2022 Oder evnironmental disaster

This repository contains the analytical pipeline for the research about the 2022 algal bloom disaster in Oder. The project uses Sentinel-2 data (10 and 20m bands) to visualise the bloom, separate the spectral characteristics of Prymnesium parvum, and to identify the impact of the bloom on the waters of Szczecin lagoon, Usedom-Wolin archipelago straits, and Pomeranian Bay.

The project is developed as a part of the curriculum for the course [GEO4515 - Remote Sensing of the Earth's surface](https://www.uio.no/studier/emner/matnat/geofag/GEO4515/index.html) at the University of Oslo. The project is authored by Michał Jan Odorczuk and Anna Wojciechowska.

The project is still ongoing, thus, not all the analysis and results are available yet. Check side branches for the in-progress files.

## Navigation

Consult other notebooks for the full research process. The available notebooks are:
 - [Main notebook](main.ipynb) - notebook including the introduction of the problem and explanation of the available data and the area of interest.
 - [Data fetching notebook](data_fetching.ipynb) - notebook including the whole pipeline for fetching the data from the Copernicus database, filtering it, processing, and storing in the format used by the further analysis.
 - [Local maps notebook](local_maps.ipynb) - demo notebook showing examples of available data for the areas of interest in the form of maps of small regions within our area of interest.
 - [Profile notebook](profile.ipynb) - demo notebook showing examples of available data for the whole river in the form of spectral (and spectra-derived) characteristics along the Oder centreline.
 - [Classification notebook](classification.ipynb) - demo notebook showing examples of classification of Oder waters.

You can find the auxiliary scripts in the [scirpts](scripts) directory. All the parametrisation of the data used for the research can be set in the [metadata file](metadata.json).
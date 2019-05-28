kedro.io
========

.. rubric:: Description

.. automodule:: kedro.io

Data Catalog
------------

.. autosummary::
    :toctree:
    :template: autosummary/class.rst

    kedro.io.DataCatalog

Data Sets
---------

.. autosummary::
    :toctree:
    :template: autosummary/class.rst

    kedro.io.CSVLocalDataSet
    kedro.io.CSVS3DataSet
    kedro.io.HDFLocalDataSet
    kedro.io.JSONLocalDataSet
    kedro.io.LambdaDataSet
    kedro.io.MemoryDataSet
    kedro.io.ParquetLocalDataSet
    kedro.io.PickleLocalDataSet
    kedro.io.PickleS3DataSet
    kedro.io.SQLTableDataSet
    kedro.io.SQLQueryDataSet
    kedro.io.TextLocalDataSet
    kedro.io.ExcelLocalDataSet

Additional ``AbstractDataSet`` implementations can be found in ``kedro.contrib.io``.

Errors
------

.. autosummary::
    :toctree:
    :template: autosummary/class.rst

    kedro.io.DataSetAlreadyExistsError
    kedro.io.DataSetError
    kedro.io.DataSetNotFoundError


Base Classes
------------

.. autosummary::
    :toctree:
    :template: autosummary/class.rst

    kedro.io.AbstractDataSet
    kedro.io.ExistsMixin
    kedro.io.FilepathVersionMixIn
    kedro.io.S3PathVersionMixIn
    kedro.io.Version

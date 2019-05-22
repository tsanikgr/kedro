# Copyright 2018-2019 QuantumBlack Visual Analytics Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
# NONINFRINGEMENT. IN NO EVENT WILL THE LICENSOR OR OTHER CONTRIBUTORS
# BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF, OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# The QuantumBlack Visual Analytics Limited (“QuantumBlack”) name and logo
# (either separately or in combination, “QuantumBlack Trademarks”) are
# trademarks of QuantumBlack. The License does not grant you any right or
# license to the QuantumBlack Trademarks. You may not use the QuantumBlack
# Trademarks or any confusingly similar mark as a trademark for your product,
#     or use the QuantumBlack Trademarks in any other manner that might cause
# confusion in the marketplace, including but not limited to in advertising,
# on websites, or on software.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""``CSVS3DataSet`` loads and saves data to a file in S3. It uses s3fs
to read and write from S3 and pandas to handle the csv file.
"""
from typing import Any, Dict, Optional

import pandas as pd
from s3fs.core import S3FileSystem

from kedro.io.core import (
    AbstractDataSet,
    DataSetError,
    ExistsMixin,
    S3PathVersionMixIn,
    Version,
)


class CSVS3DataSet(AbstractDataSet, ExistsMixin, S3PathVersionMixIn):
    """``CSVS3DataSet`` loads and saves data to a file in S3. It uses s3fs
    to read and write from S3 and pandas to handle the csv file.

    Example:
    ::

        >>> from kedro.io import CSVS3DataSet
        >>> import pandas as pd
        >>>
        >>> data = pd.DataFrame({'col1': [1, 2], 'col2': [4, 5],
        >>>                      'col3': [5, 6]})
        >>>
        >>> data_set = CSVS3DataSet(filepath="test.csv",
        >>>                         bucket_name="test_bucket",
        >>>                         load_args=None,
        >>>                         save_args={"index": False})
        >>> data_set.save(data)
        >>> reloaded = data_set.load()
        >>>
        >>> assert data.equals(reloaded)
    """

    def _describe(self) -> Dict[str, Any]:
        return dict(
            filepath=self._filepath,
            bucket_name=self._bucket_name,
            load_args=self._load_args,
            save_args=self._save_args,
            version=self._version,
        )

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        filepath: str,
        bucket_name: str,
        credentials: Optional[Dict[str, Any]] = None,
        load_args: Optional[Dict[str, Any]] = None,
        save_args: Optional[Dict[str, Any]] = None,
        version: Version = None,
    ) -> None:
        """Creates a new instance of ``CSVS3DataSet`` pointing to a concrete
        csv file on S3.

        Args:
            filepath: Path to a csv file.
            bucket_name: S3 bucket name.
            credentials: Credentials to access the S3 bucket, such as
                ``aws_access_key_id``, ``aws_secret_access_key``.
            load_args: Pandas options for loading csv files.
                Here you can find all available arguments:
                https://pandas.pydata.org/pandas-docs/stable/generated/pandas.read_csv.html
                All defaults are preserved.
            save_args: Pandas options for saving csv files.
                Here you can find all available arguments:
                https://pandas.pydata.org/pandas-docs/stable/generated/pandas.DataFrame.to_csv.html
                All defaults are preserved, but "index", which is set to False.
            version: If specified, should be an instance of
                ``kedro.io.core.Version``. If its ``load`` attribute is
                None, the latest version will be loaded. If its ``save``
                attribute is None, save version will be autogenerated.

        """
        default_save_args = {"index": False}
        self._save_args = (
            {**default_save_args, **save_args} if save_args else default_save_args
        )
        self._load_args = load_args if load_args else {}
        self._filepath = filepath
        self._bucket_name = bucket_name
        self._credentials = credentials if credentials else {}
        self._version = version
        self._s3 = S3FileSystem(client_kwargs=self._credentials)

    @property
    def _client(self):
        return self._s3.s3

    def _load(self) -> pd.DataFrame:
        load_key = self._get_load_path(
            self._client, self._bucket_name, self._filepath, self._version
        )

        with self._s3.open(
            "{}/{}".format(self._bucket_name, load_key), mode="rb"
        ) as s3_file:
            return pd.read_csv(s3_file, **self._load_args)

    def _save(self, data: pd.DataFrame) -> None:
        save_key = self._get_save_path(
            self._client, self._bucket_name, self._filepath, self._version
        )

        with self._s3.open(
            "{}/{}".format(self._bucket_name, save_key), mode="wb"
        ) as s3_file:
            # Only binary read and write modes are implemented for S3Files
            s3_file.write(data.to_csv(**self._save_args).encode("utf8"))

        load_key = self._get_load_path(
            self._client, self._bucket_name, self._filepath, self._version
        )
        self._check_paths_consistency(load_key, save_key)

    def _exists(self) -> bool:
        try:
            load_key = self._get_load_path(
                self._client, self._bucket_name, self._filepath, self._version
            )
        except DataSetError:
            return False
        args = (self._client, self._bucket_name, load_key)
        return any(key == load_key for key in self._list_objects(*args))

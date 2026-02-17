# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.


class JobErrors:
    @staticmethod
    def refresh_id_not_found() -> str:
        return (
            "Failed to extract refresh ID from API response. "
            "Neither Location header nor RequestId header present in response."
        )

    @staticmethod
    def dataset_refresh_params_not_supported() -> str:
        return (
            "Dataset refresh does not support -P/--params or -i/--input parameters. "
            "The refresh will use the default payload with retryCount=0."
        )

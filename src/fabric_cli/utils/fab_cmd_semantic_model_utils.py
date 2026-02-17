# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from argparse import Namespace
from typing import Callable

from fabric_cli.client.fab_api_types import ApiResponse
from fabric_cli.core import fab_constant
from fabric_cli.core.fab_exceptions import FabricCLIError
from fabric_cli.errors import ErrorMessages


def extract_dataset_refresh_id(response: ApiResponse) -> str:
    """
    Extract refresh ID from the POST datasets/refreshes response.

    Tries to get the refreshId from the Location header first. If not present,
    falls back to the RequestId header.

    Args:
        response: ApiResponse from refresh trigger request (202 status code)

    Returns:
        Refresh ID string suitable for display and polling

    Raises:
        FabricCLIError: If neither Location header nor RequestId are present
    """
    refresh_location_url = response.headers.get("Location", "")

    if refresh_location_url:
        return refresh_location_url.split("/")[-1]

    request_id = response.headers.get("RequestId", "")
    if not request_id:
        raise FabricCLIError(
            ErrorMessages.Job.refresh_id_not_found(),
            fab_constant.ERROR_API_FAILED,
        )

    return request_id


def create_refresh_status_function(
    job_response: ApiResponse, args: Namespace
) -> Callable[[Namespace], ApiResponse]:
    """
    Create a status polling function for dataset refresh.

    This function determines the appropriate API method to use based on the
    response headers from the POST dataset refresh trigger operation.

    Args:
        job_response: Initial API response from dataset refresh trigger
        args: Namespace containing ws_id and item_id

    Returns:
        A callable function that takes Namespace args and returns ApiResponse
        for polling refresh execution status
    """
    from fabric_cli.client import fab_api_semantic_model as sm_api

    refresh_location_url = job_response.headers.get("Location", "")

    if refresh_location_url:
        # Use the Location URL directly for polling
        return lambda a: sm_api.get_refresh_execution_details_by_url(
            a, refresh_url=refresh_location_url
        )

    # Fallback: use extract_dataset_refresh_id to get the refresh ID
    # and call get_refresh_execution_details (IDs extracted from args)
    refresh_id = extract_dataset_refresh_id(job_response)

    def polling_func(a: Namespace) -> ApiResponse:
        # Ensure args has the required attributes for get_refresh_execution_details
        a.ws_id = args.ws_id
        a.item_id = args.item_id
        a.refresh_id = refresh_id
        return sm_api.get_refresh_execution_details(a)

    return polling_func

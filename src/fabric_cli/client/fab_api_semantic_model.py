# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from argparse import Namespace

from fabric_cli.client import fab_api_client as fabric_api
from fabric_cli.client.fab_api_types import ApiResponse


def refresh_semantic_model(args: Namespace, payload: str) -> ApiResponse:
    """https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/refresh-dataset-in-group"""
    original_wait = getattr(args, "wait", False)

    args.uri = f"groups/{args.ws_id}/datasets/{args.item_id}/refreshes"
    args.method = "post"
    args.audience = "powerbi"
    args.wait = (
        False  # Disable automatic long-running operation polling for the HTTP request
    )

    response = fabric_api.do_request(args, data=payload)

    # Restore the original wait value for job polling
    args.wait = original_wait

    return response


def get_refresh_execution_details(args: Namespace) -> ApiResponse:
    """
    https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/get-refresh-execution-details-in-group
    """
    # Extract refresh ID from args (supports both instance_id and refresh_id attributes)
    refresh_id = getattr(args, "instance_id", None) or getattr(args, "refresh_id", None)

    if not refresh_id:
        raise ValueError("args must contain either 'instance_id' or 'refresh_id'")

    args.uri = f"groups/{args.ws_id}/datasets/{args.item_id}/refreshes/{refresh_id}"
    args.method = "get"
    args.audience = "powerbi"
    args.wait = False

    return fabric_api.do_request(args)


def get_refresh_execution_details_by_url(
    args: Namespace, refresh_url: str
) -> ApiResponse:
    """https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/get-refresh-execution-details-in-group"""
    from urllib.parse import urlparse

    parsed_url = urlparse(refresh_url)

    path_parts = parsed_url.path.split("/v1.0/myorg/", 1)
    if len(path_parts) == 2:
        uri = path_parts[1]
    else:
        uri = parsed_url.path.lstrip("/")

    hostname = parsed_url.netloc

    args.uri = uri
    args.method = "get"
    args.audience = "powerbi"
    args.wait = False

    return fabric_api.do_request(args, hostname=hostname)


def cancel_refresh(args: Namespace, refresh_id: str) -> ApiResponse:
    """https://learn.microsoft.com/en-us/rest/api/power-bi/datasets/cancel-refresh-in-group"""
    args.uri = f"groups/{args.ws_id}/datasets/{args.item_id}/refreshes/{refresh_id}"
    args.method = "delete"
    args.audience = "powerbi"

    return fabric_api.do_request(args)

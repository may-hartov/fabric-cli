# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from argparse import Namespace

from fabric_cli.client import fab_api_jobs as jobs_api
from fabric_cli.core.fab_types import FabricJobType
from fabric_cli.core.hiearchy.fab_hiearchy import Item
from fabric_cli.utils import fab_ui


def exec_command(args: Namespace, context: Item) -> None:
    if context.job_type == FabricJobType.SEMANTIC_MODEL_REFRESH:
        _exec_semantic_model_status(args, context)
    else:
        _exec_fabric_job_status(args, context)


def _exec_fabric_job_status(args: Namespace, context: Item) -> None:
    if args.schedule:
        args.schedule_id = args.id
        response = jobs_api.get_item_schedule(args)
    else:
        args.instance_id = args.id
        response = jobs_api.get_item_job_instance(args)

    if response.status_code == 200:
        content = json.loads(response.text)
        fab_ui.print_output_format(args, data=content, show_headers=True)


def _exec_semantic_model_status(args: Namespace, context: Item) -> None:
    from fabric_cli.client import fab_api_semantic_model as semantic_model_api

    # Semantic models don't support schedules via the job run-status command
    # (they would use Power BI's own refresh schedule API)
    if args.schedule:
        fab_ui.print_warning(
            "Schedule status not supported for semantic models via this command. "
            "Use Power BI portal or API to manage refresh schedules."
        )
        return

    # Set required IDs from context
    args.ws_id = context.workspace.id
    args.item_id = context.id
    args.instance_id = args.id

    response = semantic_model_api.get_refresh_execution_details(args)

    if response.status_code == 200:
        # Transform to match Fabric Job Instance format
        content = json.loads(response.text)
        transformed = _transform_to_job_instance_format(
            content, args.id, context.id)
        fab_ui.print_output_format(args, data=transformed, show_headers=True)
    # get execution details can retun 202, need to handle
    # elif response.status_code == 202:
    #     # For 202 (Accepted) responses, log the entire response as-is
    #     content = json.loads(response.text)
    #     fab_ui.print_output_format(args, data=content, show_headers=True)


def _transform_to_job_instance_format(
    content: dict, refresh_id: str, item_id: str
) -> dict:
    # Get status - prefer extendedStatus, fallback to status
    status = content.get("extendedStatus") or content.get("status")

    # Build base response matching ItemJobInstance schema
    transformed = {
        "id": refresh_id,
        "itemId": item_id,
        "jobType": "RefreshSemanticModel",
        "invokeType": content.get("currentRefreshType", "Unknown"),
        "status": status,
        "startTimeUtc": content.get("startTime"),
        "endTimeUtc": content.get("endTime"),
    }

    # Add failureReason only if status indicates failure
    if status and status.lower() not in ["completed", "success"]:
        failure_reason = _extract_failure_reason(content.get("messages", []))
        if failure_reason:
            transformed["failureReason"] = failure_reason

    return transformed


def _extract_failure_reason(messages: list) -> dict:
    if not messages:
        return None

    error_messages = [
        {"code": msg.get("code"), "message": msg.get("message")}
        for msg in messages
        if msg.get("type") == "Error"
    ]

    if not error_messages:
        return None

    return {"errors": error_messages}

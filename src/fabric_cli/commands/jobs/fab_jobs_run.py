# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import json
from argparse import Namespace

from fabric_cli.client import fab_api_jobs as jobs_api
from fabric_cli.core import fab_constant as con
from fabric_cli.core import fab_state_config as config
from fabric_cli.core.fab_types import FabricJobType
from fabric_cli.core.hiearchy.fab_hiearchy import Item
from fabric_cli.utils import fab_cmd_job_utils as utils_job
from fabric_cli.utils import fab_ui


def exec_command(args: Namespace, item: Item) -> None:
    """
    Execute job run command.
    Routes to appropriate implementation based on job type.
    """
    if item.job_type == FabricJobType.DATASET_REFRESH:
        _exec_semantic_model_refresh(args, item)
    else:
        _exec_fabric_job(args, item)


def _handle_timeout_cancellation(
    args: Namespace, job_id: str, job_type_name: str
) -> None:
    """
    Handle timeout cancellation decision and messaging.

    Args:
        args: Command arguments
        job_id: Job instance ID or refresh ID
        job_type_name: Display name for the job type (e.g., "Job instance", "Refresh")
    """
    if config.get_config(con.FAB_JOB_CANCEL_ONTIMEOUT) == "false":
        fab_ui.print_grey(
            f"{job_type_name} still running. To change this behaviour and cancel on timeout, set {con.FAB_JOB_CANCEL_ONTIMEOUT} config property to 'true'"
        )
    else:
        fab_ui.print_grey(
            f"Cancelling {job_type_name.lower()} '{job_id}' (timeout). To change this behaviour and continue running on timeout, set {con.FAB_JOB_CANCEL_ONTIMEOUT} config property to 'false'"
        )


def _cancel_fabric_job(args: Namespace, job_id: str) -> None:
    """
    Cancel a Fabric job instance on timeout.

    Args:
        args: Command arguments
        job_id: Job instance ID to cancel
    """
    _handle_timeout_cancellation(args, job_id, "Job instance")

    if config.get_config(con.FAB_JOB_CANCEL_ONTIMEOUT) != "false":
        args.instance_id = job_id
        response = jobs_api.cancel_item_job_instance(args)
        if response.status_code == 202:
            fab_ui.print_output_format(
                args,
                message=f"Job instance '{job_id}' cancelled (async)",
            )


def _cancel_dataset_refresh(args: Namespace, refresh_id: str) -> None:
    """
    Cancel a semantic model refresh on timeout.

    Args:
        args: Command arguments
        refresh_id: Refresh ID to cancel
    """
    from fabric_cli.client import fab_api_semantic_model as semantic_model_api

    _handle_timeout_cancellation(args, refresh_id, "Refresh")

    if config.get_config(con.FAB_JOB_CANCEL_ONTIMEOUT) != "false":
        response = semantic_model_api.cancel_refresh(args, refresh_id)
        if response.status_code == 200:
            fab_ui.print_output_format(
                args,
                message=f"Refresh '{refresh_id}' cancelled",
            )


def _wait_for_job_with_timeout(
    args: Namespace,
    job_id: str,
    response,
    job_type_name: str,
    is_dataset_refresh: bool,
    cancel_func,
) -> None:
    """
    Wait for job completion with timeout handling.

    Args:
        args: Command arguments
        job_id: Job instance ID or refresh ID
        response: Initial response from job creation
        job_type_name: Display name for the job type (e.g., "Job instance", "Refresh")
        is_dataset_refresh: Whether this is a dataset refresh
        cancel_func: Function to call to cancel the job on timeout
    """
    fab_ui.print_grey(
        f"∟ {job_type_name} '{job_id}' {'started' if is_dataset_refresh else 'created'}"
    )
    timeout = getattr(args, "timeout", None)
    if timeout is not None:
        fab_ui.print_grey(f"∟ Timeout: {timeout} seconds")
    else:
        fab_ui.print_grey("∟ Timeout: no timeout specified")

    try:
        utils_job.wait_for_job_completion(
            args,
            job_id,
            response,
            timeout=timeout,
            custom_polling_interval=getattr(args, "polling_interval", None),
            is_dataset_refresh=is_dataset_refresh,
        )
    except TimeoutError as e:
        fab_ui.print_warning(str(e))
        cancel_func(args, job_id)


def _exec_fabric_job(args: Namespace, item: Item) -> None:
    """Execute Fabric job (existing implementation for non-semantic model items)."""
    if getattr(args, "configuration", None) is not None:
        payload = json.dumps({"executionData": json.loads(args.configuration)})
    else:
        payload = None

    (response, job_instance_id) = jobs_api.run_on_demand_item_job(args, payload)

    if response.status_code == 202:
        if args.wait:
            _wait_for_job_with_timeout(
                args=args,
                job_id=job_instance_id,
                response=response,
                job_type_name="Job instance",
                is_dataset_refresh=False,
                cancel_func=_cancel_fabric_job,
            )
        else:
            fab_ui.print_output_format(
                args, message=f"Job instance '{job_instance_id}' created"
            )
            fab_ui.print_grey(
                f"→ To see status run 'job run-status {item.path} --id {job_instance_id}'"
            )


def _exec_semantic_model_refresh(args: Namespace, item: Item) -> None:
    """Execute semantic model (Power BI dataset) refresh."""
    from fabric_cli.client import fab_api_semantic_model as semantic_model_api
    from fabric_cli.utils import fab_cmd_semantic_model_utils as sm_utils

    # Dataset refresh always uses {"retryCount": 0} as the request body
    # -i/--input and -P/--params are not supported and are rejected in build_config_from_args()
    payload = json.dumps({"retryCount": 0})

    response = semantic_model_api.refresh_semantic_model(args, payload)

    if response.status_code == 202:
        # Extract refresh ID from response
        refresh_id = sm_utils.extract_dataset_refresh_id(response)

        # Job run always waits for semantic model refresh (no --wait flag support)
        _wait_for_job_with_timeout(
            args=args,
            job_id=refresh_id,
            response=response,
            job_type_name="Refresh",
            is_dataset_refresh=True,
            cancel_func=_cancel_dataset_refresh,
        )

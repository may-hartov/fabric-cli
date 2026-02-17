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
    if item.job_type == FabricJobType.SEMANTIC_MODEL_REFRESH:
        _exec_semantic_model_refresh(args, item)
    else:
        _exec_fabric_job(args, item)


def _cancel_fabric_job(args: Namespace, job_id: str) -> None:
    args.instance_id = job_id
    response = jobs_api.cancel_item_job_instance(args)
    if response.status_code == 202:
        fab_ui.print_output_format(
            args,
            message=f"Job instance '{job_id}' cancelled (async)",
        )


def _cancel_semantic_model_refresh(args: Namespace, refresh_id: str) -> None:
    from fabric_cli.client import fab_api_semantic_model as semantic_model_api

    response = semantic_model_api.cancel_refresh(args, refresh_id)
    if response.status_code == 200:
        fab_ui.print_output_format(
            args,
            message=f"Job instance '{refresh_id}' cancelled (async)",
        )


def _wait_for_job_with_timeout(
    args: Namespace,
    job_id: str,
    response,
    is_semantic_model_refresh: bool,
    cancel_func,
) -> None:
    fab_ui.print_grey(f"∟ Job instance '{job_id}' created'")
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
            is_semantic_model_refresh=is_semantic_model_refresh,
        )
    except TimeoutError as e:
        fab_ui.print_warning(str(e))
        if config.get_config(con.FAB_JOB_CANCEL_ONTIMEOUT) == "false":
            fab_ui.print_grey(
                f"Job still running. To change this behaviour and cancel on timeout, set {con.FAB_JOB_CANCEL_ONTIMEOUT} config property to 'true'"
            )
        else:
            fab_ui.print_grey(
                f"Cancelling job instance '{job_id}' (timeout). To change this behaviour and continue running on timeout, set {con.FAB_JOB_CANCEL_ONTIMEOUT} config property to 'false'"
            )

        if config.get_config(con.FAB_JOB_CANCEL_ONTIMEOUT) != "false":
            cancel_func(args, job_id)


def _handle_job_response(
    args: Namespace,
    item: Item,
    response,
    job_id: str,
    is_semantic_model_refresh: bool,
) -> None:
    if args.wait:
        cancel_func = (
            _cancel_semantic_model_refresh
            if is_semantic_model_refresh
            else _cancel_fabric_job
        )
        _wait_for_job_with_timeout(
            args=args,
            job_id=job_id,
            response=response,
            is_semantic_model_refresh=is_semantic_model_refresh,
            cancel_func=cancel_func,
        )
    else:
        fab_ui.print_output_format(args, message=f"Job instance '{job_id}' created")
        fab_ui.print_grey(
            f"→ To see status run 'job run-status {item.path} --id {job_id}'"
        )


def _exec_fabric_job(args: Namespace, item: Item) -> None:
    if getattr(args, "configuration", None) is not None:
        payload = json.dumps({"executionData": json.loads(args.configuration)})
    else:
        payload = None

    (response, job_instance_id) = jobs_api.run_on_demand_item_job(args, payload)

    if response.status_code == 202:
        _handle_job_response(
            args=args,
            item=item,
            response=response,
            job_id=job_instance_id,
            is_semantic_model_refresh=False,
        )


def _exec_semantic_model_refresh(args: Namespace, item: Item) -> None:
    from fabric_cli.client import fab_api_semantic_model as semantic_model_api
    from fabric_cli.utils import fab_cmd_semantic_model_utils as sm_utils

    payload = json.dumps({"retryCount": 0})

    response = semantic_model_api.refresh_semantic_model(args, payload)

    if response.status_code == 202:
        refresh_id = sm_utils.extract_semantic_model_refresh_id(response)

        _handle_job_response(
            args=args,
            item=item,
            response=response,
            job_id=refresh_id,
            is_semantic_model_refresh=True,
        )
